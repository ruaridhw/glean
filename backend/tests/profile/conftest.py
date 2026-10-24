"""Fakes for the interview's two paid boundaries: the decisions endpoint and the LLM router.

The corpus is real (a throwaway filesystem blob store), so favourite-meal matching is tested
against the same search code the deployed corpus uses.
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from pydantic import SecretStr

from glean.decisions import DecisionClient
from glean.dependencies import get_decision_client, get_llm_router
from glean.main import app
from glean.profile import service
from glean.profile.schemas import InterviewTurn, ProfileDraft
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.stored import RecipeProvenance, StoredRecipe
from glean.screening import clear_screen_cache

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from pathlib import Path

ACCEPTED = 0.95
REJECTED = 0.05


class FakeDecisions:
    """The decisions endpoint: a low probability for a note containing an injected marker."""

    def __init__(self, *, injected: Sequence[str] = (), probability: float = ACCEPTED) -> None:
        self.injected = [marker.casefold() for marker in injected]
        self.probability = probability
        self.notes: list[str] = []

    def client(self) -> DecisionClient:
        return DecisionClient(api_key=SecretStr("test"), transport=httpx.MockTransport(self._answer))

    def _answer(self, request: httpx.Request) -> httpx.Response:
        note = json.loads(request.content)["state"]["note"]
        self.notes.append(note)
        probability = REJECTED if any(marker in note.casefold() for marker in self.injected) else self.probability
        return _noul_response(probability)


def slow_decisions(delay_s: float = 0.5) -> DecisionClient:
    """A decisions client that takes its time, for the request's screening budget."""

    def slow(request: httpx.Request) -> httpx.Response:
        time.sleep(delay_s)
        return _noul_response(ACCEPTED)

    return DecisionClient(api_key=SecretStr("test"), transport=httpx.MockTransport(slow))


def broken_decisions() -> DecisionClient:
    """A decisions client that cannot answer: the screen has to fail closed."""

    def unavailable(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "upstream unavailable"})

    return DecisionClient(api_key=SecretStr("test"), transport=httpx.MockTransport(unavailable))


def _noul_response(probability: float) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "gen-dec-interview",
            "model": "typesafe/jev-1.14-20261014",
            "provider": "TypeSafe",
            "answers": {"is_food_preference": {"type": "noul", "noul": probability}},
            "usage": {"input_tokens": 10, "output_tokens": 1, "cost": 0.0},
        },
    )


def empty_draft() -> ProfileDraft:
    """A draft profile with nothing filled in, as the model would return when it heard nothing usable."""
    return ProfileDraft(
        favourite_meals=[],
        loved_ingredients=[],
        disliked_ingredients=[],
        cuisines_liked=[],
        cuisines_avoided=[],
        protein_targets=[],
        spice_tolerance=None,
        habits="",
        household="",
    )


def finished(draft: ProfileDraft | None = None, summary: str = "") -> InterviewTurn:
    """A model turn that asks nothing, which finishes the interview."""
    return InterviewTurn(draft_profile=draft or empty_draft(), question=None, summary=summary)


def asks(text: str, field: str = "spice_tolerance", options: Sequence[str] = ()) -> InterviewTurn:
    """A model turn that asks one follow-up."""
    return InterviewTurn(
        draft_profile=empty_draft(),
        question={"text": text, "field": field, "options": list(options)},  # type: ignore[arg-type]
        summary="",
    )


class FakeRouter:
    """Answers each structured call with the next scripted turn, and records what it was asked."""

    def __init__(self, replies: Sequence[InterviewTurn] = ()) -> None:
        self.replies = list(replies)
        self.calls: list[dict[str, Any]] = []

    def invoke(self, feature: object, schema: type, messages: Any, **_: Any) -> InterviewTurn:
        self.calls.append({"feature": feature, "schema": schema, "messages": messages})
        if self.replies:
            reply = self.replies.pop(0)
            assert isinstance(reply, schema)
            return reply
        return finished()

    def payload(self, index: int = -1) -> dict[str, Any]:
        """The JSON the model was given, so a test can prove what did and didn't reach it."""
        return json.loads(self.calls[index]["messages"][-1].content)

    def sent_text(self, index: int = -1) -> str:
        return "\n".join(str(message.content) for message in self.calls[index]["messages"])


def stored_recipe(external_id: str, title: str) -> StoredRecipe:
    return StoredRecipe(
        external_id=external_id,
        title=title,
        difficulty="Easy",
        total_time_mins=30,
        provenance=RecipeProvenance(source_url="", parser="test"),
    )


@pytest.fixture
def decisions() -> FakeDecisions:
    return FakeDecisions()


@pytest.fixture
def model() -> FakeRouter:
    return FakeRouter()


@pytest.fixture
def corpus(tmp_path: Path) -> RecipeCorpusStore:
    store = RecipeCorpusStore(FilesystemBlobStore(tmp_path / "corpus"))
    store.rebuild_index()
    return store


@pytest.fixture(autouse=True)
def _local_boundaries(decisions: FakeDecisions, model: FakeRouter, corpus: RecipeCorpusStore, monkeypatch) -> None:
    """HTTP tests get the canned decisions endpoint, the scripted router and a throwaway corpus."""
    app.dependency_overrides[get_decision_client] = decisions.client
    app.dependency_overrides[get_llm_router] = lambda: model
    monkeypatch.setattr(service, "RecipeCorpusStore", lambda: corpus)
    clear_screen_cache()


@pytest.fixture(autouse=True)
def _cold_screen_cache() -> Iterator[None]:
    """The screen's cache lives on the module, so a test must never inherit another test's answers."""
    clear_screen_cache()
    yield
    clear_screen_cache()
