"""The dietary thresholds, checked against real Jev answers to the labelled sample (#125).

`tests/fixtures/jev/dietary_sample.json` labels which flags each recipe violates: every
row of the issue's table, the allowed cases (coconut milk, nutmeg, parmesan under
vegetarian, gluten-free oats), held-out items the criteria don't name, and ordinary
recipes. `dietary_sample_measured.json` holds the probabilities live Jev gave on
2026-10-15 (re-record with `tests/integration/test_dietary_sample_live.py`).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from glean.meal_plan.dietary_decisions import NUT_FREE, NUT_FREE_THRESHOLD, PREFERENCE_THRESHOLD

FIXTURES = Path(__file__).parents[1] / "fixtures" / "jev"
ROWS = json.loads((FIXTURES / "dietary_sample.json").read_text())["rows"]
MEASURED = json.loads((FIXTURES / "dietary_sample_measured.json").read_text())["probabilities"]

LABELLED = [(row["id"], flag, violates) for row in ROWS for flag, violates in row["violates"].items()]


def _threshold(flag: str) -> float:
    return NUT_FREE_THRESHOLD if flag == NUT_FREE else PREFERENCE_THRESHOLD


@pytest.mark.parametrize(("row_id", "flag"), [(r, f) for r, f, violates in LABELLED if violates])
def test_every_recipe_that_breaks_a_flag_is_excluded(row_id: str, flag: str) -> None:
    assert MEASURED[row_id][flag] >= _threshold(flag)


@pytest.mark.parametrize(("row_id", "flag"), [(r, f) for r, f, violates in LABELLED if not violates and f != NUT_FREE])
def test_every_recipe_that_is_fine_for_a_preference_flag_is_kept(row_id: str, flag: str) -> None:
    assert MEASURED[row_id][flag] < _threshold(flag)


def test_nut_free_keeps_coconut_milk_and_nutmeg_and_most_ordinary_recipes() -> None:
    clean = [
        (row_id, MEASURED[row_id][NUT_FREE]) for row_id, flag, violates in LABELLED if flag == NUT_FREE and not violates
    ]
    excluded = {row_id for row_id, probability in clean if probability >= NUT_FREE_THRESHOLD}

    # The allergy threshold is strict, so tahini and hummus (nut-butter lookalikes) may be lost, but little else.
    assert not {"allowed-coconut-milk", "allowed-nutmeg", "allowed-butternut"} & excluded
    assert len(excluded) <= 2


def test_nut_free_is_stricter_than_preference_flags_and_both_sit_clear_of_the_measurements() -> None:
    assert NUT_FREE_THRESHOLD < PREFERENCE_THRESHOLD
    violating_nut = [MEASURED[r][f] for r, f, v in LABELLED if v and f == NUT_FREE]
    assert min(violating_nut) / 2 > NUT_FREE_THRESHOLD  # lots of headroom: the allergy must never sit on the edge
