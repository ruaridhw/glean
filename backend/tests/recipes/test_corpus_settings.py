"""`RECIPE_STORE` picks the corpus store (F1/#162), and a broken deployment fails loudly instead of empty."""

from __future__ import annotations

from typing import Any

import pytest

from glean import config
from glean.recipes import corpus, projection
from glean.recipes.dynamo_corpus import DynamoCorpusBackend
from glean.recipes.projection import S3ProjectionStore
from tests.conftest import RECIPES_TABLE_NAME


@pytest.fixture(autouse=True)
def _cold_backend_caches() -> Any:
    corpus._dynamo_corpus_backend.cache_clear()
    projection.get_projection_store.cache_clear()
    yield
    corpus._dynamo_corpus_backend.cache_clear()
    projection.get_projection_store.cache_clear()


def _settings(**overrides: Any) -> config.Settings:
    return config.Settings(
        _env_file=None,
        openrouter_api_key="test-openrouter_api_key",
        recipe_api_key="test-recipe_api_key",
        cognito_user_pool_id="test-cognito_user_pool_id",
        cognito_app_client_id="test-cognito_app_client_id",
        s3_receipts_bucket="test-s3_receipts_bucket",
        s3_recipe_cache_bucket="glean-recipe-cache-test",
        **overrides,
    )


def test_the_setting_defaults_to_the_blob_corpus() -> None:
    assert _settings().recipe_store == "blobs"


def test_an_unknown_recipe_store_is_rejected() -> None:
    with pytest.raises(ValueError, match="recipe_store"):
        _settings(recipe_store="s3")


def test_recipe_store_dynamo_opens_the_table_and_its_projection(
    recipes_table: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        config, "get_settings", lambda: _settings(recipe_store="dynamo", recipes_table=RECIPES_TABLE_NAME)
    )

    store = corpus.RecipeCorpusStore().store

    assert isinstance(store, DynamoCorpusBackend)
    assert isinstance(store._projections, S3ProjectionStore)


def test_recipe_store_dynamo_without_a_table_names_the_missing_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "get_settings", lambda: _settings(recipe_store="dynamo"))

    with pytest.raises(corpus.CorpusStoreError, match="RECIPES_TABLE"):
        corpus.RecipeCorpusStore()


def test_the_blob_path_costs_no_dynamodb_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "get_settings", lambda: _settings())

    assert isinstance(corpus.RecipeCorpusStore().store, corpus.BlobCorpusBackend)


def test_a_process_without_deployment_settings_stays_on_the_blob_path(monkeypatch: pytest.MonkeyPatch) -> None:
    # A script or test that never configures the backend still gets the default store, not a crash.
    monkeypatch.setattr(config, "get_settings", lambda: config.Settings(_env_file=None))

    assert isinstance(corpus.RecipeCorpusStore().store, corpus.BlobCorpusBackend)
