#!/usr/bin/env python3
"""Live eval for normalisation (#123): set the match threshold and compare the decision model with an LLM alone.

    uv run python -m scripts.eval_normalisation --out /tmp/normalisation-eval.json

Reads tests/fixtures/normalisation/eval_names.json, asks the decision model about every name (twice, for
consistency) and asks the naming LLM the same match question alone, then prints metrics per threshold.
Uses OPENROUTER_API_KEY from backend/.env. Costs well under $1.
"""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from dotenv import dotenv_values
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, SecretStr

from glean.catalogue.groups import GROUPS, GroupId
from glean.catalogue.normalise import NONE_OF_THESE, SHORTLIST_SIZE, questions_for
from glean.catalogue.seed import load_seed
from glean.catalogue.store import InMemoryCatalogueStore
from glean.llm import Feature, LLMRouter

if TYPE_CHECKING:
    from collections.abc import Sequence

_FIXTURE = Path(__file__).parents[1] / "tests" / "fixtures" / "normalisation" / "eval_names.json"
_GRID = [round(0.3 + 0.05 * step, 2) for step in range(14)]
# Rough tokens per character for pricing the naming LLM, which doesn't report usage through LLMRouter.
_FLASH_LITE_USD_PER_TOKEN = (0.10 / 1e6, 0.40 / 1e6)


class Outcome(StrEnum):
    CORRECT = "correct"
    DUPLICATE = "duplicate"  # an existing item fit, but the name was treated as new
    FALSE_MATCH = "false_match"  # matched to an item that is wrong, or to any item when none fits


@dataclass(frozen=True)
class Label:
    input: str
    expected: str | None  # catalogue item name, None for "no item fits", "NONSENSE" for a name with no meaning
    also_acceptable: tuple[str, ...] = ()
    expected_groups: tuple[str, ...] = ()


@dataclass(frozen=True)
class Prediction:
    match: str | None  # the shortlisted item picked, None for "none of these"
    probability: float
    kind_agrees: bool  # the item's kind equals the kind of the group chosen for the name


@dataclass(frozen=True)
class Metrics:
    threshold: float
    correct: int
    duplicates: int
    false_matches: int
    total: int

    @property
    def accuracy(self) -> float:
        return self.correct / self.total

    @property
    def false_match_rate(self) -> float:
        return self.false_matches / self.total

    @property
    def duplicate_rate(self) -> float:
        return self.duplicates / self.total


def classify(row: Label, predicted: str | None) -> Outcome:
    acceptable = {row.expected, *row.also_acceptable} - {None, "NONSENSE"}
    if predicted is None:
        return Outcome.DUPLICATE if row.expected not in (None, "NONSENSE") else Outcome.CORRECT
    return Outcome.CORRECT if predicted in acceptable else Outcome.FALSE_MATCH


def _predicted_at(prediction: Prediction, threshold: float) -> str | None:
    if prediction.match is None or prediction.probability < threshold or not prediction.kind_agrees:
        return None
    return prediction.match


def metrics_at(rows: Sequence[Label], predictions: Sequence[Prediction], threshold: float) -> Metrics:
    outcomes = [classify(row, _predicted_at(p, threshold)) for row, p in zip(rows, predictions, strict=True)]
    return Metrics(
        threshold=threshold,
        correct=outcomes.count(Outcome.CORRECT),
        duplicates=outcomes.count(Outcome.DUPLICATE),
        false_matches=outcomes.count(Outcome.FALSE_MATCH),
        total=len(outcomes),
    )


def pick_threshold(
    rows: Sequence[Label],
    predictions: Sequence[Prediction],
    *,
    max_false_match_rate: float,
    grid: Sequence[float] = _GRID,
) -> float:
    """The lowest threshold whose false-match rate stays within the budget; the highest grid value if none does."""
    for threshold in sorted(grid):
        if metrics_at(rows, predictions, threshold).false_match_rate <= max_false_match_rate:
            return threshold
    return max(grid)


class LLMOnlyAnswer(BaseModel):
    match: str = Field(description="The catalogue item name that is the same product, or 'none of these'.")
    ingredient_group: str = Field(description="The ingredient group id the item belongs to.")


_LLM_ONLY_PROMPT = (
    "You match a raw shopping name to a household catalogue. Pick the candidate that is the same product, or "
    "'none of these'. Also give the ingredient group id from this list: "
    + ", ".join(f"{group.value} ({rules.name})" for group, rules in GROUPS.items())
)


def _load_labels() -> list[Label]:
    return [
        Label(r["input"], r["expected"], tuple(r["also_acceptable"]), tuple(r["expected_groups"]))
        for r in json.loads(_FIXTURE.read_text())
    ]


def _decision_run(client: Any, label: Label, store: InMemoryCatalogueStore) -> dict[str, Any]:
    shortlist = store.shortlist(label.input, SHORTLIST_SIZE)
    state = {"name": label.input, "context": None, "shortlist": [item.name for item in shortlist]}
    started = time.monotonic()
    answer = client.decide(state, questions_for(label.input, shortlist))
    latency = time.monotonic() - started
    group = GroupId(answer.choice("ingredient_group").choice)
    match = answer.choice("match") if shortlist else None
    chosen = None if match is None or match.choice == NONE_OF_THESE else store.get_by_name(match.choice)
    return {
        "shortlist": [item.name for item in shortlist],
        "match": None if chosen is None else chosen.name,
        "probability": 0.0 if match is None else match.probabilities.get(match.choice, 0.0),
        "none_probability": 1.0 if match is None else match.probabilities.get(NONE_OF_THESE, 0.0),
        "kind_agrees": chosen is None or GROUPS[chosen.group].kind is GROUPS[group].kind,
        "group": group.value,
        "form": answer.choice("form").choice,
        "perishable": answer.noul("perishable").noul,
        "latency_s": latency,
        "cost_usd": answer.usage.cost,
        "model": answer.model,
    }


def _llm_only_run(router: LLMRouter, label: Label, store: InMemoryCatalogueStore) -> dict[str, Any]:
    shortlist = store.shortlist(label.input, SHORTLIST_SIZE)
    options = [item.name for item in shortlist] + [NONE_OF_THESE]
    prompt = f"Name: {label.input}\nCandidates: {options}"
    started = time.monotonic()
    answer = router.invoke(
        Feature.INGREDIENT_NORMALISATION,
        LLMOnlyAnswer,
        [SystemMessage(content=_LLM_ONLY_PROMPT), HumanMessage(content=prompt)],
        request_timeout=30_000,
    )
    latency = time.monotonic() - started
    chosen = answer.match if answer.match in {item.name for item in shortlist} else None
    cost = (len(_LLM_ONLY_PROMPT) + len(prompt)) / 4 * _FLASH_LITE_USD_PER_TOKEN[0] + 30 * _FLASH_LITE_USD_PER_TOKEN[1]
    return {"match": chosen, "group": answer.ingredient_group, "latency_s": latency, "cost_usd": cost}


def _evaluate(rows: list[Label], client: Any, router: LLMRouter) -> dict[str, Any]:
    store = InMemoryCatalogueStore(load_seed().items)
    with ThreadPoolExecutor(max_workers=8) as pool:
        first = list(pool.map(lambda row: _decision_run(client, row, store), rows))
        second = list(pool.map(lambda row: _decision_run(client, row, store), rows))
        llm_only = list(pool.map(lambda row: _llm_only_run(router, row, store), rows))
    return {"labels": [asdict(r) for r in rows], "decision": first, "decision_repeat": second, "llm_only": llm_only}


def _predictions(runs: Sequence[dict[str, Any]]) -> list[Prediction]:
    return [Prediction(r["match"], r["probability"], r["kind_agrees"]) for r in runs]


def report(results: dict[str, Any], *, max_false_match_rate: float) -> dict[str, Any]:
    rows = [
        Label(r["input"], r["expected"], tuple(r["also_acceptable"]), tuple(r["expected_groups"]))
        for r in results["labels"]
    ]
    # Names the catalogue already holds never reach the decision model in production, so score the rest.
    store = InMemoryCatalogueStore(load_seed().items)
    live = [i for i, row in enumerate(rows) if store.get_by_name(row.input) is None]
    rows = [rows[i] for i in live]
    first = _predictions([results["decision"][i] for i in live])
    repeat = _predictions([results["decision_repeat"][i] for i in live])
    llm_only = [Prediction(results["llm_only"][i]["match"], 1.0, True) for i in live]
    threshold = pick_threshold(rows, first, max_false_match_rate=max_false_match_rate)
    return {
        "names_scored": len(rows),
        "sweep": [
            asdict(metrics_at(rows, first, t)) | {"false_match_rate": metrics_at(rows, first, t).false_match_rate}
            for t in _GRID
        ],
        "threshold": threshold,
        "decision_at_threshold": asdict(metrics_at(rows, first, threshold)),
        "llm_only": asdict(metrics_at(rows, llm_only, 0.0)),
        "repeat_agreement": sum(
            _predicted_at(a, threshold) == _predicted_at(b, threshold) for a, b in zip(first, repeat, strict=True)
        )
        / len(rows),
        "decision_latency_median_s": sorted(r["latency_s"] for r in results["decision"])[len(results["decision"]) // 2],
        "decision_latency_max_s": max(r["latency_s"] for r in results["decision"]),
        "decision_cost_per_name_usd": sum(r["cost_usd"] for r in results["decision"]) / len(results["decision"]),
        "llm_only_latency_median_s": sorted(r["latency_s"] for r in results["llm_only"])[len(results["llm_only"]) // 2],
        "llm_only_cost_per_name_usd": sum(r["cost_usd"] for r in results["llm_only"]) / len(results["llm_only"]),
        "group_accuracy_on_unmatched": _group_accuracy(rows, results, live),
    }


def _group_accuracy(rows: Sequence[Label], results: dict[str, Any], live: Sequence[int]) -> float | None:
    graded = [(row, results["decision"][i]["group"]) for row, i in zip(rows, live, strict=True) if row.expected_groups]
    return sum(group in row.expected_groups for row, group in graded) / len(graded) if graded else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="Where to write the raw results JSON.")
    parser.add_argument("--max-false-match-rate", type=float, default=0.02)
    args = parser.parse_args(argv)
    from glean.decisions import DecisionClient  # noqa: PLC0415

    key = dotenv_values(Path(__file__).parents[1] / ".env").get("OPENROUTER_API_KEY")
    if not key or not key.startswith("sk-or-"):
        raise SystemExit("No real OPENROUTER_API_KEY in backend/.env")
    secret = SecretStr(key)
    results = _evaluate(_load_labels(), DecisionClient(api_key=secret, timeout_s=30.0), LLMRouter(api_key=secret))
    args.out.write_text(json.dumps(results, indent=1))
    print(json.dumps(report(results, max_false_match_rate=args.max_false_match_rate), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
