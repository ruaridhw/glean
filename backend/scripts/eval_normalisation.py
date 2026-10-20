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
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from dotenv import dotenv_values
from pydantic import BaseModel, Field, SecretStr

from glean.catalogue.groups import GROUPS, GroupId, Kind
from glean.catalogue.normalise import NONE_OF_THESE, SHORTLIST_SIZE, normalise, questions_for
from glean.catalogue.seed import load_seed
from glean.catalogue.store import InMemoryCatalogueStore
from glean.llm import Feature, LLMRouter

if TYPE_CHECKING:
    from collections.abc import Sequence

_FIXTURE = Path(__file__).parents[1] / "tests" / "fixtures" / "normalisation" / "eval_names.json"
_GRID = [round(0.3 + 0.05 * step, 2) for step in range(14)]
# Rough tokens per character for pricing the naming LLM, which doesn't report usage through LLMRouter.
_FLASH_LITE_USD_PER_TOKEN = (0.10 / 1e6, 0.40 / 1e6)


class Grade(StrEnum):
    """How a whole pipeline result compares with its label."""

    CORRECT = "correct"
    DUPLICATE = "duplicate"  # an existing item fit, but a new item was created
    FALSE_MATCH = "false_match"  # matched to a wrong item, or to any item for a name with no fitting item
    KIND_ERROR = "kind_error"  # created in a group of the wrong kind: a household good as a food, or the reverse
    WRONG_GROUP = "wrong_group"  # created in a group outside the acceptable ones, but of the right kind
    WRONG_UNMATCHED = "wrong_unmatched"  # called unidentifiable, but it is a real item
    NONSENSE_NAMED = "nonsense_named"  # nonsense that was given an item anyway
    UNRESOLVED = "unresolved"  # nothing settled; a retry would be needed


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


def _kind_of_group(group: str) -> str:
    return "household_item" if GROUPS[GroupId(group)].kind is Kind.HOUSEHOLD else "ingredient"


def grade_result(row: Label, *, status: str, canonical: str, group: str | None, kind: str | None) -> Grade:
    """Grade a pipeline result: status, the resolved item's (or created item's) name, its group and kind."""
    if status == "unresolved":
        return Grade.UNRESOLVED
    nonsense = row.expected == "NONSENSE"
    acceptable = {row.expected, *row.also_acceptable} - {None, "NONSENSE"}
    if status == "unmatched":
        return Grade.CORRECT if nonsense else Grade.WRONG_UNMATCHED
    if status == "matched":
        return Grade.CORRECT if canonical in acceptable else Grade.FALSE_MATCH
    if nonsense:
        return Grade.NONSENSE_NAMED
    if acceptable and row.expected is not None:
        return Grade.DUPLICATE
    if not row.expected_groups or group in row.expected_groups:
        return Grade.CORRECT
    wanted_kinds = {_kind_of_group(g) for g in row.expected_groups}
    return Grade.KIND_ERROR if kind not in wanted_kinds else Grade.WRONG_GROUP


class LLMOnlyAnswer(BaseModel):
    match: str = Field(description="The catalogue item name that is the same product, or 'none of these'.")
    canonical_name: str | None = Field(
        description="When nothing matches: the plain canonical name for a new item, or null if the input is nonsense."
    )
    ingredient_group: str = Field(description="The ingredient group id the item belongs to.")


_LLM_ONLY_PROMPT = (
    "You match a raw shopping name to a household catalogue. Pick the candidate that is the same product, or "
    "'none of these'. If none matches, give the plain canonical name for a new item (strip brands and sizes; "
    "household goods keep a name close to what was written), or null if the input is nonsense. Also give the "
    "ingredient group id from this list: "
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


def _flash_lite_cost(chars_in: int, chars_out: int) -> float:
    return chars_in / 4 * _FLASH_LITE_USD_PER_TOKEN[0] + chars_out / 4 * _FLASH_LITE_USD_PER_TOKEN[1]


class _Recorder:
    """Wraps the real decision client and LLM router to total up calls, latency and cost."""

    def __init__(self, client: Any, router: LLMRouter) -> None:
        self._client, self._router = client, router
        self._lock = threading.Lock()
        self.decision_calls = 0
        self.decision_cost = 0.0
        self.naming_calls = 0
        self.naming_cost = 0.0

    def decide(self, state: Any, questions: Any) -> Any:
        answer = self._client.decide(state, questions)
        with self._lock:
            self.decision_calls += 1
            self.decision_cost += answer.usage.cost
        return answer

    def invoke(self, feature: Any, schema: Any, *, system: str, user: str, **kwargs: Any) -> Any:
        reply = self._router.invoke(feature, schema, system=system, user=user, **kwargs)
        self.naming_calls += 1
        self.naming_cost += _flash_lite_cost(len(system) + len(user), len(reply.model_dump_json()))
        return reply


def _pipeline_run(rows: Sequence[Label], client: Any, router: LLMRouter) -> dict[str, Any]:
    """The whole service over the set in batches of 20, each against a fresh seeded catalogue, with real fallback."""
    results: list[dict[str, Any]] = []
    batches: list[dict[str, Any]] = []
    for start in range(0, len(rows), 20):
        batch = rows[start : start + 20]
        recorder = _Recorder(client, router)
        store = InMemoryCatalogueStore(load_seed().items)
        began = time.monotonic()
        out = normalise([row.input for row in batch], store=store, decisions=recorder, llm_router=recorder)  # ty: ignore[invalid-argument-type]
        batches.append(
            {
                "names": len(batch),
                "latency_s": time.monotonic() - began,
                "cost_usd": recorder.decision_cost + recorder.naming_cost,
                "decision_calls": recorder.decision_calls,
                "naming_calls": recorder.naming_calls,
            }
        )
        for row, result in zip(batch, out, strict=True):
            grade = grade_result(
                row,
                status=result.status.value,
                canonical=result.canonical_name,
                group=result.ingredient_group.value if result.ingredient_group else None,
                kind=result.kind.value if result.kind else None,
            )
            results.append(
                {
                    "input": row.input,
                    "status": result.status.value,
                    "canonical": result.canonical_name,
                    "group": result.ingredient_group.value if result.ingredient_group else None,
                    "source": result.source.value,
                    "grade": grade.value,
                }
            )
    return {"results": results, "batches": batches}


def _llm_only_run(router: LLMRouter, label: Label, store: InMemoryCatalogueStore) -> dict[str, Any]:
    shortlist = store.shortlist(label.input, SHORTLIST_SIZE)
    options = [item.name for item in shortlist] + [NONE_OF_THESE]
    prompt = f"Name: {label.input}\nCandidates: {options}"
    started = time.monotonic()
    answer = router.invoke(
        Feature.INGREDIENT_NORMALISATION,
        LLMOnlyAnswer,
        system=_LLM_ONLY_PROMPT,
        user=prompt,
        timeout_ms=30_000,
    )
    latency = time.monotonic() - started
    chosen = answer.match if answer.match in {item.name for item in shortlist} else None
    group = answer.ingredient_group if answer.ingredient_group in {g.value for g in GroupId} else GroupId.OTHER.value
    if chosen is not None:
        status, canonical = "matched", chosen
    elif answer.canonical_name:
        status, canonical = "created", answer.canonical_name
    else:
        status, canonical = "unmatched", label.input
    grade = grade_result(label, status=status, canonical=canonical, group=group, kind=_kind_of_group(group))
    cost = _flash_lite_cost(len(_LLM_ONLY_PROMPT) + len(prompt), len(answer.model_dump_json()))
    return {
        "match": chosen,
        "status": status,
        "canonical": canonical,
        "group": group,
        "grade": grade.value,
        "latency_s": latency,
        "cost_usd": cost,
    }


def _evaluate(rows: list[Label], client: Any, router: LLMRouter) -> dict[str, Any]:
    store = InMemoryCatalogueStore(load_seed().items)
    with ThreadPoolExecutor(max_workers=8) as pool:
        first = list(pool.map(lambda row: _decision_run(client, row, store), rows))
        second = list(pool.map(lambda row: _decision_run(client, row, store), rows))
        llm_only = list(pool.map(lambda row: _llm_only_run(router, row, store), rows))
    return {
        "labels": [asdict(r) for r in rows],
        "decision": first,
        "decision_repeat": second,
        "llm_only": llm_only,
        "pipeline": _pipeline_run(rows, client, router),
    }


def _predictions(runs: Sequence[dict[str, Any]]) -> list[Prediction]:
    return [Prediction(r["match"], r["probability"], r["kind_agrees"]) for r in runs]


def _grade_counts(grades: Sequence[str]) -> dict[str, int]:
    return {grade.value: grades.count(grade.value) for grade in Grade}


def _group_accuracy(rows: Sequence[Label], results: dict[str, Any], live: Sequence[int]) -> float | None:
    graded = [(row, results["decision"][i]["group"]) for row, i in zip(rows, live, strict=True) if row.expected_groups]
    return sum(group in row.expected_groups for row, group in graded) / len(graded) if graded else None


def report(results: dict[str, Any], *, max_false_match_rate: float) -> dict[str, Any]:
    """Two parts: the decision-stage threshold sweep, and the whole pipeline against the LLM alone."""
    all_rows = [
        Label(r["input"], r["expected"], tuple(r["also_acceptable"]), tuple(r["expected_groups"]))
        for r in results["labels"]
    ]
    # Names the catalogue already holds never reach the decision model in production, so score the rest.
    store = InMemoryCatalogueStore(load_seed().items)
    live = [i for i, row in enumerate(all_rows) if store.get_by_name(row.input) is None]
    rows = [all_rows[i] for i in live]
    first = _predictions([results["decision"][i] for i in live])
    repeat = _predictions([results["decision_repeat"][i] for i in live])
    threshold = pick_threshold(rows, first, max_false_match_rate=max_false_match_rate)
    sweep = []
    for t in _GRID:
        m = metrics_at(rows, first, t)
        sweep.append(asdict(m) | {"false_match_rate": m.false_match_rate})
    batches = results["pipeline"]["batches"]
    pipeline = [results["pipeline"]["results"][i]["grade"] for i in live]
    llm_only = [results["llm_only"][i]["grade"] for i in live]
    llm_latencies = sorted(r["latency_s"] for r in results["llm_only"])
    return {
        "decision_stage": {
            "names_scored": len(rows),
            "sweep": sweep,
            "threshold": threshold,
            "repeat_agreement": sum(
                _predicted_at(a, threshold) == _predicted_at(b, threshold) for a, b in zip(first, repeat, strict=True)
            )
            / len(rows),
            "latency_median_s": sorted(r["latency_s"] for r in results["decision"])[len(results["decision"]) // 2],
            "group_accuracy_on_unmatched": _group_accuracy(rows, results, live),
        },
        "pipeline": {
            "names_scored": len(live),
            "grades": _grade_counts(pipeline),
            "batch_latency_max_s": max(b["latency_s"] for b in batches),
            "batch_names": [b["names"] for b in batches],
            "cost_per_name_usd": sum(b["cost_usd"] for b in batches) / sum(b["names"] for b in batches),
            "naming_calls_per_batch": [b["naming_calls"] for b in batches],
        },
        "llm_only": {
            "grades": _grade_counts(llm_only),
            "latency_median_s": llm_latencies[len(llm_latencies) // 2],
            "cost_per_name_usd": sum(r["cost_usd"] for r in results["llm_only"]) / len(results["llm_only"]),
        },
    }


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
