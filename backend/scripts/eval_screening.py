#!/usr/bin/env python3
"""Live calibration of the injection screen's bar (spec §6.1, "Confidence bars").

    cd backend && uv run python -m scripts.eval_screening --out /tmp/screening-eval.json

Reads tests/fixtures/screening_calibration.json — 60 synthetic, hand-labelled notes, half benign food
preferences and half injection attempts — and asks the pinned decision model the screening question
about each one. It reports how the shipped bar (SCREEN_BAR) does on that set and what the neighbouring
thresholds would do, then writes the probabilities so a change can be compared with the old run.

This spends real money (60 decision calls, well under $1) and needs OPENROUTER_API_KEY in backend/.env.
Run it before changing SCREEN_BAR, the question, or the pinned decision model, and put the resulting
numbers in the PR that changes them.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TYPE_CHECKING

from dotenv import dotenv_values
from pydantic import SecretStr

from glean.decisions import DECISION_MODEL, DecisionClient, DecisionError
from glean.screening import SCREEN_BAR, SCREEN_QUESTION, SCREEN_QUESTION_NAME

if TYPE_CHECKING:
    from collections.abc import Sequence

_FIXTURE = Path(__file__).parents[1] / "tests" / "fixtures" / "screening_calibration.json"
# The shipped bar, and the thresholds either side of it, so a report shows what moving it would cost.
_GRID = [round(0.5 + 0.025 * step, 3) for step in range(21)]

FOOD_PREFERENCE = "food_preference"
INSTRUCTION = "instruction"


def _load_items() -> list[dict[str, str]]:
    return json.loads(_FIXTURE.read_text())


def _measure(client: DecisionClient, items: Sequence[dict[str, str]]) -> list[dict[str, object]]:
    measured = []
    for item in items:
        try:
            decision = client.decide({"note": item["text"]}, {SCREEN_QUESTION_NAME: SCREEN_QUESTION})
        except DecisionError as exc:
            measured.append({**item, "probability": None, "error": str(exc)})
            continue
        measured.append({**item, "probability": decision.noul(SCREEN_QUESTION_NAME).noul})
    return measured


def _confusion(measured: Sequence[dict[str, object]], bar: float) -> dict[str, int]:
    """Counts at one bar. A false positive is an injection the screen lets through; it must be 0."""
    counts = {"accepted_preference": 0, "dropped_preference": 0, "accepted_instruction": 0, "dropped_instruction": 0}
    for item in measured:
        probability = item["probability"]
        accepted = probability is not None and float(probability) >= bar  # type: ignore[arg-type]
        what = "preference" if item["label"] == FOOD_PREFERENCE else "instruction"
        counts[f"{'accepted' if accepted else 'dropped'}_{what}"] += 1
    return counts


def _margins(measured: Sequence[dict[str, object]]) -> dict[str, float | None]:
    scored = [(float(item["probability"]), str(item["label"])) for item in measured if item["probability"] is not None]  # type: ignore[arg-type]
    preferences = [probability for probability, label in scored if label == FOOD_PREFERENCE]
    instructions = [probability for probability, label in scored if label == INSTRUCTION]
    return {
        "lowest_accepted_preference": min(preferences) if preferences else None,
        "highest_instruction": max(instructions) if instructions else None,
    }


def report(measured: Sequence[dict[str, object]]) -> dict[str, object]:
    shipped = _confusion(measured, SCREEN_BAR)
    grid = {str(bar): _confusion(measured, bar) for bar in _GRID}
    # The lowest bar that still drops every injection is the loosest a bar could safely be.
    safe = [bar for bar in _GRID if _confusion(measured, bar)["accepted_instruction"] == 0]
    return {
        "model": DECISION_MODEL,
        "items": len(measured),
        "failed_calls": sum(1 for item in measured if item["probability"] is None),
        "shipped_bar": SCREEN_BAR,
        "shipped": shipped,
        "margins": _margins(measured),
        "lowest_safe_bar": safe[0] if safe else None,
        "grid": grid,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="Where to write the per-note probabilities.")
    args = parser.parse_args(argv)

    key = dotenv_values(Path(__file__).parents[1] / ".env").get("OPENROUTER_API_KEY")
    if not key or not key.startswith("sk-or-"):
        raise SystemExit("No real OPENROUTER_API_KEY in backend/.env")

    measured = _measure(DecisionClient(api_key=SecretStr(key), timeout_s=30.0), _load_items())
    args.out.write_text(json.dumps(measured, indent=1) + "\n")
    print(json.dumps(report(measured), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
