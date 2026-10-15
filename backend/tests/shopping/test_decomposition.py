from __future__ import annotations

import json
import re
import threading
import time
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from botocore.exceptions import ConnectTimeoutError, EndpointConnectionError
from pydantic import SecretStr

from glean.decisions import DecisionClient
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.shopping import service
from glean.shopping.schemas import ShoppingBatchParseResponse, ShoppingParseRequest, ShoppingParseResponse
from glean.shopping.service import SHOPPING_PARSE_SYSTEM_PROMPT, parse_shopping_description

if TYPE_CHECKING:
    from collections.abc import Callable

    from glean.llm import Feature

# Live scores from the pinned decision model for a labelled phrase sample, recorded once (see the fixture).
_SAMPLE = json.loads((Path(__file__).parents[1] / "fixtures" / "shopping_gate_sample.json").read_text())
_RECORDED = {row["phrase"]: (row["dish"], row["list"]) for row in _SAMPLE}
_NUMBERED_PHRASE = re.compile(r"^(\d+)\. \[(\w+)\] (.+)$", re.MULTILINE)


def _item(name: str, *, unit: str = "units", confidence: float = 0.9) -> dict[str, Any]:
    return {"name": name, "quantity": 1, "unit": unit, "unit_price": None, "category": None, "confidence": confidence}


class _FakeLLMRouter:
    """Answers each numbered phrase with one item named after it, or with a canned reply.

    `batches` records, per batch call, the (treatment, phrase) pairs it was asked about; `singles` records
    the (system prompt, text) of each single-call parse.
    """

    def __init__(
        self,
        replies: dict[str, ShoppingParseResponse] | None = None,
        *,
        model: str = "test/model",
        delay_s: float = 0.0,
        hang: threading.Event | None = None,
        omit: set[str] = frozenset(),
    ) -> None:
        self.replies = replies or {}
        self.model = model
        self.delay_s = delay_s
        self.hang = hang
        self.omit = omit
        self.batches: list[list[tuple[str, str]]] = []
        self.singles: list[tuple[str, str]] = []
        self._lock = threading.Lock()

    def model_id_for(self, feature: Feature) -> str:
        return self.model

    def invoke(self, feature: Feature, schema: type[object], messages: list[Any], **kwargs: Any) -> Any:
        if schema is ShoppingBatchParseResponse:
            return self._batch(messages[1].content)
        text = messages[1].content.removeprefix("Parse this shopping list description: ")
        with self._lock:
            self.singles.append((messages[0].content, text))
        return ShoppingParseResponse(items=[_item(text)])

    def _batch(self, text: str) -> ShoppingBatchParseResponse:
        listed = [(int(number), treatment, phrase) for number, treatment, phrase in _NUMBERED_PHRASE.findall(text)]
        with self._lock:
            self.batches.append([(treatment, phrase) for _, treatment, phrase in listed])
        if self.hang is not None:
            self.hang.wait(5)
        time.sleep(self.delay_s)
        units = []
        for number, _, phrase in listed:
            if phrase in self.omit:
                continue
            reply = self.replies.get(phrase) or ShoppingParseResponse(items=[_item(phrase)])
            units.append(
                {
                    "number": number,
                    **reply.model_dump(exclude={"items": {"__all__": {"food_group", "api_ingredient_id"}}}),
                }
            )
        return ShoppingBatchParseResponse.model_validate({"units": units})

    @property
    def phrases(self) -> list[str]:
        return sorted(phrase for batch in self.batches for _, phrase in batch)

    @property
    def treatments(self) -> dict[str, str]:
        return {phrase: treatment for batch in self.batches for treatment, phrase in batch}


class _Decisions:
    """A real DecisionClient whose HTTP endpoint answers from `scores` (phrase -> (dish, list))."""

    def __init__(
        self, scores: Callable[[str], tuple[float, float]] = lambda phrase: (0.5, 0.1), *, status: int = 200
    ) -> None:
        self.asked: list[tuple[str, tuple[str, ...]]] = []
        self._scores = scores
        self._status = status
        self._lock = threading.Lock()
        self.client = DecisionClient(api_key=SecretStr("test"), transport=httpx.MockTransport(self._handle))

    def _handle(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        phrase, names = body["state"]["phrase"], tuple(body["questions"])
        with self._lock:
            self.asked.append((phrase, names))
        dish, listed = self._scores(phrase)
        answers = {"names_a_dish": dish, "lists_several_items": listed}
        return httpx.Response(
            self._status,
            json={
                "id": "gen-dec-1",
                "model": "typesafe/jev-1.14-20261014",
                "provider": "TypeSafe",
                "answers": {name: {"type": "noul", "noul": answers[name]} for name in names},
                "usage": {"input_tokens": 10, "output_tokens": 1, "cost": 0.0},
            },
        )


def _recorded(phrase: str) -> tuple[float, float]:
    return _RECORDED.get(phrase, (0.03, 0.03))


def _parse(
    text: str,
    *,
    router: _FakeLLMRouter,
    tmp_path: Path,
    decisions: _Decisions | None = None,
    cache: FilesystemBlobStore | None = None,
    time_budget_s: float | None = None,
) -> ShoppingParseResponse:
    extra = {} if time_budget_s is None else {"time_budget_s": time_budget_s}
    return parse_shopping_description(
        ShoppingParseRequest(text=text),
        llm_router=router,
        decision_client=(decisions or _Decisions()).client,
        cache=cache or FilesystemBlobStore(tmp_path),
        **extra,
    )


def _names(response: ShoppingParseResponse) -> list[str]:
    return [item.name for item in response.items]


def test_a_multi_item_description_is_split_at_list_separators_and_parsed_in_one_model_call(tmp_path: Path) -> None:
    router = _FakeLLMRouter()

    response = _parse("milk, 2 bananas; bread,\n and eggs", router=router, tmp_path=tmp_path)

    assert len(router.batches) == 1
    assert router.phrases == ["2 bananas", "bread", "eggs", "milk"]
    assert _names(response) == ["milk", "2 bananas", "bread", "eggs"]


def test_a_decimal_comma_is_not_a_list_separator(tmp_path: Path) -> None:
    router = _FakeLLMRouter()

    _parse("1,5 kg potatoes, milk", router=router, tmp_path=tmp_path)

    assert router.phrases == ["1,5 kg potatoes", "milk"]


def test_all_cache_hits_are_answered_without_calling_the_llm_or_the_decision_model(tmp_path: Path) -> None:
    _parse("milk, bread", router=_FakeLLMRouter(), tmp_path=tmp_path)
    router, decisions = _FakeLLMRouter(), _Decisions()

    response = _parse("Milk,  bread", router=router, tmp_path=tmp_path, decisions=decisions)

    assert (router.batches, router.singles, decisions.asked) == ([], [], [])
    assert _names(response) == ["milk", "bread"]


def test_partial_hits_ask_the_model_only_about_the_misses_and_merge_in_description_order(tmp_path: Path) -> None:
    _parse("bread", router=_FakeLLMRouter(), tmp_path=tmp_path)
    router = _FakeLLMRouter()

    response = _parse("milk, bread, eggs", router=router, tmp_path=tmp_path)

    assert len(router.batches) == 1
    assert router.phrases == ["eggs", "milk"]
    assert _names(response) == ["milk", "bread", "eggs"]


def test_a_unit_repeated_in_the_description_is_parsed_once_and_proposed_once(tmp_path: Path) -> None:
    router = _FakeLLMRouter()

    response = _parse("milk, bread, Milk", router=router, tmp_path=tmp_path)

    assert router.phrases == ["bread", "milk"]
    assert _names(response) == ["milk", "bread"]


def test_each_phrase_is_treated_as_a_dish_an_item_or_unsure_by_the_decision_model(tmp_path: Path) -> None:
    router = _FakeLLMRouter()

    _parse("tacos, milk, snacks", router=router, tmp_path=tmp_path, decisions=_Decisions(_recorded))

    assert router.treatments == {"tacos": "dish", "milk": "item", "snacks": "item"}
    router = _FakeLLMRouter()

    _parse("something for dinner", router=router, tmp_path=tmp_path, decisions=_Decisions(_recorded))

    assert router.treatments == {"something for dinner": "unsure"}


def test_an_ambiguous_phrase_keeps_its_clarifying_questions_merged_without_repeats(tmp_path: Path) -> None:
    router = _FakeLLMRouter(
        {
            "snacks": ShoppingParseResponse(items=[_item("snacks")], clarifying_questions=["Which snacks?"]),
            "treats": ShoppingParseResponse(items=[_item("treats")], clarifying_questions=["Which snacks?"]),
        }
    )

    response = _parse("snacks, treats", router=router, tmp_path=tmp_path)

    assert _names(response) == ["snacks", "treats"]
    assert response.clarifying_questions == ["Which snacks?"]


def test_when_the_decision_model_is_unavailable_phrases_are_unsure_and_nothing_is_cached(tmp_path: Path) -> None:
    router = _FakeLLMRouter()

    response = _parse("tacos", router=router, tmp_path=tmp_path, decisions=_Decisions(status=503))

    assert _names(response) == ["tacos"]
    assert router.treatments == {"tacos": "unsure"}

    retry = _FakeLLMRouter()
    _parse("tacos", router=retry, tmp_path=tmp_path, decisions=_Decisions(_recorded))
    assert retry.treatments == {"tacos": "dish"}


@pytest.mark.parametrize(
    "compound", ["sweet and sour sauce", "mac and cheese", "fish & chips", "salt and pepper crisps", "bangers and mash"]
)
def test_a_compound_dish_or_product_name_stays_whole_among_other_items(compound: str, tmp_path: Path) -> None:
    router = _FakeLLMRouter()

    response = _parse(f"milk, {compound}, eggs", router=router, tmp_path=tmp_path, decisions=_Decisions(_recorded))

    assert router.phrases == sorted(["milk", compound, "eggs"])
    assert _names(response) == ["milk", compound, "eggs"]


def test_a_segment_that_lists_separate_items_is_split_at_and_and_ampersand_after_the_decision(
    tmp_path: Path,
) -> None:
    router, decisions = _FakeLLMRouter(), _Decisions(_recorded)

    response = _parse("milk and eggs, bread & butter", router=router, tmp_path=tmp_path, decisions=decisions)

    assert _names(response) == ["milk", "eggs", "bread", "butter"]
    first_questions = [names for phrase, names in decisions.asked if phrase in {"milk and eggs", "bread & butter"}]
    assert first_questions == [("names_a_dish", "lists_several_items")] * 2


def test_a_split_segment_is_cached_whole_so_a_repeat_asks_nothing(tmp_path: Path) -> None:
    _parse("milk and eggs", router=_FakeLLMRouter(), tmp_path=tmp_path, decisions=_Decisions(_recorded))
    router, decisions = _FakeLLMRouter(), _Decisions(_recorded)

    response = _parse("milk and eggs", router=router, tmp_path=tmp_path, decisions=decisions)

    assert (router.batches, decisions.asked) == ([], [])
    assert _names(response) == ["milk", "eggs"]


def test_a_unit_cached_on_its_own_is_reused_when_it_reappears_inside_a_split_segment(tmp_path: Path) -> None:
    _parse("milk", router=_FakeLLMRouter(), tmp_path=tmp_path, decisions=_Decisions(_recorded))
    router = _FakeLLMRouter()

    response = _parse("milk and eggs", router=router, tmp_path=tmp_path, decisions=_Decisions(_recorded))

    assert router.phrases == ["eggs"]
    assert _names(response) == ["milk", "eggs"]


def test_a_unit_repeated_across_a_split_segment_and_a_plain_one_is_proposed_once(tmp_path: Path) -> None:
    _parse("milk, eggs", router=_FakeLLMRouter(), tmp_path=tmp_path, decisions=_Decisions(_recorded))
    router = _FakeLLMRouter()

    response = _parse("milk and eggs, milk", router=router, tmp_path=tmp_path, decisions=_Decisions(_recorded))

    assert router.batches == []
    assert _names(response) == ["milk", "eggs"]


def test_a_fully_cached_list_with_split_and_compound_segments_asks_no_model_anything(tmp_path: Path) -> None:
    text = "milk and eggs, mac and cheese, sweet and sour sauce, tacos"
    first = _parse(text, router=_FakeLLMRouter(), tmp_path=tmp_path, decisions=_Decisions(_recorded))
    router, decisions = _FakeLLMRouter(), _Decisions(_recorded)

    response = _parse(text, router=router, tmp_path=tmp_path, decisions=decisions)

    assert (router.batches, router.singles, decisions.asked) == ([], [], [])
    assert _names(response) == _names(first) == ["milk", "eggs", "mac and cheese", "sweet and sour sauce", "tacos"]


def _expected_route(row: dict[str, Any]) -> Callable[[dict[str, str]], bool]:
    """What a person labelling the sample expects the parser to do with this phrase."""
    phrase = row["phrase"]
    return {
        "dish": lambda treatments: treatments == {phrase: "dish"},
        "item": lambda treatments: len(treatments) == 1 and treatments.get(phrase) in {"item", "unsure"},
        "compound_item": lambda treatments: len(treatments) == 1 and treatments.get(phrase) in {"item", "unsure"},
        "list": lambda treatments: len(treatments) > 1 and phrase not in treatments,
        "ambiguous": lambda treatments: phrase not in {"tacos", "roast dinner"} or treatments == {phrase: "dish"},
    }[row["kind"]]


@pytest.mark.parametrize("row", _SAMPLE, ids=lambda row: row["phrase"])
def test_routing_follows_the_labelled_sample_scored_by_the_pinned_decision_model(
    row: dict[str, Any], tmp_path: Path
) -> None:
    router = _FakeLLMRouter()

    _parse(row["phrase"], router=router, tmp_path=tmp_path, decisions=_Decisions(_recorded))

    assert _expected_route(row)(router.treatments), router.treatments


def test_a_long_cold_list_is_parsed_with_one_model_call_inside_the_time_budget(tmp_path: Path) -> None:
    router = _FakeLLMRouter(delay_s=0.2)
    text = ", ".join(f"item {n}" for n in range(32))

    started = time.monotonic()
    response = _parse(text, router=router, tmp_path=tmp_path, time_budget_s=2.0)

    assert time.monotonic() - started < 2.0
    assert len(router.batches) == 1
    assert router.singles == []
    assert _names(response) == [f"item {n}" for n in range(32)]


def test_a_model_call_that_outlives_the_budget_degrades_to_the_single_call_parse(tmp_path: Path) -> None:
    hang = threading.Event()
    router = _FakeLLMRouter(hang=hang)
    store = FilesystemBlobStore(tmp_path)

    try:
        started = time.monotonic()
        response = _parse("milk, eggs", router=router, tmp_path=tmp_path, cache=store, time_budget_s=1.0)
        elapsed = time.monotonic() - started
    finally:
        hang.set()

    assert elapsed < 1.5
    assert router.singles == [(SHOPPING_PARSE_SYSTEM_PROMPT, "milk, eggs")]
    assert _names(response) == ["milk, eggs"]
    assert store.list_keys() == []


def test_a_phrase_the_batch_leaves_out_degrades_to_the_single_call_parse_and_the_rest_is_cached(
    tmp_path: Path,
) -> None:
    router = _FakeLLMRouter(omit={"eggs"})
    store = FilesystemBlobStore(tmp_path)

    response = _parse("milk, eggs, bread", router=router, tmp_path=tmp_path, cache=store)

    assert router.singles == [(SHOPPING_PARSE_SYSTEM_PROMPT, "eggs")]
    assert _names(response) == ["milk", "eggs", "bread"]
    assert len(store.list_keys()) == 2


class _ChangedModelRouter(_FakeLLMRouter):
    def model_id_for(self, feature: Feature) -> str:
        return "test/another-model"


def test_cached_parses_are_invalidated_when_prompt_schema_unit_vocabulary_or_models_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def misses_after(change: Callable[[], None], router: _FakeLLMRouter | None = None) -> bool:
        store = FilesystemBlobStore(tmp_path / str(len(list(tmp_path.iterdir()))))
        _parse("milk", router=_FakeLLMRouter(), tmp_path=tmp_path, cache=store)
        change()
        router = router or _FakeLLMRouter()
        _parse("milk", router=router, tmp_path=tmp_path, cache=store)
        monkeypatch.undo()
        return bool(router.batches)

    assert not misses_after(lambda: None)
    assert misses_after(lambda: monkeypatch.setattr(service, "BATCH_PARSE_SYSTEM_PROMPT", "changed"))
    assert misses_after(lambda: monkeypatch.setattr(service, "SHOPPING_PARSE_SYSTEM_PROMPT", "changed"))
    assert misses_after(lambda: monkeypatch.setattr(service, "ShoppingUnit", StrEnum("ShoppingUnit", {"G": "g"})))
    assert misses_after(lambda: monkeypatch.setattr(service, "DECISION_MODEL", "typesafe/jev-9"))
    assert misses_after(lambda: monkeypatch.setattr(service, "_DISH_AT_LEAST", 0.99))
    assert misses_after(lambda: None, router=_ChangedModelRouter())
    assert misses_after(
        lambda: monkeypatch.setattr(
            service.ShoppingBatchParseResponse, "model_json_schema", classmethod(lambda cls, **_: {"changed": True})
        )
    )


class _BrokenStore(FilesystemBlobStore):
    """A cache whose entries are unreadable and whose writes fail, like a flaky bucket."""

    def read(self, key: str) -> str | None:
        return "not json"

    def write(self, key: str, content: str) -> None:
        raise OSError("bucket unavailable")


class _UnreachableStore(FilesystemBlobStore):
    """A cache whose bucket can't be reached at all, as botocore reports a transport failure."""

    def read(self, key: str) -> str | None:
        raise EndpointConnectionError(endpoint_url="https://s3.test.invalid")

    def write(self, key: str, content: str) -> None:
        raise ConnectTimeoutError(endpoint_url="https://s3.test.invalid")


@pytest.mark.parametrize("store_type", [_BrokenStore, _UnreachableStore])
def test_a_cache_that_is_broken_or_unreachable_never_fails_the_parse(
    store_type: type[FilesystemBlobStore], tmp_path: Path
) -> None:
    router = _FakeLLMRouter()

    response = _parse("milk", router=router, tmp_path=tmp_path, cache=store_type(tmp_path))

    assert _names(response) == ["milk"]
    assert router.phrases == ["milk"]
