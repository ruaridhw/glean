from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

import httpx
import pytest
from pydantic import Field, SecretStr, TypeAdapter, ValidationError

from glean.decisions import (
    DECISIONS_URL,
    ChoiceQuestion,
    DecisionClient,
    DecisionResponseError,
    NoulQuestion,
    ScoreQuestion,
)

if TYPE_CHECKING:
    from collections.abc import Callable

FIXTURES = Path(__file__).parent / "fixtures" / "jev"
API_KEY = "sk-or-test-key"
_QUESTION_SET = TypeAdapter(
    dict[str, Annotated[ChoiceQuestion | NoulQuestion | ScoreQuestion, Field(discriminator="type")]]
)

type Handler = Callable[[httpx.Request], httpx.Response]


def _probe_request() -> dict[str, Any]:
    return json.loads((FIXTURES / "probe_request.json").read_text())


def _probe() -> tuple[dict[str, Any], dict[str, ChoiceQuestion | NoulQuestion | ScoreQuestion]]:
    request = _probe_request()
    return request["state"], _QUESTION_SET.validate_python(request["questions"])


def _recorded_response() -> dict[str, Any]:
    return json.loads((FIXTURES / "probe_response.json").read_text())


def _client(handler: Handler) -> DecisionClient:
    return DecisionClient(api_key=SecretStr(API_KEY), transport=httpx.MockTransport(handler))


def _respond_with(body: Any, status: int = 200) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=body)

    return handler


class TestRequest:
    def test_posts_the_pinned_model_state_and_questions_in_the_documented_wire_format(self) -> None:
        sent: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            sent.append(request)
            return httpx.Response(200, json=_recorded_response())

        state, questions = _probe()
        _client(handler).decide(state, questions)

        (request,) = sent
        assert str(request.url) == DECISIONS_URL
        assert request.headers["Authorization"] == f"Bearer {API_KEY}"
        assert json.loads(request.content) == _probe_request()

    def test_an_empty_question_set_is_rejected_without_calling_jev(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError(f"unexpected request to {request.url}")

        with pytest.raises(ValueError, match="at least one question"):
            _client(handler).decide({"recipe_title": "Toast"}, {})


class TestAnswers:
    def test_parses_each_answer_type_from_the_recorded_response(self) -> None:
        state, questions = _probe()

        decision = _client(_respond_with(_recorded_response())).decide(state, questions)

        assert 0.0 <= decision.noul("contains_nuts").noul <= 1.0
        group = decision.choice("ingredient_group")
        assert group.choice in questions["ingredient_group"].criteria
        assert sum(group.probabilities.values()) == pytest.approx(1.0, abs=0.01)
        quality = decision.score("quality")
        assert 0.0 <= quality.score <= len(questions["quality"].criteria) - 1
        assert "jev-1.13" in decision.model
        assert decision.usage.cost > 0

    def test_asking_for_the_wrong_answer_type_names_the_question(self) -> None:
        state, questions = _probe()
        decision = _client(_respond_with(_recorded_response())).decide(state, questions)

        with pytest.raises(DecisionResponseError, match="contains_nuts"):
            decision.choice("contains_nuts")


class TestQuestions:
    def test_a_choice_needs_at_least_two_options(self) -> None:
        with pytest.raises(ValidationError):
            ChoiceQuestion(instructions="Pick one", criteria={"only": "The only option"})

    def test_a_score_needs_at_least_two_levels(self) -> None:
        with pytest.raises(ValidationError):
            ScoreQuestion(instructions="Rate it", criteria=["Fine"])
