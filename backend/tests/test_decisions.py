from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

import httpx
import pytest
from langsmith import Client, tracing_context
from pydantic import Field, SecretStr, TypeAdapter, ValidationError

from glean.decisions import (
    DECISIONS_URL,
    ChoiceQuestion,
    DecisionClient,
    DecisionError,
    DecisionHTTPError,
    DecisionResponseError,
    DecisionTimeoutError,
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


class TestMalformedAnswers:
    def test_a_missing_answer_names_the_question(self) -> None:
        body = _recorded_response()
        del body["answers"]["quality"]
        state, questions = _probe()

        with pytest.raises(DecisionResponseError, match="quality"):
            _client(_respond_with(body)).decide(state, questions)

    def test_a_choice_that_was_not_offered_is_rejected(self) -> None:
        body = _recorded_response()
        body["answers"]["ingredient_group"]["choice"] = "frozen"
        state, questions = _probe()

        with pytest.raises(DecisionResponseError, match="frozen"):
            _client(_respond_with(body)).decide(state, questions)

    def test_an_answer_of_the_wrong_shape_is_rejected(self) -> None:
        body = _recorded_response()
        body["answers"]["contains_nuts"] = {"unexpected": True}
        state, questions = _probe()

        with pytest.raises(DecisionResponseError, match="contains_nuts"):
            _client(_respond_with(body)).decide(state, questions)

    def test_an_answer_from_another_model_version_is_rejected(self) -> None:
        body = _recorded_response()
        body["model"] = "typesafe/jev-1.14"
        state, questions = _probe()

        with pytest.raises(DecisionResponseError, match="pinned"):
            _client(_respond_with(body)).decide(state, questions)

    def test_a_non_json_body_is_rejected(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<html>Bad gateway</html>")

        state, questions = _probe()
        with pytest.raises(DecisionResponseError, match="JSON"):
            _client(handler).decide(state, questions)


class TestTransportFailures:
    def test_an_http_error_carries_its_status_and_never_the_api_key(self) -> None:
        state, questions = _probe()
        rate_limited = _respond_with({"error": {"message": "Rate limited", "code": 429}}, status=429)

        with pytest.raises(DecisionHTTPError) as caught:
            _client(rate_limited).decide(state, questions)

        assert caught.value.status_code == 429
        assert "Rate limited" in str(caught.value)
        assert API_KEY not in str(caught.value)

    def test_a_timeout_is_a_decision_timeout_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timed out", request=request)

        state, questions = _probe()
        with pytest.raises(DecisionTimeoutError):
            _client(handler).decide(state, questions)

    def test_a_connection_failure_is_a_decision_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        state, questions = _probe()
        with pytest.raises(DecisionError, match="connection refused"):
            _client(handler).decide(state, questions)


def _exception_chain_text(exc: BaseException | None) -> str:
    parts: list[str] = []
    while exc is not None:
        parts.append(f"{type(exc).__name__}: {exc}")
        exc = exc.__cause__ or exc.__context__
    return "\n".join(parts)


class TestCredentialsNeverLeak:
    def test_a_key_reflected_in_an_error_body_is_scrubbed_from_the_exception_chain(self) -> None:
        reflected = {"error": {"message": f"Invalid credential: {API_KEY}"}}
        state, questions = _probe()

        with pytest.raises(DecisionHTTPError) as caught:
            _client(_respond_with(reflected, status=401)).decide(state, questions)

        assert caught.value.status_code == 401
        assert "Invalid credential" in str(caught.value)
        assert API_KEY not in _exception_chain_text(caught.value)

    def test_a_key_reflected_in_a_malformed_answer_is_scrubbed_from_the_exception_chain(self) -> None:
        body = _recorded_response()
        body["answers"]["contains_nuts"] = {"noul": API_KEY}
        state, questions = _probe()

        with pytest.raises(DecisionResponseError) as caught:
            _client(_respond_with(body)).decide(state, questions)

        assert API_KEY not in _exception_chain_text(caught.value)

    def test_a_key_reflected_in_the_traced_run_error_is_scrubbed(self) -> None:
        runs: list[Any] = []

        class RecordingClient(Client):
            def create_run(self, **kwargs: Any) -> None:
                runs.append(kwargs)

            def update_run(self, run_id: Any, **kwargs: Any) -> None:
                runs.append(kwargs)

        reflected = {"error": {"message": f"Invalid credential: {API_KEY}"}}
        state, questions = _probe()
        client = RecordingClient(api_key="ls-test", api_url="http://localhost:1", auto_batch_tracing=False)

        with tracing_context(enabled=True, client=client), pytest.raises(DecisionHTTPError):
            _client(_respond_with(reflected, status=401)).decide(state, questions)

        assert any(run.get("error") for run in runs)
        assert API_KEY not in json.dumps(runs, default=str)
