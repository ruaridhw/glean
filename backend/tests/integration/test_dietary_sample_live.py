"""Re-check the dietary thresholds against the live decision model. Needs a real OPENROUTER_API_KEY in backend/.env.

Run with: uv run pytest tests/integration/test_dietary_sample_live.py -v --no-cov
Costs about $0.02. If it fails, the model's answers moved: re-measure before changing the thresholds.
Scores through `evaluate_dietary_model`, the same path `scripts/evaluate_dietary_model.py` uses, so the
labelled-sample loop is written once.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from glean.decisions import DecisionClient
from glean.meal_plan.dietary_decisions import THRESHOLDS
from glean.meal_plan.dietary_evaluation import evaluate_dietary_model, load_labelled_samples

if TYPE_CHECKING:
    from pydantic import SecretStr

pytestmark = pytest.mark.integration

_FIXTURES = Path(__file__).parents[1] / "fixtures" / "decisions"
_FILES = ("dietary_sample", "dietary_regex_coverage")


def test_live_model_separates_the_labelled_samples_at_the_chosen_thresholds(openrouter_api_key: SecretStr) -> None:
    report = evaluate_dietary_model(
        DecisionClient(api_key=openrouter_api_key, timeout_s=60.0),
        load_labelled_samples([_FIXTURES / f"{name}.json" for name in _FILES]),
    )

    summaries = report.summaries()
    missed = [
        f"{score.sample_id}/{flag}={score.probability}"
        for flag, summary in summaries.items()
        for score in summary.missed
    ]
    # Allergy flags deliberately drop a few clean-looking recipes; only preferences must stay clean here.
    wrongly_excluded = [
        f"{score.sample_id}/{flag}={score.probability}"
        for flag, summary in summaries.items()
        if flag not in THRESHOLDS
        for score in summary.wrongly_excluded
    ]

    assert report.failures == ()
    assert missed == []
    assert wrongly_excluded == []
