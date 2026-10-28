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

**A stored answer is the model's answer, and the bar is a policy over it.** Every answer keeps the option the
model chose and the probability that chose it, whatever bar was declared when it was asked, so one paid run
is enough to replay every candidate bar: the compare step applies each bar from 0.7 to 0.95 to those stored
probabilities and reports, per attribute, the accuracy of the answers each bar accepts and how much of the
sample they cover. What is chosen here goes into `MEASURED_BARS`; the answers themselves are a measurement,
not corpus data.

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

from glean.decisions import DecisionClient
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.attributes import ATTRIBUTE_QUESTIONS, UNSURE, RecipeAttributes
from glean.recipes.corpus import BlobCorpusBackend, RecipeCorpusStore
from glean.recipes.enrichment import run_enrichment
from glean.recipes.enrichment.active_time import ACTIVE_TIME_BAR, ACTIVE_TIME_ENRICHER
from glean.recipes.enrichment.attributes import ATTRIBUTE_ENRICHER, MEASURED_BARS
from glean.recipes.enrichment.enricher import ATTRIBUTE_BAR_MODEL, DEFAULT_ATTRIBUTE_BAR, MIN_ATTRIBUTE_BAR
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
# A bar is chosen for the corpus, not for the sample's luckiest answer: it has to be right at least this
# often on at least this many answers. Both are configurable on `compare`.
DEFAULT_TARGET_ACCURACY = 0.95
DEFAULT_MIN_ACCEPTED = 20
# The z for a 95% Wilson interval, used to rank bars when none meets the target.
_WILSON_Z = 1.96
# The bar each attribute ships with, so the report marks what production actually reads rather than one bar
# for all six. `--bar` overrides every mark, for weighing one candidate bar across the board.
SHIPPED_BARS: dict[str, float] = {**MEASURED_BARS, "active_time": ACTIVE_TIME_BAR}


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
                # What the run declared, for the record. It does not affect what is stored: every answer keeps
                # its top option, so the compare step can replay any bar over it.
                "bars": SHIPPED_BARS,
                "answers": answers,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Answers: {answers_path}")
    print(f"Model: {ATTRIBUTE_BAR_MODEL.request}")
    print(f"Next: uv run python scripts/check_recipe_attributes.py compare --sample {args.sample}")
    return 0


def _sample_enrichers() -> tuple[Enricher, ...]:
    """The two V5 enrichers as this build declares them; the stored answers keep every top option anyway."""
    return (ATTRIBUTE_ENRICHER, ACTIVE_TIME_ENRICHER)


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
    # The bars are measured for one model, so the sample is asked that model and no other.
    return DecisionClient(api_key=SecretStr(api_key), model=ATTRIBUTE_BAR_MODEL, timeout_s=timeout_s)


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

    @property
    def wilson_lower(self) -> float:
        """The lower end of the 95% Wilson score interval around this bar's accuracy.

        Accuracy alone favours a bar that accepted two answers and got both right. The interval asks how
        little the sample could be telling us, which is what a bar has to be defensible on.
        """
        if not self.accepted:
            return 0.0
        n = self.accepted
        p = self.correct / n
        centre = p + _WILSON_Z**2 / (2 * n)
        margin = _WILSON_Z * ((p * (1 - p) / n + _WILSON_Z**2 / (4 * n**2)) ** 0.5)
        return (centre - margin) / (1 + _WILSON_Z**2 / n)


@dataclass
class AttributeComparison:
    """One attribute's answers measured against an independent labeller."""

    attribute: str
    labelled: int
    answered: int
    truths: Counter[str] = field(default_factory=Counter)
    confused: Counter[tuple[str, str]] = field(default_factory=Counter)
    bars: list[BarResult] = field(default_factory=list)
    # (label, the answer's stored value, its probability), so a bar can be applied after the fact.
    pairs: list[tuple[str, str, float]] = field(default_factory=list)

    def unsure_at(self, bar: float) -> int:
        """Answers that read as `unsure` under `bar`: stored `unsure`, or under the bar.

        This is what a reader of the corpus would not see: their labels are in the store but the bar does not
        trust them. It is the number to watch when a bar is raised.
        """
        return sum(1 for _truth, value, probability in self.pairs if value == UNSURE or probability < bar)

    def chosen(
        self, *, target: float = DEFAULT_TARGET_ACCURACY, min_accepted: int = DEFAULT_MIN_ACCEPTED
    ) -> BarResult | None:
        """The loosest bar that is both accurate enough and measured on enough answers.

        Loosest, because a bar that clears the target on more answers describes more of the corpus: among bars
        that meet the target and the minimum, the lowest wins. Chasing accuracy alone picks the bar that
        happened to accept one right answer (a 1-of-1 bar scores 100%), which says nothing about the corpus.
        When no bar meets both, the best-supported one wins instead — the highest Wilson lower bound, so the
        report still names a defensible bar and says it fell short of the target.
        """
        if not self.bars:
            return None
        qualifying = [result for result in self.bars if result.accepted >= min_accepted and result.accuracy >= target]
        if qualifying:
            return min(qualifying, key=lambda result: result.bar)
        measured = [result for result in self.bars if result.accepted]
        if not measured:
            return None
        return max(measured, key=lambda result: (result.wilson_lower, result.coverage, -result.bar))

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
        for recipe_id in compared:
            truth = truths[recipe_id][attribute]
            prediction = answers.get(recipe_id, {}).get(attribute)
            value = str(prediction["value"]) if prediction is not None else UNSURE
            probability = float(prediction["probability"]) if prediction is not None else 0.0
            comparison.truths[truth] += 1
            comparison.pairs.append((truth, value, probability))
            if value != UNSURE:
                comparison.confused[(truth, value)] += 1
        for bar in bars:
            accepted = [pair for pair in comparison.pairs if pair[1] != UNSURE and pair[2] >= bar]
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
        target=args.target,
        min_accepted=args.min_accepted,
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
    production_bar: float | None = None,
    step: float = BAR_STEP,
    target: float = DEFAULT_TARGET_ACCURACY,
    min_accepted: int = DEFAULT_MIN_ACCEPTED,
    sample: str | None = None,
    enriched_at: str | None = None,
) -> str:
    """The report: per attribute, its confusion table, then every bar's accuracy and coverage.

    Each attribute is marked at the bar production reads it with (`SHIPPED_BARS`) unless `production_bar` is
    given, which marks one candidate bar across every attribute.
    """
    lines = []
    if sample:
        lines.append(f"Sample: {sample}   Enriched: {enriched_at or 'unknown'}")
    marked = (
        f"Marked bar: {production_bar:.2f} for every attribute"
        if production_bar is not None
        else "Marked bar: each attribute's shipped bar"
    )
    lines.extend(
        [
            f"Recipes labelled: {len(comparison.labels)}   Bars replayed: {MIN_ATTRIBUTE_BAR:.2f} to "
            f"{BAR_CEILING:.2f} by {step:.2f}   {marked}",
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
        lines.extend(
            _attribute_lines(
                attribute_comparison,
                marked_bar=_marked_bar(attribute_comparison.attribute, production_bar),
            )
        )

    lines.append(
        f"Chosen bars (the lowest bar at {target:.0%} accuracy or better on at least {min_accepted} answers; "
        f"when none qualifies, the highest Wilson lower bound):"
    )
    for attribute_comparison in comparison.attributes:
        chosen = attribute_comparison.chosen(target=target, min_accepted=min_accepted)
        if chosen is None:
            lines.append(f"  {attribute_comparison.attribute}: no accepted answers at any bar")
            continue
        meets_target = chosen.accepted >= min_accepted and chosen.accuracy >= target
        note = "" if meets_target else "  (no bar met the target; best supported)"
        lines.append(
            f"  {attribute_comparison.attribute}: {chosen.bar:.2f} - accuracy {chosen.accuracy:.1%} "
            f"on {chosen.accepted}/{attribute_comparison.labelled} labelled recipes "
            f"({chosen.coverage:.0%} coverage, Wilson lower bound {chosen.wilson_lower:.1%}){note}"
        )
    return "\n".join(lines)


def _marked_bar(attribute: str, production_bar: float | None) -> float:
    """The bar this attribute's row is marked at: the override, or the bar it actually ships with."""
    if production_bar is not None:
        return production_bar
    return SHIPPED_BARS.get(attribute, DEFAULT_ATTRIBUTE_BAR)


def _attribute_lines(comparison: AttributeComparison, *, marked_bar: float) -> list[str]:
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
    lines.append(
        f"  pred is what was stored; {comparison.unsure_at(marked_bar)} answer(s) fall below the marked "
        f"{marked_bar:.2f} bar and read as unsure"
    )
    for result in comparison.bars:
        marker = "*" if abs(result.bar - marked_bar) < 1e-9 else " "
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
    compare.add_argument(
        "--bar",
        type=float,
        default=None,
        help="Mark this bar for every attribute. Default: each attribute's shipped bar.",
    )
    compare.add_argument("--step", type=float, default=BAR_STEP, help="How finely the bars are replayed.")
    compare.add_argument(
        "--target",
        type=float,
        default=DEFAULT_TARGET_ACCURACY,
        help="The accuracy a chosen bar has to reach (default 95%%).",
    )
    compare.add_argument(
        "--min-accepted",
        type=int,
        default=DEFAULT_MIN_ACCEPTED,
        help="The answers a chosen bar has to accept before it can be chosen (default 20).",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
