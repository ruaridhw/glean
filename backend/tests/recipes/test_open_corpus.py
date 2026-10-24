"""The scripts' one switch between the blob corpus and the DynamoDB store (F1/#162)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from glean.recipe_api.blob_store import S3BlobStore
from glean.recipes.corpus import BlobCorpusBackend, open_corpus, projection_store_for
from glean.recipes.dynamo_corpus import DynamoCorpusBackend
from glean.recipes.projection import FilesystemProjectionStore, S3ProjectionStore
from tests.conftest import RECIPES_TABLE_NAME
from tests.recipes.corpus_fixtures import synthetic_recipe

if TYPE_CHECKING:
    from pathlib import Path


def test_without_a_table_the_scripts_read_the_blob_corpus(tmp_path: Path) -> None:
    corpus = open_corpus(cache_dir=tmp_path)
    recipe = synthetic_recipe("rec_x", title="X", ingredients=["rice"])

    corpus.save(recipe)

    assert isinstance(corpus.store, BlobCorpusBackend)
    assert (tmp_path / "corpus" / "_unknown" / "rec_x.json").exists()
    assert corpus.get("rec_x") == recipe


def test_a_corpus_dir_overrides_where_the_blobs_live(tmp_path: Path) -> None:
    # import_recipe_corpus.py's --cache-dir is the corpus directory itself, not a cache root.
    corpus = open_corpus(cache_dir=tmp_path, corpus_dir=tmp_path)

    corpus.save(synthetic_recipe("rec_x", title="X", ingredients=["rice"]))

    assert (tmp_path / "_unknown" / "rec_x.json").exists()


def test_a_bucket_is_the_corpus_prefix() -> None:
    with_bucket = open_corpus(bucket="glean-recipe-cache-test").store

    assert isinstance(with_bucket, BlobCorpusBackend)
    assert isinstance(with_bucket.blobs, S3BlobStore)


def test_with_a_table_the_scripts_write_the_dynamo_store(recipes_table: Any, tmp_path: Path) -> None:
    corpus = open_corpus(table=RECIPES_TABLE_NAME, cache_dir=tmp_path)
    recipe = synthetic_recipe("rec_x", title="X", ingredients=["rice"], source_url="https://example.com/x")

    corpus.save(recipe)

    assert isinstance(corpus.store, DynamoCorpusBackend)
    assert corpus.get("rec_x") == recipe
    assert corpus.get_by_source_url("https://example.com/x") == recipe


def test_the_projection_lives_where_the_script_says(tmp_path: Path) -> None:
    assert isinstance(projection_store_for(bucket="glean-recipe-cache-test"), S3ProjectionStore)
    assert isinstance(projection_store_for(cache_dir=tmp_path), FilesystemProjectionStore)
