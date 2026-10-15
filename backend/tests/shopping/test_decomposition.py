from __future__ import annotations

import threading
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from pydantic import SecretStr

from glean.decisions import DecisionClient
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.shopping.schemas import ShoppingParseRequest, ShoppingParseResponse
from glean.shopping import service
from glean.shopping.service import (
    DISH_PARSE_SYSTEM_PROMPT,
    ITEM_PARSE_SYSTEM_PROMPT,
    SHOPPING_PARSE_SYSTEM_PROMPT,
    parse_shopping_description,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from glean.llm import Feature


def _item(name: str, *, unit: str = "units", confidence: float = 0.9) -> dict[str, Any]:
    return {"name": name, "quantity": 1, "unit": unit, "unit_price": None, "category": None, "confidence": confidence}


def _phrase_of(message: Any) -> str:
    return message.content.removeprefix("Parse this shopping list description: ")


class _FakeLLMRouter:
    """Answers each shopping phrase with one item named after it, or with a canned reply."""

    def __init__(self, replies: dict[str, ShoppingParseResponse] | None = None) -> None:
        self.replies = replies or {}
        self.calls: list[tuple[Feature, type[object], list[Any]]] = []
        self._lock = threading.Lock()

    def model_id_for(self, feature: Feature) -> str:
        return "test/model"

    def invoke(self, feature: Feature, schema: type[object], messages: list[Any]) -> ShoppingParseResponse:
        with self._lock:
            self.calls.append((feature, schema, messages))
        phrase = _phrase_of(messages[1])
        return self.replies.get(phrase) or ShoppingParseResponse(items=[_item(phrase)])

    @property
    def phrases(self) -> list[str]:
        return sorted(_phrase_of(messages[1]) for _, _, messages in self.calls)


def _decision_client(
    dish_probability: Callable[[str], float] = lambda phrase: 0.5, *, status: int = 200
) -> DecisionClient:
    """A real DecisionClient whose HTTP endpoint says how dish-like each phrase is."""

    def handler(request: httpx.Request) -> httpx.Response:
        import json  # noqa: PLC0415

        phrase = json.loads(request.content)["state"]["phrase"]
        return httpx.Response(
            status,
            json={
                "id": "gen-dec-1",
                "model": "typesafe/jev-1.14-20261014",
                "provider": "TypeSafe",
                "answers": {"names_a_dish": {"type": "noul", "noul": dish_probability(phrase)}},
                "usage": {"input_tokens": 10, "output_tokens": 1, "cost": 0.0},
            },
        )

    return DecisionClient(api_key=SecretStr("test"), transport=httpx.MockTransport(handler))


def _parse(
    text: str, *, router: _FakeLLMRouter, tmp_path: Path, decisions: DecisionClient | None = None
) -> ShoppingParseResponse:
    return parse_shopping_description(
        ShoppingParseRequest(text=text),
        llm_router=router,
        decision_client=decisions or _decision_client(),
        cache=FilesystemBlobStore(tmp_path),
    )


def test_a_multi_item_description_is_split_into_shopping_units_parsed_one_by_one(tmp_path: Path) -> None:
    router = _FakeLLMRouter()

    response = _parse("milk, 2 bananas and bread;\neggs", router=router, tmp_path=tmp_path)

    assert router.phrases == ["2 bananas", "bread", "eggs", "milk"]
    assert [item.name for item in response.items] == ["milk", "2 bananas", "bread", "eggs"]


def test_all_cache_hits_are_answered_without_calling_the_llm_or_the_decision_model(tmp_path: Path) -> None:
    _parse("milk, bread", router=_FakeLLMRouter(), tmp_path=tmp_path)
    router = _FakeLLMRouter()

    def unreachable(phrase: str) -> float:
        raise AssertionError(f"decision asked about a cached phrase: {phrase}")

    response = _parse("Milk,  bread", router=router, tmp_path=tmp_path, decisions=_decision_client(unreachable))

    assert router.calls == []
    assert [item.name for item in response.items] == ["milk", "bread"]


def test_partial_hits_call_the_llm_only_for_the_misses_and_merge_in_description_order(tmp_path: Path) -> None:
    _parse("bread", router=_FakeLLMRouter(), tmp_path=tmp_path)
    router = _FakeLLMRouter()

    response = _parse("milk, bread, eggs", router=router, tmp_path=tmp_path)

    assert router.phrases == ["eggs", "milk"]
    assert [item.name for item in response.items] == ["milk", "bread", "eggs"]


def test_a_unit_repeated_in_the_description_is_parsed_once_and_proposed_once(tmp_path: Path) -> None:
    router = _FakeLLMRouter()

    response = _parse("milk, bread, Milk", router=router, tmp_path=tmp_path)

    assert router.phrases == ["bread", "milk"]
    assert [item.name for item in response.items] == ["milk", "bread"]


def _system_prompts(router: _FakeLLMRouter) -> dict[str, str]:
    return {_phrase_of(messages[1]): messages[0].content for _, _, messages in router.calls}


def test_a_phrase_that_names_a_dish_is_parsed_with_the_dish_decomposition_prompt(tmp_path: Path) -> None:
    router = _FakeLLMRouter()

    _parse("tacos, milk", router=router, tmp_path=tmp_path, decisions=_decision_client(lambda p: 0.95 if p == "tacos" else 0.02))

    assert _system_prompts(router) == {"tacos": DISH_PARSE_SYSTEM_PROMPT, "milk": ITEM_PARSE_SYSTEM_PROMPT}


def test_an_ambiguous_phrase_falls_back_to_the_combined_prompt_and_keeps_its_clarifying_questions(
    tmp_path: Path,
) -> None:
    router = _FakeLLMRouter(
        {
            "snacks": ShoppingParseResponse(items=[_item("snacks", confidence=0.5)], clarifying_questions=["Which snacks?"]),
            "treats": ShoppingParseResponse(items=[_item("treats", confidence=0.5)], clarifying_questions=["Which snacks?"]),
        }
    )

    response = _parse("snacks, treats", router=router, tmp_path=tmp_path, decisions=_decision_client(lambda p: 0.5))

    assert set(_system_prompts(router).values()) == {SHOPPING_PARSE_SYSTEM_PROMPT}
    assert [item.name for item in response.items] == ["snacks", "treats"]
    assert response.clarifying_questions == ["Which snacks?"]


def test_when_the_decision_model_is_unavailable_the_combined_prompt_is_used_and_nothing_is_cached(
    tmp_path: Path,
) -> None:
    router = _FakeLLMRouter()

    response = _parse("tacos", router=router, tmp_path=tmp_path, decisions=_decision_client(status=503))

    assert [item.name for item in response.items] == ["tacos"]
    assert _system_prompts(router) == {"tacos": SHOPPING_PARSE_SYSTEM_PROMPT}

    retry = _FakeLLMRouter()
    _parse("tacos", router=retry, tmp_path=tmp_path, decisions=_decision_client(lambda p: 0.95))
    assert _system_prompts(retry) == {"tacos": DISH_PARSE_SYSTEM_PROMPT}


class _ChangedModelRouter(_FakeLLMRouter):
    def model_id_for(self, feature: Feature) -> str:
        return "test/another-model"


def test_cached_parses_are_invalidated_when_prompt_schema_unit_vocabulary_or_models_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def misses_after(change: Callable[[], None], router: _FakeLLMRouter | None = None) -> bool:
        store = tmp_path / str(len(list(tmp_path.iterdir())))
        _parse("milk", router=_FakeLLMRouter(), tmp_path=store)
        change()
        router = router or _FakeLLMRouter()
        _parse("milk", router=router, tmp_path=store)
        monkeypatch.undo()
        return bool(router.calls)

    assert not misses_after(lambda: None)
    assert misses_after(lambda: monkeypatch.setattr(service, "ITEM_PARSE_SYSTEM_PROMPT", "changed"))
    assert misses_after(lambda: monkeypatch.setattr(service, "DISH_PARSE_SYSTEM_PROMPT", "changed"))
    assert misses_after(lambda: monkeypatch.setattr(service, "SHOPPING_PARSE_SYSTEM_PROMPT", "changed"))
    assert misses_after(lambda: monkeypatch.setattr(service, "ShoppingUnit", StrEnum("ShoppingUnit", {"G": "g"})))
    assert misses_after(lambda: monkeypatch.setattr(service, "DECISION_MODEL", "typesafe/jev-9"))
    assert misses_after(lambda: None, router=_ChangedModelRouter())
    assert misses_after(
        lambda: monkeypatch.setattr(
            service.ShoppingParseResponse, "model_json_schema", classmethod(lambda cls, **_: {"changed": True})
        )
    )


class _BrokenStore(FilesystemBlobStore):
    """A cache whose entries are unreadable and whose writes fail, like a flaky bucket."""

    def read(self, key: str) -> str | None:
        return "not json"

    def write(self, key: str, content: str) -> None:
        raise OSError("bucket unavailable")


def test_an_unreadable_or_unwritable_cache_never_fails_the_parse(tmp_path: Path) -> None:
    router = _FakeLLMRouter()

    response = parse_shopping_description(
        ShoppingParseRequest(text="milk"),
        llm_router=router,
        decision_client=_decision_client(),
        cache=_BrokenStore(tmp_path),
    )

    assert [item.name for item in response.items] == ["milk"]
    assert router.phrases == ["milk"]
