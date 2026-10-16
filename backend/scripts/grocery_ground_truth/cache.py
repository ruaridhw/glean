"""Disk cache of the products read for a (retailer, query), so audit re-runs cost no browser requests."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, ValidationError

from .models import Product  # noqa: TC001  (pydantic resolves the field type at runtime)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


CACHE_FORMAT = 2


class CacheEntry(BaseModel):
    format: int = Field(description="Bumped when what an entry means changes, so older entries are read again.")
    retailer: str = Field(description="The retailer the products were read from.")
    query: str = Field(description="The search text the products were found by.")
    requested: int = Field(description="How many products the read asked for, so a later, larger ask re-reads.")
    fetched_at: datetime = Field(description="When the pages were read.")
    products: list[Product] = Field(description="The products read, in search order.")


class ProductCache:
    def __init__(
        self,
        directory: Path,
        *,
        max_age: timedelta = timedelta(days=30),
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._directory = directory
        self._max_age = max_age
        self._clock = clock

    def _path(self, retailer: str, query: str) -> Path:
        digest = hashlib.sha256(query.encode()).hexdigest()[:16]
        return self._directory / f"{retailer}-{digest}.json"

    def get(self, retailer: str, query: str, n: int) -> list[Product] | None:
        """The first `n` cached products, or None when there is no entry, it is stale or it asked for fewer."""
        path = self._path(retailer, query)
        if not path.exists():
            return None
        try:
            entry = CacheEntry.model_validate_json(path.read_text())
        except ValidationError:
            return None
        if entry.format != CACHE_FORMAT or self._clock() - entry.fetched_at > self._max_age or entry.requested < n:
            return None
        return entry.products[:n]

    def put(self, retailer: str, query: str, n: int, products: list[Product]) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        entry = CacheEntry(
            format=CACHE_FORMAT,
            retailer=retailer,
            query=query,
            requested=n,
            fetched_at=self._clock(),
            products=products,
        )
        self._path(retailer, query).write_text(entry.model_dump_json(indent=1))
