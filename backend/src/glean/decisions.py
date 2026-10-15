"""Client for Jev, TypeSafe's decision model, on OpenRouter's alpha decisions endpoint.

This module is the only code that calls the endpoint. Features that need a typed
decision (#123 normalisation, #125 dietary checks, #124 eval judging) go through
DecisionClient, so a change to the alpha API touches one place.
"""

from __future__ import annotations

import json
import math
import re
from typing import TYPE_CHECKING, Annotated, Any, Literal, cast

import httpx
from langsmith import traceable
from pydantic import BaseModel, ConfigDict, Field, ValidationError

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

    from pydantic import SecretStr

# Pinned, never "-latest": callers set thresholds on this snapshot's probabilities,
# and those thresholds don't carry over to another version.
JEV_MODEL = "typesafe/jev-1.13"
DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"


class DecisionError(Exception):
    """A Jev decision couldn't be obtained."""


class DecisionTimeoutError(DecisionError):
    """Jev didn't answer within the client's timeout."""


class DecisionHTTPError(DecisionError):
    """The decisions endpoint answered with a non-2xx status."""

    def __init__(self, status_code: int, body: str) -> None:
        super().__init__(f"Jev decisions endpoint returned HTTP {status_code}: {body[:300]}")
        self.status_code = status_code


class DecisionResponseError(DecisionError):
    """Jev answered, but not with what was asked."""


class _Question(BaseModel):
    model_config = ConfigDict(frozen=True)

    instructions: str = Field(min_length=1)


class ChoiceQuestion(_Question):
    """Pick one option. `criteria` maps each option's name to what it means."""

    type: Literal["choice"] = "choice"
    criteria: dict[str, str] = Field(min_length=2)


class NoulCriteria(BaseModel):
    model_config = ConfigDict(frozen=True)

    true: str = Field(min_length=1)
    false: str = Field(min_length=1)


class NoulQuestion(_Question):
    """Yes or no. The answer is the probability of `true`."""

    type: Literal["noul"] = "noul"
    criteria: NoulCriteria


class ScoreQuestion(_Question):
    """Place the state on an ordered scale. `criteria[0]` is the lowest level."""

    type: Literal["score"] = "score"
    criteria: list[str] = Field(min_length=2)


Question = ChoiceQuestion | NoulQuestion | ScoreQuestion


type Probability = Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]

# A probability distribution from Jev must sum to 1, give or take rounding in the response.
_SUM_TOLERANCE = 0.02


class ChoiceAnswer(BaseModel):
    type: Literal["choice"]
    choice: str
    probabilities: dict[str, Probability]
    confidence: Probability


class NoulAnswer(BaseModel):
    type: Literal["noul"]
    noul: Probability  # probability of `true`


class ScoreAnswer(BaseModel):
    type: Literal["score"]
    score: float = Field(allow_inf_nan=False)  # probability-weighted position on the scale; 0 is criteria[0]
    probabilities: dict[int, Probability]
    confidence: Probability


Answer = ChoiceAnswer | NoulAnswer | ScoreAnswer


class Usage(BaseModel):
    input_tokens: int
    output_tokens: int
    cost: float  # USD, as reported by OpenRouter


class Decision(BaseModel):
    """One answered request. `model` is the dated snapshot that served it."""

    id: str
    model: str
    provider: str
    answers: dict[str, Answer]
    usage: Usage

    def choice(self, name: str) -> ChoiceAnswer:
        return self._answer(name, ChoiceAnswer)

    def noul(self, name: str) -> NoulAnswer:
        return self._answer(name, NoulAnswer)

    def score(self, name: str) -> ScoreAnswer:
        return self._answer(name, ScoreAnswer)

    def _answer[AnswerT: BaseModel](self, name: str, kind: type[AnswerT]) -> AnswerT:
        answer = self.answers.get(name)
        if not isinstance(answer, kind):
            raise DecisionResponseError(f"No {kind.__name__} for question {name!r}")
        return answer


# Jev reports the pinned model either as-is or as a dated snapshot of it (`<pinned>-YYYYMMDD`).
_PINNED_MODEL_REPLY = re.compile(rf"{re.escape(JEV_MODEL)}(-\d{{8}})?")


def _check_distribution(name: str, probabilities: Mapping[Any, float], allowed: Collection[Any]) -> None:
    if not set(probabilities) <= set(allowed):
        raise DecisionResponseError(f"Jev gave probabilities for unknown entries in {name!r}: {sorted(probabilities)}")
    if not math.isclose(sum(probabilities.values()), 1.0, rel_tol=0.0, abs_tol=_SUM_TOLERANCE + 1e-9):
        raise DecisionResponseError(f"Jev's probabilities for {name!r} don't sum to 1")


def _parse_answer(name: str, question: Question, raw: Any) -> Answer:
    try:
        if isinstance(question, ChoiceQuestion):
            choice = ChoiceAnswer.model_validate(raw)
            if choice.choice not in question.criteria:
                raise DecisionResponseError(f"Jev chose {choice.choice!r} for {name!r}, which wasn't offered")
            _check_distribution(name, choice.probabilities, question.criteria)
            return choice
        if isinstance(question, NoulQuestion):
            return NoulAnswer.model_validate(raw)
        score = ScoreAnswer.model_validate(raw)
        levels = len(question.criteria)
        if not 0 <= score.score <= levels - 1:
            raise DecisionResponseError(f"Jev scored {name!r} {score.score}, outside its {levels} levels")
        _check_distribution(name, score.probabilities, range(len(question.criteria)))
        return score
    except ValidationError as exc:
        raise DecisionResponseError(f"Unexpected answer shape for {name!r}: {exc}") from exc


def _parse(body: Any, questions: Mapping[str, Question]) -> Decision:
    if not isinstance(body, dict) or not isinstance(body.get("answers"), dict):
        raise DecisionResponseError("Jev response has no answers object")
    raw_answers = body["answers"]
    answers: dict[str, Answer] = {}
    for name, question in questions.items():
        if name not in raw_answers:
            raise DecisionResponseError(f"Jev returned no answer for question {name!r}")
        answers[name] = _parse_answer(name, question, raw_answers[name])
    try:
        decision = Decision(
            id=body.get("id"),
            model=body.get("model"),
            provider=body.get("provider"),
            answers=answers,
            usage=body.get("usage"),
        )
    except ValidationError as exc:
        raise DecisionResponseError(f"Unexpected Jev response envelope: {exc}") from exc
    if not _PINNED_MODEL_REPLY.fullmatch(decision.model):
        raise DecisionResponseError(f"Jev answered with {decision.model!r}, not the pinned {JEV_MODEL!r}")
    return decision


def _redact(value: Any, secret: str) -> Any:
    """Return `value` with `secret` replaced by a placeholder in every string it holds."""
    if not secret:
        return value
    return json.loads(json.dumps(value, default=str).replace(json.dumps(secret)[1:-1], "[redacted]"))


class DecisionClient:
    """Asks Jev typed questions about a `state`. One call is one HTTP request.

    Questions in one call are answered in parallel and can't see each other's answers.
    """

    def __init__(
        self,
        *,
        api_key: SecretStr,
        timeout_s: float = 15.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._secret = api_key.get_secret_value()
        self._http = httpx.Client(
            headers={"Authorization": f"Bearer {self._secret}"},
            timeout=timeout_s,
            transport=transport,
        )
        # Built per client so traced inputs and outputs can be scrubbed of this client's key:
        # a response that echoes it back would otherwise reach LangSmith.
        traced = traceable(
            name="jev_decide",
            run_type="chain",
            metadata={"ls_provider": "openrouter", "ls_model_name": JEV_MODEL},
            process_inputs=lambda inputs: _redact(inputs, self._secret),
            process_outputs=lambda outputs: _redact(outputs, self._secret),
        )(self._decide)
        self._traced_decide = cast("Any", traced)  # langsmith's wrapper type confuses the checker

    def decide(self, state: Mapping[str, Any], questions: Mapping[str, Question]) -> Decision:
        return self._traced_decide(state, questions)

    def _decide(self, state: Mapping[str, Any], questions: Mapping[str, Question]) -> Decision:
        if not questions:
            raise ValueError("Ask Jev at least one question")
        try:
            return self._request(state, questions)
        except DecisionError as exc:
            # Upstream text (HTTP bodies, validation inputs) can echo the key back, and the
            # traced wrapper records the exception, so scrub it and drop the chained causes.
            if self._secret:
                exc.args = tuple(str(arg).replace(self._secret, "[redacted]") for arg in exc.args)
            exc.__cause__ = None
            exc.__context__ = None
            raise

    def _request(self, state: Mapping[str, Any], questions: Mapping[str, Question]) -> Decision:
        payload = {
            "model": JEV_MODEL,
            "state": dict(state),
            "questions": {name: question.model_dump() for name, question in questions.items()},
        }
        try:
            response = self._http.post(DECISIONS_URL, json=payload)
        except httpx.TimeoutException as exc:
            raise DecisionTimeoutError(f"Jev didn't answer within the timeout: {exc}") from exc
        except httpx.TransportError as exc:
            raise DecisionError(f"Jev decisions request failed: {exc}") from exc
        if not response.is_success:
            raise DecisionHTTPError(response.status_code, response.text)
        try:
            body = response.json()
        except ValueError as exc:
            raise DecisionResponseError("Jev returned a body that isn't JSON") from exc
        return _parse(body, questions)
