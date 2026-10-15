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

        assert decision.noul("contains_nuts").noul == 0.63
        group = decision.choice("ingredient_group")
        assert (group.choice, group.confidence) == ("condiments", 1)
        assert group.probabilities == {"condiments": 1, "fresh_herbs": 0, "dairy": 0, "none": 0}
        quality = decision.score("quality")
        assert (quality.score, quality.confidence) == (3.69, 0.75)
        assert quality.probabilities == {0: 0, 1: 0, 2: 0, 3: 0.3, 4: 0.7}
        assert decision.model == "typesafe/jev-1.13-20260917"
        assert (decision.usage.input_tokens, decision.usage.output_tokens) == (513, 84)
        assert decision.usage.cost == 2.1546e-05

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

    @pytest.mark.parametrize(
        "model",
        [
            "typesafe/jev-1.14",
            "typesafe/jev-1.130-20260917",
            "typesafe/jev-1.13-latest",
            "typesafe/jev-1.13-2026091",
            "other-provider/jev-1.13-20260917",
        ],
    )
    def test_an_answer_from_another_model_version_is_rejected(self, model: str) -> None:
        body = _recorded_response()
        body["model"] = model
        state, questions = _probe()

        with pytest.raises(DecisionResponseError, match="pinned"):
            _client(_respond_with(body)).decide(state, questions)

    @pytest.mark.parametrize("model", ["typesafe/jev-1.13", "typesafe/jev-1.13-20261231"])
    def test_the_pinned_model_and_any_dated_snapshot_of_it_are_accepted(self, model: str) -> None:
        body = _recorded_response()
        body["model"] = model
        state, questions = _probe()

        assert _client(_respond_with(body)).decide(state, questions).model == model

    def test_a_non_json_body_is_rejected(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<html>Bad gateway</html>")

        state, questions = _probe()
        with pytest.raises(DecisionResponseError, match="JSON"):
            _client(handler).decide(state, questions)


class TestSemanticallyInvalidAnswers:
    @pytest.mark.parametrize(
        ("question", "mutate"),
        [
            ("contains_nuts", lambda a: a.update(type="choice")),
            ("ingredient_group", lambda a: a.update(type="score")),
            ("quality", lambda a: a.update(type="noul")),
            ("contains_nuts", lambda a: a.update(noul=1.5)),
            ("contains_nuts", lambda a: a.update(noul=-0.1)),
            ("ingredient_group", lambda a: a.update(confidence=8)),
            ("ingredient_group", lambda a: a.update(confidence=-1)),
            ("quality", lambda a: a.update(confidence=1.2)),
            ("ingredient_group", lambda a: a["probabilities"].update(condiments=-2)),
            ("quality", lambda a: a["probabilities"].update({"3": 1.5})),
            ("ingredient_group", lambda a: a["probabilities"].update({"not-offered": 0})),
            ("quality", lambda a: a["probabilities"].update({"7": 0})),
            ("quality", lambda a: a.update(score=999)),
            ("quality", lambda a: a.update(score=-0.5)),
            ("ingredient_group", lambda a: a["probabilities"].update(condiments=0.5)),
            ("quality", lambda a: a["probabilities"].update({"4": 0.1})),
        ],
    )
    def test_an_answer_that_breaks_the_question_contract_is_rejected_naming_the_question(
        self, question: str, mutate: Callable[[dict[str, Any]], object]
    ) -> None:
        body = _recorded_response()
        mutate(body["answers"][question])
        state, questions = _probe()

        with pytest.raises(DecisionResponseError, match=question):
            _client(_respond_with(body)).decide(state, questions)

    @pytest.mark.parametrize("literal", ["NaN", "Infinity"])
    def test_non_finite_numbers_are_rejected(self, literal: str) -> None:
        recorded = json.dumps(_recorded_response())
        raw = recorded.replace('"noul": 0.63', f'"noul": {literal}')
        assert literal in raw

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=raw, headers={"content-type": "application/json"})

        state, questions = _probe()
        with pytest.raises(DecisionResponseError, match="contains_nuts"):
            _client(handler).decide(state, questions)

    def test_probabilities_that_sum_to_one_within_tolerance_are_accepted(self) -> None:
        body = _recorded_response()
        body["answers"]["quality"]["probabilities"]["4"] = 0.69  # sums to 0.99
        state, questions = _probe()

        decision = _client(_respond_with(body)).decide(state, questions)

        assert decision.score("quality").probabilities[4] == 0.69


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
