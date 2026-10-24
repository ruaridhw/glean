#!/usr/bin/env python3
"""Measure V5's attributes against an independently labelled sample, and pick each attribute's bar.

Two steps, because the first one costs money and the second one does not:

    # 1. Ask the decision model about a local sample of exported recipes (paid; OPENROUTER_API_KEY needed).
    uv run python scripts/check_recipe_attributes.py enrich --sample <sample-dir>

    # 2. Compare the answers with an independent labeller's labels, and report the bar each attribute earns.
    uv run python scripts/check_recipe_attributes.py compare --sample <sample-dir>

The sample is a directory of exported recipe bodies (one `StoredRecipe` JSON per file) that lives **outside**
this repo, and the answers and labels sit beside it, never committed: recipe text is third-party (ADR 0016).
The default paths are the sample directory's sibling `v5-check/`, so a sample exported as `.../v5-sample/`
puts the answers at `.../v5-check/answers.json` and reads the labels from `.../v5-check/opus-labels.json`.

**The enrich step runs at the floor bar, not production's 0.8.** The point of the sample is to choose the
bar, and a bar can only be chosen from answers that keep their top option as far down as G1 allows (0.7).
The compare step then replays every bar from 0.7 to 0.95 and reports, per attribute, the accuracy of the
answers each bar accepts and how much of the sample those answers cover. What is chosen here is what the
enrichers get declared with; the answers themselves are a measurement, not corpus data.

Labels schema (what the independent labeller writes; values are the G1 table's, and `unsure` is allowed):

    {"<external_id>": {
        "main_protein": "chicken", "main_carb": "rice", "dish_type": "curry",
        "cuisine": "Middle Eastern", "whole_food": "whole|mixed|processed",
        "active_time_bucket": "<=15|15-30|30-45|45-60|60+",
        "confidence": {"<attribute>": "high|medium|low"}, "note": "..."}}

Spellings are normalised in one place, `glean.recipes.attributes`, so a label written "Thai-Inspired" or with
an en dash in its time bucket is read as the value it means. A label that normalises to nothing is reported,
never guessed.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import SecretStr, ValidationError

from glean.decisions import DECISION_MODEL, DecisionClient
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.attributes import ATTRIBUTE_QUESTIONS, UNSURE, RecipeAttributes
from glean.recipes.corpus import BlobCorpusBackend, RecipeCorpusStore
from glean.recipes.enrichment import run_enrichment
from glean.recipes.enrichment.active_time import ActiveTimeEnricher
from glean.recipes.enrichment.attributes import AttributeEnricher
from glean.recipes.enrichment.enricher import DEFAULT_ATTRIBUTE_BAR, MIN_ATTRIBUTE_BAR
from glean.recipes.stored import StoredRecipe

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from glean.recipes.enrichment import Enricher

__all__ = [
    "ATTRIBUTES",
    "AttributeComparison",
    "BarResult",
    "Comparison",
    "compare_answers",
    "load_labels",
    "load_sample",
    "main",
    "normalise_label",
    "normalise_labels",
]

# The six attributes, by the name a projection entry and a filter use.
ATTRIBUTES: tuple[str, ...] = tuple(ATTRIBUTE_QUESTIONS)
# The label schema calls the active-time bucket something else, because a label is prose-shaped.
_LABEL_KEYS: dict[str, str] = {"active_time": "active_time_bucket"}
# The bars worth reporting: G1's floor to one so strict that almost nothing clears it.
BAR_CEILING = 0.95
BAR_STEP = 0.05


def main(argv: Sequence[str] | None = None, *, client: DecisionClient | None = None) -> int:
    args = _parse_args(argv)
    if args.command == "enrich":
        return _enrich(args, client=client)
    return _compare(args)


# -- step 1: ask the model ------------------------------------------------------------------------


def _enrich(args: argparse.Namespace, *, client: DecisionClient | None) -> int:
    recipes = load_sample(args.sample)
    answers_path = args.answers or _v5_check_dir(args.sample) / "answers.json"
    print(f"Sample: {len(recipes)} recipes from {args.sample}")
    client = client or _client(timeout_s=args.timeout)

    with tempfile.TemporaryDirectory(prefix="glean-attribute-sample-") as scratch:
        corpus = RecipeCorpusStore(BlobCorpusBackend(FilesystemBlobStore(Path(scratch))))
        for recipe in recipes:
            corpus.save(recipe)
        report = run_enrichment(corpus, client, enrichers=_sample_enrichers(), max_workers=args.workers)
        answers = {recipe.external_id: _stored_answers(corpus, recipe.external_id) for recipe in recipes}

    print(report.render())
    answers_path.parent.mkdir(parents=True, exist_ok=True)
    answers_path.write_text(
        json.dumps(
            {
                "sample": str(args.sample),
                "enriched_at": datetime.now(UTC).isoformat(),
                # The floor is deliberate: choosing a bar needs the top option's probability, and 0.7 is the
                # lowest bar G1 allows, so nothing above the floor is thrown away.
                "bars": dict.fromkeys(ATTRIBUTES, MIN_ATTRIBUTE_BAR),
                "answers": answers,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Answers: {answers_path}")
    print(f"Model: {DECISION_MODEL}")
    print(f"Next: uv run python scripts/check_recipe_attributes.py compare --sample {args.sample}")
    return 0


def _sample_enrichers() -> tuple[Enricher, ...]:
    """The V5 enrichers at G1's floor, so every answer's top option is kept for the bar to be chosen from."""
    return (
        AttributeEnricher(bars=dict.fromkeys(ATTRIBUTES, MIN_ATTRIBUTE_BAR)),
        ActiveTimeEnricher(threshold=MIN_ATTRIBUTE_BAR),
    )


def _stored_answers(corpus: RecipeCorpusStore, recipe_id: str) -> dict[str, dict[str, Any]]:
    """One recipe's answers: the value and the probability that decided it, by attribute."""
    by_question = {answer.question: answer for answer in corpus.store.answers_for(recipe_id)}
    stored: dict[str, dict[str, Any]] = {}
    for attribute, question_name in ATTRIBUTE_QUESTIONS.items():
        answer = by_question.get(question_name)
        if answer is not None and answer.value is not None:
            stored[attribute] = {"value": answer.value, "probability": answer.probability}
    return stored


def load_sample(sample: Path) -> list[StoredRecipe]:
    """The exported recipe bodies in `sample`, one `StoredRecipe` JSON per file."""
    if not sample.is_dir():
        raise SystemExit(f"{sample} is not a directory of exported recipe bodies")
    recipes: list[StoredRecipe] = []
    for path in sorted(sample.glob("*.json")):
        try:
            recipes.append(StoredRecipe.model_validate(json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, ValueError, ValidationError) as error:
            raise SystemExit(f"{path} is not a readable exported recipe: {error}") from error
    if not recipes:
        raise SystemExit(f"{sample} holds no *.json recipe bodies")
    return recipes


def _client(*, timeout_s: float) -> DecisionClient:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("Set OPENROUTER_API_KEY: the enrich step asks the decision model, which is billed.")
    return DecisionClient(api_key=SecretStr(api_key), timeout_s=timeout_s)


# -- step 2: compare against the labels -----------------------------------------------------------


@dataclass(frozen=True)
class BarResult:
    """What one candidate bar makes of the sample."""

    bar: float
    accepted: int
    correct: int
    coverage: float

    @property
    def accuracy(self) -> float:
        return self.correct / self.accepted if self.accepted else 0.0


@dataclass
class AttributeComparison:
    """One attribute's answers measured against an independent labeller."""

    attribute: str
    labelled: int
    answered: int
    truths: Counter[str] = field(default_factory=Counter)
    confused: Counter[tuple[str, str]] = field(default_factory=Counter)
    bars: list[BarResult] = field(default_factory=list)

    @property
    def unsure(self) -> int:
        """Answers stored as `unsure`, which no bar accepts and so no accuracy is claimed for."""
        return max(self.answered - sum(self.confused.values()), 0)

    @property
    def best(self) -> BarResult | None:
        """The bar with the best accuracy, then the widest coverage, then the loosest bar.

        The loosest bar on a tie is deliberate: the sample is 50 recipes, and a bar should not be raised
        past what the sample's accuracy supports. Coverage is reported beside every bar so the owner can
        trade some of it back for a stricter bar if they would rather.
        """
        if not self.bars:
            return None
        return max(self.bars, key=lambda result: (result.accuracy, result.coverage, -result.bar))

    def at(self, bar: float) -> BarResult:
        return next(result for result in self.bars if abs(result.bar - bar) < 1e-9)


@dataclass
class Comparison:
    """Every attribute's measurement, plus what could not be measured."""

    labels: dict[str, dict[str, str]]
    unreadable_labels: list[tuple[str, str, str]]
    attributes: list[AttributeComparison]

    def attribute(self, name: str) -> AttributeComparison:
        return next(comparison for comparison in self.attributes if comparison.attribute == name)


def compare_answers(
    answers: Mapping[str, Mapping[str, Mapping[str, Any]]],
    labels: Mapping[str, Mapping[str, Any]],
    *,
    step: float = BAR_STEP,
) -> Comparison:
    """Measure `answers` against `labels`, replaying every bar the enrichers may be declared at.

    `answers` is the enrich step's body (recipe id -> attribute -> value/probability); `labels` is the
    labeller's mapping (recipe id -> its attributes). A label that normalises to nothing, and a label of
    `unsure`, carry no truth: they are reported rather than scored.
    """
    truths, unreadable = normalise_labels(labels)
    bars = _bars(step)
    attributes: list[AttributeComparison] = []
    for attribute in ATTRIBUTES:
        compared = sorted(recipe_id for recipe_id in truths if attribute in truths[recipe_id])
        comparison = AttributeComparison(
            attribute=attribute,
            labelled=len(compared),
            answered=sum(1 for recipe_id in compared if attribute in answers.get(recipe_id, {})),
        )
        pairs: list[tuple[str, str, float]] = []
        for recipe_id in compared:
            truth = truths[recipe_id][attribute]
            prediction = answers.get(recipe_id, {}).get(attribute)
            value = str(prediction["value"]) if prediction is not None else UNSURE
            probability = float(prediction["probability"]) if prediction is not None else 0.0
            comparison.truths[truth] += 1
            pairs.append((truth, value, probability))
            if value != UNSURE:
                comparison.confused[(truth, value)] += 1
        for bar in bars:
            accepted = [pair for pair in pairs if pair[1] != UNSURE and pair[2] >= bar]
            comparison.bars.append(
                BarResult(
                    bar=bar,
                    accepted=len(accepted),
                    correct=sum(1 for truth, value, _probability in accepted if truth == value),
                    coverage=len(accepted) / len(compared) if compared else 0.0,
                )
            )
        attributes.append(comparison)
    return Comparison(labels=truths, unreadable_labels=unreadable, attributes=attributes)


def normalise_label(attribute: str, value: Any) -> str | None:
    """The G1 value a label means (`unsure` included), or None when it names none of them."""
    attributes = RecipeAttributes.from_mapping({attribute: value})
    normalised = getattr(attributes, attribute).value
    if normalised == UNSURE and not _is_unsure(value):
        return None
    return normalised


def normalise_labels(labels: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, dict[str, str]], list[tuple]]:
    """Every recipe's usable labels, plus the ones that named no value (reported, never guessed)."""
    truths: dict[str, dict[str, str]] = {}
    unreadable: list[tuple[str, str, str]] = []
    for recipe_id, label in labels.items():
        values: dict[str, str] = {}
        for attribute in ATTRIBUTES:
            raw = label.get(_LABEL_KEYS.get(attribute, attribute))
            if raw is None:
                continue
            normalised = normalise_label(attribute, raw)
            if normalised is None:
                unreadable.append((str(recipe_id), attribute, str(raw)))
            elif normalised != UNSURE:  # the labeller could not tell either: no truth to score
                values[attribute] = normalised
        truths[str(recipe_id)] = values
    return truths, unreadable


def load_labels(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise SystemExit(f"{path} is not a readable labels file: {error}") from error
    if not isinstance(loaded, dict) or not all(isinstance(value, dict) for value in loaded.values()):
        raise SystemExit(f"{path} is not a labels file: it must map each recipe id to its attributes")
    return loaded


def _compare(args: argparse.Namespace) -> int:
    answers_path = args.answers or _v5_check_dir(args.sample) / "answers.json"
    labels_path = args.labels or _v5_check_dir(args.sample) / "opus-labels.json"
    try:
        answers = json.loads(answers_path.read_text(encoding="utf-8"))
        run = answers["answers"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f"{answers_path} is not an answers file from the enrich step: {error}") from error
    labels = load_labels(labels_path)

    comparison = compare_answers(run, labels, step=args.step)
    rendered = render_comparison(
        comparison,
        production_bar=args.bar,
        step=args.step,
        sample=answers.get("sample"),
        enriched_at=answers.get("enriched_at"),
    )
    print(rendered)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
        print(f"Report: {args.report}")
    return 0


def render_comparison(
    comparison: Comparison,
    *,
    production_bar: float = DEFAULT_ATTRIBUTE_BAR,
    step: float = BAR_STEP,
    sample: str | None = None,
    enriched_at: str | None = None,
) -> str:
    """The report: per attribute, its confusion table, then every bar's accuracy and coverage."""
    lines = []
    if sample:
        lines.append(f"Sample: {sample}   Enriched: {sample and (enriched_at or 'unknown')}")
    lines.extend(
        [
            f"Recipes labelled: {len(comparison.labels)}   Bars replayed: {MIN_ATTRIBUTE_BAR:.2f} to "
            f"{BAR_CEILING:.2f} by {step:.2f}   Marked bar: {production_bar:.2f}",
            "",
        ]
    )
    if comparison.unreadable_labels:
        lines.append(f"Labels that named no G1 value ({len(comparison.unreadable_labels)}), left out of the scoring:")
        lines.extend(
            f"  {recipe_id} {attribute}: {raw!r}" for recipe_id, attribute, raw in comparison.unreadable_labels[:10]
        )
        lines.append("")

    for attribute_comparison in comparison.attributes:
        lines.extend(_attribute_lines(attribute_comparison, production_bar=production_bar))

    lines.append("Chosen bars (best accuracy; ties go to wider coverage, then the looser bar):")
    for attribute_comparison in comparison.attributes:
        best = attribute_comparison.best
        if best is None or best.accepted == 0:
            lines.append(f"  {attribute_comparison.attribute}: no accepted answers at any bar")
            continue
        lines.append(
            f"  {attribute_comparison.attribute}: {best.bar:.2f} - accuracy {best.accuracy:.1%} "
            f"on {best.accepted}/{attribute_comparison.labelled} labelled recipes ({best.coverage:.0%} coverage)"
        )
    return "\n".join(lines)


def _attribute_lines(comparison: AttributeComparison, *, production_bar: float) -> list[str]:
    lines = [f"{comparison.attribute}: {comparison.labelled} labelled, {comparison.answered} answered"]
    if not comparison.confused:
        return [*lines, "  nothing accepted at any bar", ""]
    truths = sorted(comparison.truths)
    values = sorted({predicted for _truth, predicted in comparison.confused})
    width = max(len(value) for value in [*values, *truths, "truth"])
    lines.append("  " + " " * (width + 2) + "  ".join(value.ljust(width) for value in values))
    for truth in truths:
        cells = [str(comparison.confused.get((truth, value), 0)).ljust(width) for value in values]
        lines.append(f"  {truth.ljust(width)}  " + "  ".join(cells))
    lines.append(f"  pred is what was stored; {comparison.unsure} answer(s) were stored unsure")
    for result in comparison.bars:
        marker = "*" if abs(result.bar - production_bar) < 1e-9 else " "
        lines.append(
            f"  {marker}{result.bar:.2f}  accepted {result.accepted:>3}  accuracy {result.accuracy:6.1%}  "
            f"coverage {result.coverage:6.1%}"
        )
    lines.append("")
    return lines


# -- shared ---------------------------------------------------------------------------------------


def _bars(step: float) -> list[float]:
    count = round((BAR_CEILING - MIN_ATTRIBUTE_BAR) / step)
    return [round(MIN_ATTRIBUTE_BAR + index * step, 4) for index in range(count + 1)]


def _is_unsure(value: Any) -> bool:
    return isinstance(value, str) and value.strip().casefold() == UNSURE


def _v5_check_dir(sample: Path) -> Path:
    """Where a sample's answers and labels live: a `v5-check/` directory beside the sample itself."""
    return sample.resolve().parent / "v5-check"


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure the V5 attributes against an independently labelled sample.", allow_abbrev=False
    )
    commands = parser.add_subparsers(dest="command", required=True)

    enrich = commands.add_parser("enrich", help="Ask the model about the sample (paid), and write the answers.")
    enrich.add_argument("--sample", type=Path, required=True, help="Directory of exported recipe bodies (*.json).")
    enrich.add_argument("--answers", type=Path, default=None, help="Answers file; defaults beside the sample.")
    enrich.add_argument("--workers", type=int, default=4, help="Concurrent decision requests.")
    enrich.add_argument("--timeout", type=float, default=30.0, help="Seconds to wait for each answer.")

    compare = commands.add_parser("compare", help="Compare the answers with the labels. No model calls.")
    compare.add_argument("--sample", type=Path, required=True, help="The sample directory the answers came from.")
    compare.add_argument("--answers", type=Path, default=None, help="Answers file; defaults beside the sample.")
    compare.add_argument("--labels", type=Path, default=None, help="Labels file; defaults beside the sample.")
    compare.add_argument("--report", type=Path, default=None, help="Also write the report here.")
    compare.add_argument("--bar", type=float, default=DEFAULT_ATTRIBUTE_BAR, help="The bar the report marks.")
    compare.add_argument("--step", type=float, default=BAR_STEP, help="How finely the bars are replayed.")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
