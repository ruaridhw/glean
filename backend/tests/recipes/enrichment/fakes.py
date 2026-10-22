"""Fakes for the enrichment tests: a recording decision API and a second, test-only enricher.

The second enricher exists so the runner is tested as a pipeline of two families of questions rather than
against dietary alone, and so the acceptance hook is exercised by a rule that is not dietary's: a high bar
below which nothing is stored (the shape V5's attribute questions take, ADR 0025).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx
from pydantic import SecretStr

from glean.decisions import DECISION_MODEL, DecisionClient, NoulCriteria, NoulQuestion
from glean.recipes.corpus import BlobCorpusBackend
from glean.recipes.enrichment import Acceptance, ConfidenceBar, EnrichmentQuestion, SafeSide

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

    def client(self) -> DecisionClient:
        return DecisionClient(api_key=SecretStr("sk-or-test"), transport=httpx.MockTransport(self._handle))

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
                    name: {"type": "noul", "noul": self._high if name == DINNER or marked else self._low}
                    for name in body["questions"]
                },
                "usage": {"input_tokens": 10, "output_tokens": 2, "cost": 0.00001},
            },
        )

    def asked(self, title: str) -> dict:
        """The one request the fake saw for the recipe with this title."""
        return next(request for request in self.requests if request["state"]["recipe_title"] == title)


def bared_noul(name: str, bar: ConfidenceBar) -> Acceptance:
    """Accept the probability only when it clears the bar, and store nothing below it."""

    def accept(decision) -> float | None:
        value = decision.noul(name).noul
        return value if value >= bar.threshold else None

    return accept


def dinner_question(*, threshold: float = 0.8, instructions: str | None = None) -> EnrichmentQuestion:
    """A question no production enricher declares: high side safe, nothing stored below the bar."""
    bar = ConfidenceBar(threshold=threshold, safe_side=SafeSide.HIGH)
    return EnrichmentQuestion(
        name=DINNER,
        question=NoulQuestion(
            instructions=instructions or "Is this recipe a dinner rather than a breakfast or a snack?",
            criteria=NoulCriteria(true="The recipe is a dinner.", false="The recipe is not a dinner."),
        ),
        bar=bar,
        accept=bared_noul(DINNER, bar),
    )


@dataclass(frozen=True)
class DinnerEnricher:
    """The test-only second enricher: one `noul` question with an attribute-style bar."""

    name: str = "test-dinner"
    threshold: float = 0.8
    instructions: str | None = None

    def questions(self) -> Sequence[EnrichmentQuestion]:
        return (dinner_question(threshold=self.threshold, instructions=self.instructions),)


class CountingBackend(BlobCorpusBackend):
    """The blob corpus backend, counting the writes and rebuilds the runner asks it for."""

    def __init__(self, blobs: BlobStore) -> None:
        super().__init__(blobs)
        self.rebuilds = 0
        self.answer_writes = 0

    def rebuild_index(self) -> int:
        self.rebuilds += 1
        return super().rebuild_index()

    def save_answers(self, answers: Sequence[RecipeAnswer]) -> int:
        self.answer_writes += 1
        return super().save_answers(answers)
