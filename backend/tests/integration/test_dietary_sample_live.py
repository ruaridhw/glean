"""Re-check the dietary thresholds against the live decision model. Needs a real OPENROUTER_API_KEY in backend/.env.

Run with: uv run pytest tests/integration/test_dietary_sample_live.py -v --no-cov
Costs about $0.02. If it fails, the model's answers moved: re-measure before changing the thresholds.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from glean.decisions import DecisionClient
from glean.meal_plan.dietary_decisions import (
    NUT_FREE,
    NUT_FREE_THRESHOLD,
    PREFERENCE_THRESHOLD,
    dietary_questions,
)

if TYPE_CHECKING:
    from pydantic import SecretStr

pytestmark = pytest.mark.integration

_FIXTURES = Path(__file__).parents[1] / "fixtures" / "decisions"
_ROWS = [
    row
    for name in ("dietary_sample", "dietary_regex_coverage")
    for row in json.loads((_FIXTURES / f"{name}.json").read_text())["rows"]
]


def test_live_model_separates_the_labelled_samples_at_the_chosen_thresholds(openrouter_api_key: SecretStr) -> None:
    client = DecisionClient(api_key=openrouter_api_key, timeout_s=60.0)
    missed: list[str] = []
    wrongly_excluded: list[str] = []
    for row in _ROWS:
        decision = client.decide({"recipe_title": row["title"], "ingredients": row["ingredients"]}, dietary_questions())
        for flag, violates in row["violates"].items():
            probability = decision.noul(flag).noul
            excluded = probability >= (NUT_FREE_THRESHOLD if flag == NUT_FREE else PREFERENCE_THRESHOLD)
            if violates and not excluded:
                missed.append(f"{row['id']}/{flag}={probability}")
            if not violates and excluded and flag != NUT_FREE:
                wrongly_excluded.append(f"{row['id']}/{flag}={probability}")

    assert missed == []
    assert wrongly_excluded == []
