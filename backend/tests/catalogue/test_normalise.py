from __future__ import annotations

import pytest

from glean.catalogue.groups import Form, GroupId, Kind
from glean.catalogue.models import Source
from glean.catalogue.normalise import ItemKind, Status, normalise
from glean.catalogue.seed import load_seed
from glean.catalogue.store import InMemoryCatalogueStore
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
