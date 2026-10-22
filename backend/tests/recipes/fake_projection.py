"""An in-memory projection document with object versions, for tests that must not reach S3."""

from __future__ import annotations

from dataclasses import dataclass, field

from glean.recipes.projection import ProjectionSnapshot


@dataclass
class _Object:
    """A document with a version, like an S3 object with its ETag. Version -1 means no object yet."""

    data: bytes | None = None
    version: int = field(default=-1, init=False)
    writes: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if self.data is not None:
            self.version = 0

    @property
    def etag(self) -> str | None:
        return None if self.version < 0 else f'"{self.version}"'

    def put(self, data: bytes) -> None:
        self.data = data
        self.version += 1
        self.writes += 1


class InMemoryProjectionStore:
    """One view of an in-memory projection object.

    `view()` opens a second independent view over the same object — two writers with separate caches, the
    situation that loses entries when the document is published without a version check.
    """

    def __init__(self, data: bytes | None = None, *, backing: _Object | None = None) -> None:
        self._object = backing or _Object(data=data)

    def view(self) -> InMemoryProjectionStore:
        return InMemoryProjectionStore(backing=self._object)

    @property
    def data(self) -> bytes | None:
        return self._object.data

    @property
    def writes(self) -> int:
        return self._object.writes

    @property
    def version(self) -> int:
        return self._object.version

    def read(self) -> bytes | None:
        return self._object.data

    def load(self) -> ProjectionSnapshot:
        return ProjectionSnapshot(data=self._object.data, etag=self._object.etag)

    def store(self, data: bytes, *, etag: str | None) -> bool:
        if etag != self._object.etag:
            return False
        self._object.put(data)
        return True
