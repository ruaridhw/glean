from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pytest
from botocore.exceptions import ClientError

from glean.recipe_api import blob_store
from glean.recipe_api.blob_store import (
    FilesystemBlobStore,
    S3BlobStore,
    get_recipe_cache_store,
    get_recipe_corpus_store,
)

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# FilesystemBlobStore
# ---------------------------------------------------------------------------


def test_filesystem_write_read_roundtrip(tmp_path: Path) -> None:
    store = FilesystemBlobStore(tmp_path)
    store.write("ns/key.json", '{"a": 1}')
    assert store.read("ns/key.json") == '{"a": 1}'
    assert (tmp_path / "ns" / "key.json").exists()


def test_filesystem_read_missing_returns_none(tmp_path: Path) -> None:
    assert FilesystemBlobStore(tmp_path).read("missing.json") is None


def test_filesystem_list_keys_filters_by_prefix_and_extension(tmp_path: Path) -> None:
    store = FilesystemBlobStore(tmp_path)
    store.write("corpus/a.json", "{}")
    store.write("corpus/sub/b.json", "{}")
    store.write("search_x.json", "{}")
    (tmp_path / "notes.txt").write_text("ignore me")

    assert store.list_keys("corpus/") == ["corpus/a.json", "corpus/sub/b.json"]
    assert "search_x.json" in store.list_keys()


# ---------------------------------------------------------------------------
# S3BlobStore (against a fake boto3 client)
# ---------------------------------------------------------------------------


class _FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def get_object(self, *, Bucket: str, Key: str) -> dict:
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        return {"Body": io.BytesIO(self.objects[Key])}

    def put_object(self, *, Bucket: str, Key: str, Body: bytes) -> None:
        self.objects[Key] = Body

    def get_paginator(self, name: str) -> _FakeS3Client._FakePaginator:
        return self._FakePaginator(self.objects)

    class _FakePaginator:
        def __init__(self, objects: dict[str, bytes]) -> None:
            self._objects = objects

        def paginate(self, *, Bucket: str, Prefix: str):
            yield {"Contents": [{"Key": k} for k in self._objects if k.startswith(Prefix)]}


@pytest.fixture
def fake_s3(monkeypatch: pytest.MonkeyPatch) -> _FakeS3Client:
    client = _FakeS3Client()
    monkeypatch.setattr("boto3.client", lambda *args, **kwargs: client)
    return client


def test_s3_write_read_roundtrip_applies_prefix(fake_s3: _FakeS3Client) -> None:
    store = S3BlobStore("bucket", region="eu-west-2", prefix="corpus/")
    store.write("ns/key.json", '{"a": 1}')

    assert fake_s3.objects == {"corpus/ns/key.json": b'{"a": 1}'}
    assert store.read("ns/key.json") == '{"a": 1}'


def test_s3_read_missing_returns_none(fake_s3: _FakeS3Client) -> None:
    assert S3BlobStore("bucket", region="eu-west-2").read("missing.json") is None


def test_s3_list_keys_strips_prefix_and_filters_extension(fake_s3: _FakeS3Client) -> None:
    store = S3BlobStore("bucket", region="eu-west-2", prefix="corpus/")
    store.write("a.json", "{}")
    store.write("sub/b.json", "{}")
    fake_s3.objects["corpus/not-json.txt"] = b"x"

    assert store.list_keys() == ["a.json", "sub/b.json"]


# ---------------------------------------------------------------------------
# Environment-selected factory
# ---------------------------------------------------------------------------


class _Settings:
    def __init__(self, bucket: str) -> None:
        self.s3_recipe_cache_bucket = bucket
        self.aws_region = "eu-west-2"


@pytest.fixture(autouse=True)
def _clear_store_caches() -> None:
    get_recipe_cache_store.cache_clear()
    get_recipe_corpus_store.cache_clear()


def test_factory_uses_filesystem_without_a_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("glean.config.get_settings", lambda: _Settings(""))
    assert isinstance(get_recipe_cache_store(), FilesystemBlobStore)
    assert isinstance(get_recipe_corpus_store(), FilesystemBlobStore)


def test_factory_uses_s3_when_bucket_configured(monkeypatch: pytest.MonkeyPatch, fake_s3: _FakeS3Client) -> None:
    monkeypatch.setattr("glean.config.get_settings", lambda: _Settings("glean-recipe-cache-prod"))
    cache = get_recipe_cache_store()
    corpus = get_recipe_corpus_store()

    assert isinstance(cache, S3BlobStore)
    assert isinstance(corpus, S3BlobStore)
    # corpus is namespaced under a "corpus/" prefix; the HTTP cache sits at the root.
    corpus.write("x.json", "{}")
    assert "corpus/x.json" in fake_s3.objects


def test_blob_store_module_exposes_default_cache_dir() -> None:
    assert blob_store.DEFAULT_CACHE_DIR.name == "glean_recipe_cache"
