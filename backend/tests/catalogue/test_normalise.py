from __future__ import annotations

import pytest

from glean.catalogue.groups import Form, GroupId
from glean.catalogue.normalise import Status, normalise
from glean.catalogue.seed import load_seed
from glean.catalogue.store import InMemoryCatalogueStore
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
