"""Fakes for the enrichment tests: a recording decision API and a second, test-only enricher.

The second enricher exists so the runner is tested as a pipeline of two families of questions rather than
against dietary alone, and so the acceptance hook is exercised by a rule that is not dietary's: a `choice`
question whose top option is stored with its probability, and whose bar decides at read time whether that
option is trusted (exactly the shape V5's attribute questions take, ADR 0025). It answers in the endpoint's
wire format, so the tests cross the same seam the real client does.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx
from pydantic import SecretStr

from glean.decisions import (
    DECISION_MODEL,
    DEFAULT_MODEL,
    ChoiceQuestion,
    DecisionClient,
    DecisionModel,
)
from glean.recipes.corpus import BlobCorpusBackend
from glean.recipes.enrichment import Acceptance, ConfidenceBar, EnrichmentQuestion, SafeSide, StoredValue

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from glean.recipe_api.blob_store import BlobStore
    from glean.recipes.answers import RecipeAnswer

SNAPSHOT = f"{DECISION_MODEL}-20261014"
# Any recipe naming this ingredient looks like a nut/animal product to the fake, and so scores high.
MARKER = "pesto"
DINNER = "test:dinner"


class FakeDecisionApi:
    """Answers each question high when the recipe names the marker (or the question is the test-only one).

    Everything else scores low, so a recipe looks clean to the fake unless it names `pesto`. It speaks the
    endpoint's wire format, so the tests cross the same seam the real client does, and it records what it
    was asked.
    """

    def __init__(
        self,
        *,
        snapshot: str = SNAPSHOT,
        fail_when: Callable[[dict], bool] | None = None,
        high: float = 0.9,
        low: float = 0.01,
        marker: str = MARKER,
        crash_when: Callable[[dict], bool] | None = None,
    ) -> None:
        self.requests: list[dict] = []
        self._snapshot = snapshot
        self._fail_when = fail_when
        self._crash_when = crash_when
        self._high = high
        self._low = low
        self._marker = marker

    def client(self, *, model: DecisionModel = DEFAULT_MODEL) -> DecisionClient:
        return DecisionClient(api_key=SecretStr("sk-or-test"), model=model, transport=httpx.MockTransport(self._handle))

    def _handle(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.requests.append(body)
        if self._crash_when is not None and self._crash_when(body):
            raise RuntimeError("the decision client died mid-run")
        if self._fail_when is not None and self._fail_when(body):
            return httpx.Response(500, text="boom")
        marked = self._marker in json.dumps(body["state"])
        return httpx.Response(
            200,
            json={
                "id": "gen-dec-test",
                "model": self._snapshot,
                "provider": "TypeSafe",
                "answers": {
                    name: self._answer(question, high=name == DINNER or marked)
                    for name, question in body["questions"].items()
                },
                "usage": {"input_tokens": 10, "output_tokens": 2, "cost": 0.00001},
            },
        )

    def _answer(self, question: dict, *, high: bool) -> dict:
        """One answer in the endpoint's shape: a `noul` probability, a choice distribution, or a score."""
        if question["type"] == "noul":
            return {"type": "noul", "noul": self._high if high else self._low}
        if question["type"] == "choice":
            options = list(question["criteria"])
            top = options[0] if high else options[1]
            rest = (1.0 - self._high) / max(len(options) - 1, 1)
            probabilities = {option: (self._high if option == top else rest) for option in options}
            return {"type": "choice", "choice": top, "probabilities": probabilities, "confidence": self._high}
        # A score question: the same distribution over level indices, high at the top level and low at the
        # bottom, plus the probability-weighted position the endpoint reports with it.
        levels = len(question["criteria"])
        top = levels - 1 if high else 0
        rest = (1.0 - self._high) / max(levels - 1, 1)
        probabilities = {index: (self._high if index == top else rest) for index in range(levels)}
        score = sum(index * probability for index, probability in probabilities.items())
        return {
            "type": "score",
            "score": score,
            "probabilities": {str(index): probability for index, probability in probabilities.items()},
            "confidence": self._high,
        }

    def asked(self, title: str) -> dict:
        """The one request the fake saw for the recipe with this title."""
        return next(request for request in self.requests if request["state"]["recipe_title"] == title)


def bared_choice(name: str) -> Acceptance:
    """Store the top option (V5's attribute rule): the bar is applied when the answer is read, not here."""

    def accept(decision) -> StoredValue:
        answer = decision.choice(name)
        top = max(answer.probabilities, key=lambda option: answer.probabilities[option])
        return StoredValue(probability=answer.probabilities[top], value=top)

    return accept


def dinner_question(*, threshold: float = 0.8, instructions: str | None = None) -> EnrichmentQuestion:
    """A question no production enricher declares: high side safe, `unsure` stored below the bar."""
    bar = ConfidenceBar(threshold=threshold, safe_side=SafeSide.HIGH)
    return EnrichmentQuestion(
        name=DINNER,
        question=ChoiceQuestion(
            instructions=instructions or "Which meal is this recipe for: dinner, or not dinner?",
            criteria={
                "dinner": "The recipe is served as an evening meal.",
                "not_dinner": "The recipe is a breakfast, a snack, a side or a drink.",
            },
        ),
        bar=bar,
        accept=bared_choice(DINNER),
    )


@dataclass(frozen=True)
class DinnerEnricher:
    """The test-only second enricher: one `choice` question with an attribute-style bar and `unsure`."""

    name: str = "test-dinner"
    threshold: float = 0.8
    instructions: str | None = None

    def questions(self) -> Sequence[EnrichmentQuestion]:
        return (dinner_question(threshold=self.threshold, instructions=self.instructions),)

    def state(self, recipe) -> dict:
        return {}


class CountingBackend(BlobCorpusBackend):
    """The blob corpus backend, counting the writes and rebuilds the runner asks it for."""

    def __init__(self, blobs: BlobStore) -> None:
        super().__init__(blobs)
        self.rebuilds = 0
        self.answer_writes = 0
        self.batches: list[int] = []

    def rebuild_index(self) -> int:
        self.rebuilds += 1
        return super().rebuild_index()

    def save_answers(self, answers: Sequence[RecipeAnswer]) -> int:
        self.answer_writes += 1
        self.batches.append(len(answers))
        return super().save_answers(answers)
