"""Client for Jev, TypeSafe's decision model, on OpenRouter's alpha decisions endpoint.

This module is the only code that calls the endpoint. Features that need a typed
decision (#123 normalisation, #125 dietary checks, #124 eval judging) go through
DecisionClient, so a change to the alpha API touches one place.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

if TYPE_CHECKING:
    from collections.abc import Mapping

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


class ChoiceAnswer(BaseModel):
    choice: str
    probabilities: dict[str, float]
    confidence: float


class NoulAnswer(BaseModel):
    noul: float = Field(ge=0.0, le=1.0)  # probability of `true`


class ScoreAnswer(BaseModel):
    score: float  # probability-weighted position on the scale; 0 is criteria[0]
    probabilities: dict[int, float]
    confidence: float


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


# "jev-1.13": the dated snapshot Jev reports must belong to the pinned version.
_PINNED_VERSION = JEV_MODEL.split("/", 1)[1]


def _parse_answer(name: str, question: Question, raw: Any) -> Answer:
    try:
        if isinstance(question, ChoiceQuestion):
            choice = ChoiceAnswer.model_validate(raw)
            if choice.choice not in question.criteria:
                raise DecisionResponseError(f"Jev chose {choice.choice!r} for {name!r}, which wasn't offered")
            return choice
        if isinstance(question, NoulQuestion):
            return NoulAnswer.model_validate(raw)
        return ScoreAnswer.model_validate(raw)
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
    if _PINNED_VERSION not in decision.model:
        raise DecisionResponseError(f"Jev answered with {decision.model!r}, not the pinned {JEV_MODEL!r}")
    return decision


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
        self._http = httpx.Client(
            headers={"Authorization": f"Bearer {api_key.get_secret_value()}"},
            timeout=timeout_s,
            transport=transport,
        )

    def decide(self, state: Mapping[str, Any], questions: Mapping[str, Question]) -> Decision:
        if not questions:
            raise ValueError("Ask Jev at least one question")
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
