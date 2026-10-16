from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))

from judge_study.decision_judge import DecisionJudge
from judge_study.features import FEATURES
from judge_study.results import OutputItem
from tests.integration.evals.judges import rubrics

from glean.decisions import DecisionClient, DecisionHTTPError

MEAL_PLAN_INPUTS = {
    "pantry_summary": "- rice: 800g",
    "dietary_flags": ["vegan"],
    "title": "Rice bowl",
    "reason": "Uses the rice before it expires",
}


def _answer(probabilities: list[float], score: float, confidence: float) -> dict[str, Any]:
    return {
        "model": "typesafe/jev-1.14-20261014",
        "id": "gen-dec-1",
        "provider": "TypeSafe",
        "answers": {
            "quality": {
                "type": "score",
                "score": score,
                "probabilities": {str(level): p for level, p in enumerate(probabilities)},
                "confidence": confidence,
            }
        },
        "usage": {"input_tokens": 400, "output_tokens": 50, "cost": 1.7e-5},
    }


def _judge(handler: Any, clock: Any = None) -> DecisionJudge:
    client = DecisionClient(api_key=SecretStr("sk-or-test"), transport=httpx.MockTransport(handler))
    return DecisionJudge(client, clock=clock or iter([10.0, 10.4]).__next__)


def _item(feature: str = "meal_plan", inputs: dict | None = None) -> OutputItem:
    return OutputItem(
        item_id=f"{feature}/0/0", feature=feature, input={}, output={}, judge_inputs=inputs or MEAL_PLAN_INPUTS
    )


class TestDecisionJudge:
    def test_the_most_probable_level_is_the_one_to_five_score(self) -> None:
        body = _answer([0.0, 0.05, 0.1, 0.25, 0.6], score=3.35, confidence=0.6)

        judgement = _judge(lambda _: httpx.Response(200, json=body)).judge(_item(), repeat=2)

        assert (judgement.judge, judgement.repeat, judgement.score) == ("decision", 2, 5)

    def test_it_keeps_the_weighted_score_confidence_probabilities_cost_and_snapshot(self) -> None:
        body = _answer([0.0, 0.0, 0.1, 0.7, 0.2], score=3.1, confidence=0.7)

        judgement = _judge(lambda _: httpx.Response(200, json=body)).judge(_item(), repeat=1)

        assert judgement.weighted_score == pytest.approx(4.1)
        assert judgement.confidence == 0.7
        assert judgement.probabilities == [0.0, 0.0, 0.1, 0.7, 0.2]
        assert judgement.cost_usd == pytest.approx(1.7e-5)
        assert judgement.model == "typesafe/jev-1.14-20261014"
        assert judgement.score == 4

    def test_latency_is_the_time_the_call_took(self) -> None:
        body = _answer([0, 0, 0, 0, 1], score=4, confidence=1)

        judgement = _judge(lambda _: httpx.Response(200, json=body), clock=iter([5.0, 5.75]).__next__).judge(_item(), 1)

        assert judgement.latency_s == pytest.approx(0.75)

    def test_it_asks_the_rubric_as_five_ordered_criteria_about_the_text_the_llm_judge_reads(self) -> None:
        sent: list[dict] = []

        def handler(request: httpx.Request) -> httpx.Response:
            sent.append(json.loads(request.content))
            return httpx.Response(200, json=_answer([0, 0, 0, 0, 1], score=4, confidence=1))

        _judge(handler).judge(_item(), repeat=1)

        (payload,) = sent
        question = payload["questions"]["quality"]
        assert question["type"] == "score"
        assert len(question["criteria"]) == 5
        assert question["criteria"][0].startswith("Bad — violates dietary flags")
        assert payload["state"] == {"evaluation": rubrics.meal_plan_prompt(**MEAL_PLAN_INPUTS)}

    def test_a_failed_call_surfaces_as_the_clients_typed_error(self) -> None:
        with pytest.raises(DecisionHTTPError):
            _judge(lambda _: httpx.Response(500, text="boom")).judge(_item(), repeat=1)

    def test_every_feature_has_a_rubric_that_parses_to_a_scale(self) -> None:
        assert set(FEATURES) == {
            "receipt_scan",
            "meal_plan",
            "recipe_import",
            "pantry_description",
            "shopping_list_description",
        }
        assert all(len(spec.question.criteria) == 5 for spec in FEATURES.values())
