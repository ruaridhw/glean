from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from glean.catalogue.groups import Form, GroupId, Kind
from glean.catalogue.models import Source
from glean.catalogue.normalise import ItemKind, NormalisedName, Status, normalise
from glean.catalogue.seed import load_seed
from glean.catalogue.store import InMemoryCatalogueStore
from glean.decisions import DecisionTimeoutError
from glean.llm import Feature
from tests.catalogue.normalise_fakes import FakeDecisions, FakeRouter, decision


@pytest.fixture
def store() -> InMemoryCatalogueStore:
    return InMemoryCatalogueStore(load_seed().items)


def no_decisions() -> FakeDecisions:
    def fail(name: str, questions: object) -> object:
        raise AssertionError(f"unexpected model call for {name!r}")

    return FakeDecisions(script=fail)  # ty: ignore[invalid-argument-type]


def test_a_known_name_or_alias_resolves_from_the_catalogue_without_a_model_call(
    store: InMemoryCatalogueStore,
) -> None:
    decisions = no_decisions()

    [by_name, by_alias] = normalise(
        ["Coriander", "cilantro"], store=store, decisions=decisions, llm_router=FakeRouter()
    )

    assert (by_name.status, by_name.source, by_name.canonical_name) == (Status.MATCHED, "cache", "coriander")
    assert by_alias.catalogue_item_id == by_name.catalogue_item_id == "coriander"
    assert by_name.ingredient_group is GroupId.FRESH_HERBS
    assert by_name.confidence == 1.0
    assert decisions.calls == []


def test_a_confident_decision_match_stores_the_input_as_an_alias_so_the_next_call_needs_no_model(
    store: InMemoryCatalogueStore,
) -> None:
    raw = "Tesco Fresh Cut Coriander 30g"
    decisions = FakeDecisions(
        script=lambda name, questions: decision(
            questions, match={"coriander": 0.93}, group=GroupId.FRESH_HERBS, form=Form.NOT_APPLICABLE, perishable=0.9
        )
    )

    [first] = normalise([raw], store=store, decisions=decisions, llm_router=FakeRouter())
    [second] = normalise([raw], store=store, decisions=decisions, llm_router=FakeRouter())

    assert (first.status, first.source, first.catalogue_item_id) == (Status.MATCHED, "decision", "coriander")
    assert first.ingredient_group is GroupId.FRESH_HERBS
    assert first.perishable is True
    assert first.confidence == pytest.approx(0.93)
    assert (second.status, second.source, second.catalogue_item_id) == (Status.MATCHED, "cache", "coriander")
    assert len(decisions.calls) == 1


def naming(**canonical_by_input: str | None):
    """A scripted naming reply: input -> canonical name (None = can't be identified)."""

    def reply(schema: type, messages: object) -> object:
        return schema(names=[{"input": raw, "canonical_name": name} for raw, name in canonical_by_input.items()])

    return reply


def unseen(group: GroupId, form: Form = Form.NOT_APPLICABLE) -> FakeDecisions:
    return FakeDecisions(script=lambda name, questions: decision(questions, group=group, form=form))


def test_one_batched_naming_call_creates_provisional_items_for_every_miss(store: InMemoryCatalogueStore) -> None:
    router = FakeRouter(
        script=naming(**{"Tesco Lemongrass Stalks 40g": "lemongrass", "Dragon Fruit Each": "dragon fruit"})
    )
    decisions = FakeDecisions(
        script=lambda name, questions: decision(
            questions,
            group=GroupId.FRESH_HERBS if "Lemongrass" in name else GroupId.FRUIT,
            form=Form.FRESH if "Dragon" in name else Form.NOT_APPLICABLE,
        )
    )

    results = normalise(
        ["Tesco Lemongrass Stalks 40g", "Dragon Fruit Each"], store=store, decisions=decisions, llm_router=router
    )

    assert [(r.status, r.source, r.canonical_name) for r in results] == [
        (Status.CREATED, "llm", "lemongrass"),
        (Status.CREATED, "llm", "dragon fruit"),
    ]
    assert len(router.calls) == 1
    assert router.calls[0]["feature"] is Feature.INGREDIENT_NORMALISATION
    created = store.get_by_name("Dragon Fruit Each")
    assert created is not None
    assert (created.source, created.group, created.form) == (Source.LLM, GroupId.FRUIT, Form.FRESH)
    assert "Dragon Fruit Each" in created.aliases


def test_a_created_name_is_found_in_the_catalogue_next_time_with_no_model_call(
    store: InMemoryCatalogueStore,
) -> None:
    router = FakeRouter(script=naming(**{"Dragon Fruit Each": "dragon fruit"}))
    normalise(["Dragon Fruit Each"], store=store, decisions=unseen(GroupId.FRUIT, Form.FRESH), llm_router=router)

    [again] = normalise(["Dragon Fruit Each"], store=store, decisions=no_decisions(), llm_router=FakeRouter())

    assert (again.status, again.source, again.canonical_name) == (Status.MATCHED, "cache", "dragon fruit")


def test_a_match_below_the_threshold_counts_as_no_match(store: InMemoryCatalogueStore) -> None:
    decisions = FakeDecisions(
        script=lambda name, questions: decision(questions, match={"coriander": 0.4}, group=GroupId.FRESH_HERBS)
    )
    router = FakeRouter(script=naming(**{"Thai basil": "thai basil"}))

    [result] = normalise(["Thai basil"], store=store, decisions=decisions, llm_router=router)

    assert (result.status, result.canonical_name) == (Status.CREATED, "thai basil")
    assert store.get_by_name("Thai basil") is not None
    assert store.get_by_name("Thai basil").id != "coriander"  # ty: ignore[unresolved-attribute]


def test_a_household_item_is_never_matched_to_a_food_and_a_food_never_to_a_household_item(
    store: InMemoryCatalogueStore,
) -> None:
    decisions = FakeDecisions(
        script=lambda name, questions: decision(questions, match={"coriander": 0.95}, group=GroupId.HOUSEHOLD)
    )
    router = FakeRouter(script=naming(**{"Coriander Scented Candle": "coriander scented candle"}))

    [result] = normalise(["Coriander Scented Candle"], store=store, decisions=decisions, llm_router=router)

    assert result.status is Status.CREATED
    assert result.catalogue_item_id != "coriander"


def test_a_created_item_follows_its_group_so_birthday_candles_is_a_household_item(
    store: InMemoryCatalogueStore,
) -> None:
    router = FakeRouter(script=naming(**{"Birthday Candles": "birthday candles"}))

    [
        candles,
    ] = normalise(["Birthday Candles"], store=store, decisions=unseen(GroupId.HOUSEHOLD), llm_router=router)

    assert candles.status is Status.CREATED
    assert candles.kind is ItemKind.HOUSEHOLD_ITEM
    assert candles.ingredient_group is GroupId.HOUSEHOLD
    assert candles.canonical_name == "birthday candles"
    assert store.get_by_name("birthday candles").kind is Kind.HOUSEHOLD  # ty: ignore[unresolved-attribute]


def test_a_name_that_cannot_be_identified_is_unmatched_once_naming_succeeds_and_stays_unmatched(
    store: InMemoryCatalogueStore,
) -> None:
    router = FakeRouter(script=naming(asdkjh=None))

    [first] = normalise(["asdkjh"], store=store, decisions=unseen(GroupId.OTHER), llm_router=router)
    [second] = normalise(["asdkjh"], store=store, decisions=no_decisions(), llm_router=FakeRouter())

    assert (first.status, first.input, first.canonical_name, first.catalogue_item_id) == (
        Status.UNMATCHED,
        "asdkjh",
        "asdkjh",
        None,
    )
    assert (second.status, second.source) == (Status.UNMATCHED, "cache")
    assert store.is_unmatched("asdkjh")


def failing_naming(error: Exception):
    def reply(schema: type, messages: object) -> object:
        raise error

    return reply


@pytest.mark.parametrize("error", [RuntimeError("provider outage"), TimeoutError("naming timed out")])
def test_a_naming_failure_leaves_the_names_unresolved_with_nothing_stored_and_the_next_call_recovers(
    store: InMemoryCatalogueStore, error: Exception
) -> None:
    before = {item.id for item in store.shortlist("dragon fruit", 50)}
    broken = FakeRouter(script=failing_naming(error))

    [down] = normalise(
        ["Dragon Fruit Each"], store=store, decisions=unseen(GroupId.FRUIT, Form.FRESH), llm_router=broken
    )

    assert (down.status, down.input, down.canonical_name, down.catalogue_item_id) == (
        Status.UNRESOLVED,
        "Dragon Fruit Each",
        "Dragon Fruit Each",
        None,
    )
    assert store.get_by_name("Dragon Fruit Each") is None
    assert not store.is_unmatched("Dragon Fruit Each")
    assert {item.id for item in store.shortlist("dragon fruit", 50)} == before

    restored = FakeRouter(script=naming(**{"Dragon Fruit Each": "dragon fruit"}))
    [up] = normalise(
        ["Dragon Fruit Each"], store=store, decisions=unseen(GroupId.FRUIT, Form.FRESH), llm_router=restored
    )
    assert (up.status, up.canonical_name) == (Status.CREATED, "dragon fruit")


def test_an_exhausted_naming_budget_skips_the_call_and_leaves_misses_unresolved(store: InMemoryCatalogueStore) -> None:
    router = FakeRouter(script=naming(**{"Dragon Fruit Each": "dragon fruit"}))

    [result] = normalise(
        ["Dragon Fruit Each"],
        store=store,
        decisions=unseen(GroupId.FRUIT, Form.FRESH),
        llm_router=router,
        naming_budget_s=0,
    )

    assert result.status is Status.UNRESOLVED
    assert router.calls == []
    assert store.get_by_name("Dragon Fruit Each") is None


def test_the_naming_call_is_bounded_by_the_time_left(store: InMemoryCatalogueStore) -> None:
    router = FakeRouter(script=naming(**{"Dragon Fruit Each": "dragon fruit"}))

    normalise(
        ["Dragon Fruit Each"],
        store=store,
        decisions=unseen(GroupId.FRUIT, Form.FRESH),
        llm_router=router,
        naming_budget_s=2.0,
    )

    assert 0 < router.calls[0]["kwargs"]["request_timeout"] <= 2000


def test_a_name_the_llm_skipped_is_unresolved_not_unmatched(store: InMemoryCatalogueStore) -> None:
    router = FakeRouter(script=naming(**{"Dragon Fruit Each": "dragon fruit"}))

    [named, skipped] = normalise(
        ["Dragon Fruit Each", "Lychee Tin"], store=store, decisions=unseen(GroupId.FRUIT), llm_router=router
    )

    assert (named.status, skipped.status) == (Status.CREATED, Status.UNRESOLVED)
    assert not store.is_unmatched("Lychee Tin")


def test_a_failed_decision_request_leaves_only_that_name_unresolved(store: InMemoryCatalogueStore) -> None:
    def script(name: str, questions: object) -> object:
        if "Broken" in name:
            raise DecisionTimeoutError("slow")
        return decision(questions, group=GroupId.FRUIT, form=Form.FRESH)  # ty: ignore[invalid-argument-type]

    router = FakeRouter(script=naming(**{"Dragon Fruit Each": "dragon fruit"}))

    [good, bad] = normalise(
        ["Dragon Fruit Each", "Broken Thing"], store=store, decisions=FakeDecisions(script=script), llm_router=router
    )

    assert (good.status, bad.status) == (Status.CREATED, Status.UNRESOLVED)
    assert store.get_by_name("Broken Thing") is None


def test_two_concurrent_calls_for_the_same_new_name_create_one_item(store: InMemoryCatalogueStore) -> None:
    both_naming = threading.Barrier(2, timeout=5)

    def slow_naming(schema: type, messages: object) -> object:
        both_naming.wait()  # each call is naming "dragon fruit" before either has written
        return naming(**{"Dragon Fruit Each": "dragon fruit"})(schema, messages)

    def call() -> NormalisedName:
        [result] = normalise(
            ["Dragon Fruit Each"],
            store=store,
            decisions=unseen(GroupId.FRUIT, Form.FRESH),
            llm_router=FakeRouter(script=slow_naming),
        )
        return result

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.map(lambda _: call(), range(2))

    assert first.catalogue_item_id == second.catalogue_item_id
    assert sum(1 for item in store.shortlist("dragon fruit", 50) if item.name == "dragon fruit") == 1


def test_more_than_twenty_names_are_rejected_and_twenty_new_names_are_all_resolved(
    store: InMemoryCatalogueStore,
) -> None:
    names = [f"Mystery Fruit {letter}" for letter in "abcdefghijklmnopqrst"]
    router = FakeRouter(script=naming(**{raw: raw.lower() for raw in names}))

    with pytest.raises(ValueError, match="At most 20"):
        normalise([*names, "one more"], store=store, decisions=no_decisions(), llm_router=router)
    results = normalise(names, store=store, decisions=unseen(GroupId.FRUIT, Form.FRESH), llm_router=router)

    assert [r.status for r in results] == [Status.CREATED] * 20
    assert len(router.calls) == 1


def test_normalise_leaves_no_work_running_after_it_returns(store: InMemoryCatalogueStore) -> None:
    threads_before = threading.active_count()

    normalise(
        ["Dragon Fruit Each", "Lychee Tin"],
        store=store,
        decisions=unseen(GroupId.FRUIT, Form.FRESH),
        llm_router=FakeRouter(script=naming(**{"Dragon Fruit Each": "dragon fruit", "Lychee Tin": "lychee"})),
    )

    assert threading.active_count() == threads_before


def test_repeated_names_in_one_call_cost_one_decision_and_keep_each_spelling(store: InMemoryCatalogueStore) -> None:
    decisions = unseen(GroupId.FRUIT, Form.FRESH)
    router = FakeRouter(script=naming(**{"Dragon Fruit Each": "dragon fruit"}))

    results = normalise(
        ["Dragon Fruit Each", "dragon  fruit each", "coriander"], store=store, decisions=decisions, llm_router=router
    )

    assert [r.input for r in results] == ["Dragon Fruit Each", "dragon  fruit each", "coriander"]
    assert results[0].catalogue_item_id == results[1].catalogue_item_id
    assert len(decisions.calls) == 1
