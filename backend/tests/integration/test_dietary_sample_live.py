"""Re-check the dietary thresholds against the live decision model. Needs a real OPENROUTER_API_KEY in backend/.env.

Run with: uv run pytest tests/integration/test_dietary_sample_live.py -v --no-cov
Costs about $0.02. If it fails, the model's answers moved: re-measure before changing the thresholds.
Scores through `evaluate_dietary_model`, the same path `scripts/evaluate_dietary_model.py` uses, and asks the
model the dietary calibration names, so it validates the policy in use rather than the package default.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from glean.decisions import DecisionClient
from glean.meal_plan.dietary_decisions import CALIBRATED_DIETARY, PEANUT_FREE, TREE_NUT_FREE
from glean.meal_plan.dietary_evaluation import evaluate_dietary_model, load_labelled_samples

if TYPE_CHECKING:
    from pydantic import SecretStr

    from glean.meal_plan.dietary_evaluation import EvaluationReport

pytestmark = pytest.mark.integration

_FIXTURES = Path(__file__).parents[1] / "fixtures" / "decisions"
_FILES = ("dietary_sample", "dietary_regex_coverage")

# The nut flags deliberately drop a few clean-labelled lookalikes (see the calibration's evidence). Named
# explicitly, not by which flags carry a threshold: a custom cutoff must not turn a preference into an allergy.
ALLERGY_FLAGS = frozenset({TREE_NUT_FREE, PEANUT_FREE})


def threshold_regressions(report: EvaluationReport) -> list[str]:
    """What the labelled samples say is wrong at these cutoffs: any missed violation, and any clean-labelled
    recipe a non-allergy flag excludes. Allergy flags tolerate those few lookalikes on purpose."""
    missed = [
        f"missed {score.sample_id}/{flag}={score.probability}"
        for flag, summary in report.summaries().items()
        for score in summary.missed
    ]
    wrongly_excluded = [
        f"wrongly excluded {score.sample_id}/{flag}={score.probability}"
        for flag, summary in report.summaries().items()
        if flag not in ALLERGY_FLAGS
        for score in summary.wrongly_excluded
    ]
    return missed + wrongly_excluded


def test_live_model_separates_the_labelled_samples_at_the_chosen_thresholds(openrouter_api_key: SecretStr) -> None:
    report = evaluate_dietary_model(
        DecisionClient(api_key=openrouter_api_key, model=CALIBRATED_DIETARY.model, timeout_s=60.0),
        load_labelled_samples([_FIXTURES / f"{name}.json" for name in _FILES]),
        calibration=CALIBRATED_DIETARY,
    )

    assert report.failures == ()
    assert threshold_regressions(report) == []
