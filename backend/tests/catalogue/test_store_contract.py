"""Contract for any CatalogueStore. The DynamoDB store (#130) subclasses this with its own `store` fixture."""

from __future__ import annotations

import pytest

from glean.catalogue.groups import Form, GroupId, Kind
from glean.catalogue.models import CatalogueItem, ItemOverrides, Source
from glean.catalogue.store import (
    AliasConflictError,
    CatalogueStore,
    DuplicateIdError,
    InMemoryCatalogueStore,
    UnknownItemError,
)


def seed_items() -> list[CatalogueItem]:
    def make(name: str, group: GroupId, form: Form = Form.NOT_APPLICABLE, **kwargs: object) -> CatalogueItem:
        return CatalogueItem(id=name.replace(" ", "-"), name=name, group=group, form=form, source=Source.SEED, **kwargs)

    return [
        make("coriander", GroupId.FRESH_HERBS, aliases=("fresh coriander", "cilantro")),
        make("ground cumin", GroupId.SPICES, aliases=("cumin",)),
        make("tinned chickpeas", GroupId.BEANS_AND_PULSES, Form.TINNED_JARRED, aliases=("canned chickpeas",)),
        make("dried chickpeas", GroupId.BEANS_AND_PULSES, Form.DRIED),
        make("chickpea flour", GroupId.BAKING, aliases=("gram flour",)),
        make("toilet roll", GroupId.HOUSEHOLD, aliases=("loo roll",)),
        make("ginger", GroupId.ROOT_VEG, Form.FRESH, overrides=ItemOverrides()),
    ]


class CatalogueStoreContract:
    @pytest.fixture
    def store(self) -> CatalogueStore:
        raise NotImplementedError

    def test_finds_an_item_by_its_name(self, store: CatalogueStore) -> None:
        found = store.get_by_name("coriander")
        assert found is not None
        assert found.id == "coriander"

    def test_lookup_ignores_case_and_surrounding_whitespace(self, store: CatalogueStore) -> None:
        for spelling in ("Coriander", "  CORIANDER ", "coriander"):
            found = store.get_by_name(spelling)
            assert found is not None
            assert found.id == "coriander"

    def test_finds_an_item_by_an_alias(self, store: CatalogueStore) -> None:
        found = store.get_by_name("Fresh  Coriander")
        assert found is not None
        assert found.name == "coriander"

    def test_an_unknown_name_is_not_found(self, store: CatalogueStore) -> None:
        assert store.get_by_name("dragon fruit") is None

    def test_upserting_an_alias_makes_it_resolve(self, store: CatalogueStore) -> None:
        store.upsert_alias("coriander", "Tesco Fresh Cut Coriander 30g")
        found = store.get_by_name("tesco fresh cut coriander 30g")
        assert found is not None
        assert found.id == "coriander"
        assert "Tesco Fresh Cut Coriander 30g" in found.aliases

    def test_upserting_the_same_alias_twice_is_harmless(self, store: CatalogueStore) -> None:
        store.upsert_alias("coriander", "coriander bunch")
        store.upsert_alias("coriander", "Coriander Bunch")
        found = store.get_by_name("coriander")
        assert found is not None
        assert [a.casefold() for a in found.aliases].count("coriander bunch") == 1

    def test_an_alias_that_belongs_to_another_item_is_refused(self, store: CatalogueStore) -> None:
        with pytest.raises(AliasConflictError):
            store.upsert_alias("dried-chickpeas", "canned chickpeas")
        with pytest.raises(AliasConflictError):
            store.upsert_alias("coriander", "Ground Cumin")

    def test_an_alias_for_an_unknown_item_is_refused(self, store: CatalogueStore) -> None:
        with pytest.raises(UnknownItemError):
            store.upsert_alias("no-such-item", "whatever")

    def test_shortlist_puts_the_exact_match_first(self, store: CatalogueStore) -> None:
        assert store.shortlist("tinned chickpeas")[0].id == "tinned-chickpeas"

    def test_shortlist_finds_candidates_sharing_words_with_the_name(self, store: CatalogueStore) -> None:
        ids = [candidate.id for candidate in store.shortlist("organic chickpeas 400g")]
        assert {"tinned-chickpeas", "dried-chickpeas", "chickpea-flour"} <= set(ids)
        assert "toilet-roll" not in ids

    def test_shortlist_is_limited_and_deterministic(self, store: CatalogueStore) -> None:
        first = store.shortlist("chickpeas", limit=2)
        assert len(first) == 2
        assert [i.id for i in first] == [i.id for i in store.shortlist("chickpeas", limit=2)]

    def test_shortlist_of_nonsense_is_empty(self, store: CatalogueStore) -> None:
        assert store.shortlist("zzqx") == []

    def test_creating_a_provisional_ingredient(self, store: CatalogueStore) -> None:
        created = store.create_provisional("Dragon Fruit", GroupId.TROPICAL_FRUIT, Form.FRESH, aliases=("pitaya",))
        assert created.source is Source.LLM
        assert created.kind is Kind.INGREDIENT
        found = store.get_by_name("pitaya")
        assert found is not None
        assert found.id == created.id

    def test_a_provisional_item_in_a_household_group_is_a_household_item(self, store: CatalogueStore) -> None:
        created = store.create_provisional("birthday candles", GroupId.HOUSEHOLD, Form.NOT_APPLICABLE)
        assert created.kind is Kind.HOUSEHOLD

    def test_creating_a_provisional_item_for_a_known_name_reuses_the_existing_item(self, store: CatalogueStore) -> None:
        created = store.create_provisional("Cumin", GroupId.SPICES, Form.NOT_APPLICABLE)
        assert created.id == "ground-cumin"
        assert created.source is Source.SEED

    def test_recording_unmatched_marks_the_name_without_creating_an_item(self, store: CatalogueStore) -> None:
        assert not store.is_unmatched("Corriandr")
        store.record_unmatched("Corriandr")
        assert store.is_unmatched("Corriandr")
        assert store.get_by_name("Corriandr") is None
        assert not store.is_unmatched("coriander")

    def test_names_whose_slugs_collide_get_distinct_ids(self, store: CatalogueStore) -> None:
        first = store.create_provisional("a-b", GroupId.HOUSEHOLD, Form.NOT_APPLICABLE, aliases=("ab thing",))
        second = store.create_provisional("a b", GroupId.SPICES, Form.NOT_APPLICABLE)
        assert first.id != second.id

    def test_a_slug_collision_does_not_disturb_the_existing_item(self, store: CatalogueStore) -> None:
        first = store.create_provisional("a-b", GroupId.HOUSEHOLD, Form.NOT_APPLICABLE, aliases=("ab thing",))
        second = store.create_provisional("a b", GroupId.SPICES, Form.NOT_APPLICABLE)
        by_name = store.get_by_name("a-b")
        assert by_name is not None
        assert (by_name.id, by_name.kind) == (first.id, Kind.HOUSEHOLD)
        by_alias = store.get_by_name("ab thing")
        assert by_alias is not None
        assert by_alias.id == first.id
        other = store.get_by_name("a b")
        assert other is not None
        assert other.id == second.id

    def test_a_failed_creation_leaves_no_trace(self, store: CatalogueStore) -> None:
        with pytest.raises(AliasConflictError):
            store.create_provisional("fresh thing", GroupId.SPICES, Form.NOT_APPLICABLE, aliases=("cilantro",))
        assert store.get_by_name("fresh thing") is None
        cilantro = store.get_by_name("cilantro")
        assert cilantro is not None
        assert cilantro.id == "coriander"
        retry = store.create_provisional("fresh thing", GroupId.SPICES, Form.NOT_APPLICABLE)
        assert retry.id == "fresh-thing"


class TestInMemoryCatalogueStore(CatalogueStoreContract):
    @pytest.fixture
    def store(self) -> CatalogueStore:
        return InMemoryCatalogueStore(seed_items())

    def test_duplicate_ids_at_construction_are_refused(self) -> None:
        items = seed_items()
        twin = items[0].model_copy(update={"name": "different name", "aliases": ()})
        with pytest.raises(DuplicateIdError):
            InMemoryCatalogueStore([*items, twin])
