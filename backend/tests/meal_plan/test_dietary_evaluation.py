"""Read-only evaluation of a decision model against labelled dietary samples.

Seams: `evaluate_dietary_model` and the report it returns, with the decision API faked at the
HTTP boundary through a real `DecisionClient`. Ground truth here is the sample file's label, never
agreement with the calibrated model.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from pydantic import SecretStr

from glean.decisions import DecisionClient, DecisionModel
from glean.meal_plan.dietary_evaluation import (
    LabelledSample,
    evaluate_dietary_model,
    load_labelled_samples,
)

if TYPE_CHECKING:
    from collections.abc import Callable

CANDIDATE = DecisionModel("baseten/mammoth-1:free", served=("baseten/mammoth-1",))
SERVED = "baseten/mammoth-1-20261021"

SAMPLES = [
    LabelledSample(
        id="sample-nutty",
        title="Pesto Pasta",
        ingredients=["spaghetti", "basil pesto"],
        violates={"tree-nut-free": True, "peanut-free": False},
    ),
    LabelledSample(
        id="sample-plain",
        title="Tomato Pasta",
        ingredients=["spaghetti", "tomato"],
        violates={"tree-nut-free": False, "peanut-free": False},
    ),
]


class FakeDecisionApi:
    """Answers from a per-title table of probabilities, and records what it was asked."""

    def __init__(self, answers: dict[str, dict[str, float]], *, fail_when: Callable[[dict], bool] | None = None):
        self.requests: list[dict] = []
        self._answers = answers
        self._fail_when = fail_when

    def client(self) -> DecisionClient:
        return DecisionClient(
            api_key=SecretStr("sk-or-test"), model=CANDIDATE, transport=httpx.MockTransport(self._handle)
        )

    def _handle(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.requests.append(body)
        if self._fail_when is not None and self._fail_when(body):
            return httpx.Response(500, text="boom")
        probabilities = self._answers[body["state"]["recipe_title"]]
        return httpx.Response(
            200,
            json={
                "id": "gen-dec-test",
                "model": SERVED,
                "provider": "BaseTen",
                "answers": {name: {"type": "noul", "noul": probabilities[name]} for name in body["questions"]},
                "usage": {"input_tokens": 10, "output_tokens": 2, "cost": 0.00001},
            },
        )


def test_labelled_samples_load_from_the_neutral_fixture_files() -> None:
    samples = load_labelled_samples([_fixtures() / "dietary_sample.json"])

    assert len(samples) == 63
    assert all(sample.violates for sample in samples)


def test_known_outcomes_are_counted_per_flag_at_the_reference_thresholds() -> None:
    api = FakeDecisionApi(
        {
            "Pesto Pasta": {"tree-nut-free": 0.9, "peanut-free": 0.01},
            "Tomato Pasta": {"tree-nut-free": 0.4, "peanut-free": 0.01},
        }
    )

    report = evaluate_dietary_model(api.client(), SAMPLES, flags=("tree-nut-free", "peanut-free"))
    summaries = report.summaries()

    tree = summaries["tree-nut-free"]
    assert (tree.threshold, tree.violations, tree.clean) == (0.3, 1, 1)
    assert tree.missed == ()
    assert [score.sample_id for score in tree.wrongly_excluded] == ["sample-plain"]
    peanut = summaries["peanut-free"]
    assert (peanut.missed, peanut.wrongly_excluded) == ((), ())
    assert (report.samples, report.failures) == (2, ())
    assert report.served_models == {SERVED: 2}
    assert (report.usage.input_tokens, report.usage.output_tokens, report.usage.cost) == (20, 4, 0.00002)


def test_a_missed_violation_is_reported_with_its_probability_and_label() -> None:
    api = FakeDecisionApi(
        {
            "Pesto Pasta": {"tree-nut-free": 0.1, "peanut-free": 0.01},
            "Tomato Pasta": {"tree-nut-free": 0.01, "peanut-free": 0.01},
        }
    )

    report = evaluate_dietary_model(api.client(), SAMPLES, flags=("tree-nut-free", "peanut-free"))

    (missed,) = report.summaries()["tree-nut-free"].missed
    assert (missed.sample_id, missed.violates, missed.probability, missed.excluded) == (
        "sample-nutty",
        True,
        0.1,
        False,
    )


def test_a_request_failure_is_reported_and_the_other_samples_are_still_scored() -> None:
    api = FakeDecisionApi(
        {"Pesto Pasta": {}, "Tomato Pasta": {"tree-nut-free": 0.01, "peanut-free": 0.01}},
        fail_when=lambda body: body["state"]["recipe_title"] == "Pesto Pasta",
    )

    report = evaluate_dietary_model(api.client(), SAMPLES, flags=("tree-nut-free",))

    assert report.samples == 1
    assert len(report.failures) == 1
    assert "sample-nutty" in report.failures[0]
    assert report.summaries()["tree-nut-free"].violations == 0


def test_the_report_says_the_cutoffs_are_a_reference_and_what_is_still_unproven() -> None:
    api = FakeDecisionApi(
        {
            "Pesto Pasta": {"tree-nut-free": 0.9, "peanut-free": 0.01},
            "Tomato Pasta": {"tree-nut-free": 0.01, "peanut-free": 0.01},
        }
    )

    rendered = evaluate_dietary_model(api.client(), SAMPLES, flags=("tree-nut-free", "peanut-free")).render()

    assert CANDIDATE.request in rendered
    assert SERVED in rendered
    assert "not a calibration" in rendered.casefold()
    assert "tree-nut-free" in rendered
    assert "0.3" in rendered


def test_evaluating_a_model_cannot_write_the_stored_dietary_decisions() -> None:
    """Catches a later change that hands the evaluation a store to write; misses a module-level global store."""
    assert not {"store", "corpus", "blob_store", "sink"} & set(inspect.signature(evaluate_dietary_model).parameters)


def _fixtures() -> Path:
    return Path(__file__).parents[1] / "fixtures" / "decisions"
