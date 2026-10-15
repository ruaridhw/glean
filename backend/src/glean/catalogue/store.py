from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from glean.catalogue.models import CatalogueItem, Source, name_key, slugify

if TYPE_CHECKING:
    from collections.abc import Iterable

    from glean.catalogue.groups import Form, GroupId


class AliasConflictError(ValueError):
    """The alias already names a different catalogue item."""


class DuplicateIdError(ValueError):
    """A different catalogue item already has this id."""


class UnknownItemError(KeyError):
    """No catalogue item has this id."""


class CatalogueStore(Protocol):
    """What normalisation (#123) needs from the catalogue. Names match case- and whitespace-insensitively."""

    def get_by_name(self, name: str) -> CatalogueItem | None:
        """The item whose canonical name or alias is *name*."""
        ...

    def shortlist(self, name: str, limit: int = 8) -> list[CatalogueItem]:
        """Up to *limit* candidate items for *name*, best first. Deterministic."""
        ...

    def upsert_alias(self, item_id: str, alias: str) -> CatalogueItem:
        """Make *alias* resolve to the item. Harmless if it already does."""
        ...

    def create_provisional(self, name: str, group: GroupId, form: Form, aliases: tuple[str, ...] = ()) -> CatalogueItem:
        """Add a provisional item (source llm). Its kind follows its group. Reuses an item that already has the name."""
        ...

    def record_unmatched(self, name: str) -> None:
        """Remember that *name*, exactly as written, was confirmed to match no catalogue item."""
        ...

    def is_unmatched(self, name: str) -> bool:
        """Whether exactly this spelling was recorded as unmatched."""
        ...

    def unmatched_names(self) -> list[str]:
        """Every recorded unmatched name, exactly as written."""
        ...


def _tokens(text: str) -> set[str]:
    # Drop a trailing plural "s" so "chickpeas" and "chickpea" share a token.
    return {token.removesuffix("s") if len(token) > 3 else token for token in name_key(text).split()}


class InMemoryCatalogueStore:
    def __init__(self, items: Iterable[CatalogueItem] = ()) -> None:
        self._items: dict[str, CatalogueItem] = {}
        self._by_key: dict[str, str] = {}
        self._unmatched: dict[str, None] = {}
        for item in items:
            self._add(item)

    def _add(self, item: CatalogueItem) -> None:
        # Validate everything before touching either index, so a refusal leaves the store as it was.
        if item.id in self._items:
            raise DuplicateIdError(item.id)
        for key in {name_key(item.name), *(name_key(alias) for alias in item.aliases)}:
            owner = self._by_key.get(key)
            if owner is not None and owner != item.id:
                raise AliasConflictError(f"{key!r} already names {owner}")
        self._items[item.id] = item
        for key in {name_key(item.name), *(name_key(alias) for alias in item.aliases)}:
            self._by_key[key] = item.id

    def get_by_name(self, name: str) -> CatalogueItem | None:
        item_id = self._by_key.get(name_key(name))
        return self._items[item_id] if item_id is not None else None

    def shortlist(self, name: str, limit: int = 8) -> list[CatalogueItem]:
        wanted = _tokens(name)
        key = name_key(name)
        scored: list[tuple[int, int, int, str, CatalogueItem]] = []
        for item in self._items.values():
            names = [item.name, *item.aliases]
            exact = any(name_key(candidate) == key for candidate in names)
            best_shared, best_extra = 0, 0
            for candidate in names:
                candidate_tokens = _tokens(candidate)
                shared = len(wanted & candidate_tokens)
                if shared > best_shared or (shared == best_shared and len(candidate_tokens) - shared < best_extra):
                    best_shared, best_extra = shared, len(candidate_tokens) - shared
            if exact or best_shared:
                scored.append((0 if exact else 1, -best_shared, best_extra, item.id, item))
        scored.sort(key=lambda row: row[:4])
        return [row[4] for row in scored[:limit]]

    def upsert_alias(self, item_id: str, alias: str) -> CatalogueItem:
        item = self._items.get(item_id)
        if item is None:
            raise UnknownItemError(item_id)
        key = name_key(alias)
        owner = self._by_key.get(key)
        if owner is not None and owner != item_id:
            raise AliasConflictError(f"{alias!r} already names {owner}")
        if owner == item_id:
            return item
        updated = item.model_copy(update={"aliases": (*item.aliases, alias.strip())})
        self._items[item_id] = updated
        self._by_key[key] = item_id
        return updated

    def create_provisional(self, name: str, group: GroupId, form: Form, aliases: tuple[str, ...] = ()) -> CatalogueItem:
        existing = self.get_by_name(name)
        if existing is not None:
            return existing
        item = CatalogueItem(
            id=self._free_id(name), name=name.strip(), aliases=aliases, group=group, form=form, source=Source.LLM
        )
        self._add(item)
        return item

    def _free_id(self, name: str) -> str:
        # Slugs are lossy ("a-b" and "a b" collide), so number the id until it is unclaimed.
        base = slugify(name)
        candidate, number = base, 1
        while candidate in self._items:
            number += 1
            candidate = f"{base}-{number}"
        return candidate

    def record_unmatched(self, name: str) -> None:
        self._unmatched[name] = None

    def is_unmatched(self, name: str) -> bool:
        return name in self._unmatched

    def unmatched_names(self) -> list[str]:
        return list(self._unmatched)
