from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

import httpx
from pydantic import SecretStr

from glean.decisions import DecisionClient
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.shopping.schemas import ShoppingParseRequest, ShoppingParseResponse
from glean.shopping.service import parse_shopping_description

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


def _decision_client(dish_probability: Callable[[str], float] = lambda phrase: 0.5) -> DecisionClient:
    """A real DecisionClient whose HTTP endpoint says how dish-like each phrase is."""

    def handler(request: httpx.Request) -> httpx.Response:
        import json  # noqa: PLC0415

        phrase = json.loads(request.content)["state"]["phrase"]
        return httpx.Response(
            200,
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
