"""Offline regressions for the live dietary validation check (`tests/integration/test_dietary_sample_live.py`).

The live check is the gate that says a model's answers still separate the labelled samples at the
active dietary cutoffs. These tests run it with its model, evaluator and fixtures patched, so they
make no network call: they pin which model it asks, which calibration it scores against, and which
mistakes it refuses to tolerate.
"""

from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr

from glean.decisions import DEFAULT_MODEL, DecisionClient, DecisionModel, Usage
from glean.meal_plan.dietary_decisions import (
    CALIBRATED_DIETARY,
    DIETARY_FLAGS,
    PEANUT_FREE,
    TREE_NUT_FREE,
)
from glean.meal_plan.dietary_evaluation import EvaluationReport, LabelledSample, SampleScore
from tests.integration import test_dietary_sample_live as live

ALTERNATE = replace(
    CALIBRATED_DIETARY,
    model=DecisionModel("another-model/decider-1:free", served=("another-model/decider-1",)),
)
GLUTEN_FREE = "gluten-free"
SAMPLE = LabelledSample(id="sample-1", title="Toast", ingredients=["bread"], violates={GLUTEN_FREE: False})


def _report(*scores: SampleScore, calibration=CALIBRATED_DIETARY, failures: tuple[str, ...] = ()) -> EvaluationReport:
    return EvaluationReport(
        requested_model=calibration.model.request,
        served_models={},
        samples=len(scores),
        scores=scores,
        failures=failures,
        usage=Usage(input_tokens=0, output_tokens=0, cost=0.0),
        flags=DIETARY_FLAGS,
        calibration=calibration,
    )


def _score(flag: str, *, violates: bool, probability: float, excluded: bool) -> SampleScore:
    return SampleScore(
        sample_id=SAMPLE.id, flag=flag, violates=violates, probability=probability, threshold=0.5, excluded=excluded
    )


def _run_live_with_patched_io(monkeypatch: pytest.MonkeyPatch, calibration) -> dict[str, object]:
    """Run the live check end to end with its client, evaluator and fixtures replaced by fakes."""
    seen: dict[str, object] = {}

    def fake_evaluate(client, samples, *, calibration):  # stands in for the real scorer
        seen.update(client=client, samples=list(samples), calibration=calibration)
        return _report(calibration=calibration)

    monkeypatch.setattr(live, "CALIBRATED_DIETARY", calibration)
    monkeypatch.setattr(live, "DecisionClient", recording_client)
    monkeypatch.setattr(live, "evaluate_dietary_model", fake_evaluate)
    monkeypatch.setattr(live, "load_labelled_samples", lambda paths: [SAMPLE])

    live.test_live_model_separates_the_labelled_samples_at_the_chosen_thresholds(SecretStr("sk-or-test"))
    return seen


def recording_client(**kwargs):  # mimics the client the routine builds
    """A stand-in carrying the real default, so a missing `model=` shows up as the wrong model."""
    return SimpleNamespace(**{**kwargs, "model": kwargs.get("model", DEFAULT_MODEL)})


def test_the_live_check_asks_the_model_the_active_calibration_names(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _run_live_with_patched_io(monkeypatch, ALTERNATE)

    assert seen["client"].model == ALTERNATE.model  # type: ignore[attr-defined]
    assert seen["calibration"] is ALTERNATE


def test_the_live_check_defaults_to_the_shipped_calibration(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _run_live_with_patched_io(monkeypatch, CALIBRATED_DIETARY)

    assert seen["client"].model == CALIBRATED_DIETARY.model  # type: ignore[attr-defined]
    assert seen["calibration"] is CALIBRATED_DIETARY


def test_a_clean_labelled_gluten_exclusion_fails_even_when_the_profile_sets_a_gluten_cutoff() -> None:
    policy = replace(CALIBRATED_DIETARY, thresholds={**CALIBRATED_DIETARY.thresholds, GLUTEN_FREE: 0.5})
    report = _report(_score(GLUTEN_FREE, violates=False, probability=0.6, excluded=True), calibration=policy)

    assert GLUTEN_FREE in policy.thresholds
    assert live.threshold_regressions(report) == [f"wrongly excluded {SAMPLE.id}/{GLUTEN_FREE}=0.6"]


def test_the_live_check_fails_on_a_clean_labelled_gluten_exclusion_at_a_custom_cutoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole routine, over a mock transport: that mistake must reach its assertion."""
    policy = replace(CALIBRATED_DIETARY, thresholds={**CALIBRATED_DIETARY.thresholds, GLUTEN_FREE: 0.5})

    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "gen-dec-test",
                "model": policy.model.request,
                "provider": "TypeSafe",
                "answers": {name: {"type": "noul", "noul": 0.6} for name in body["questions"]},
                "usage": {"input_tokens": 1, "output_tokens": 1, "cost": 0.0},
            },
        )

    def mock_client(**kwargs):  # the routine's client, over a mock transport
        return DecisionClient(api_key=kwargs["api_key"], model=kwargs["model"], transport=httpx.MockTransport(handle))

    monkeypatch.setattr(live, "CALIBRATED_DIETARY", policy)
    monkeypatch.setattr(live, "DecisionClient", mock_client)
    monkeypatch.setattr(live, "load_labelled_samples", lambda paths: [SAMPLE])

    with pytest.raises(AssertionError, match=f"wrongly excluded {SAMPLE.id}/{GLUTEN_FREE}"):
        live.test_live_model_separates_the_labelled_samples_at_the_chosen_thresholds(SecretStr("sk-or-test"))


@pytest.mark.parametrize("flag", [TREE_NUT_FREE, PEANUT_FREE])
def test_a_clean_labelled_nut_lookalike_is_still_tolerated(flag: str) -> None:
    report = _report(_score(flag, violates=False, probability=0.6, excluded=True))

    assert live.threshold_regressions(report) == []


@pytest.mark.parametrize("flag", [*DIETARY_FLAGS])
def test_a_missed_violation_fails_for_every_flag_including_the_allergy_flags(flag: str) -> None:
    report = _report(_score(flag, violates=True, probability=0.1, excluded=False))

    assert live.threshold_regressions(report) == [f"missed {SAMPLE.id}/{flag}=0.1"]
