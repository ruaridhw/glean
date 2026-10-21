"""An in-memory projection document, for tests that must not reach S3."""

from __future__ import annotations


class InMemoryProjectionStore:
    def __init__(self, data: bytes | None = None) -> None:
        self.data = data
        self.writes = 0

    def read(self) -> bytes | None:
        return self.data

    def write(self, data: bytes) -> None:
        self.data = data
        self.writes += 1
