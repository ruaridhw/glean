from __future__ import annotations

import pytest

import glean.config as _config

# Replace the module-level singleton BEFORE importing any app module.
# Service modules that do `from glean.config import settings` at collection
# time will see this fake object.
_TEST_SETTINGS = _config.Settings(
    openrouter_api_key="test-openrouter_api_key",
    recipe_api_key="test-recipe_api_key",
    cognito_user_pool_id="test-cognito_user_pool_id",
    cognito_app_client_id="test-cognito_app_client_id",
    s3_receipts_bucket="test-s3_receipts_bucket",
)
_config.settings = _TEST_SETTINGS

from fastapi.testclient import TestClient

from glean.dependencies import verify_cognito_token
from glean.main import app


@pytest.fixture(scope="session")
def test_settings() -> _config.Settings:
    return _TEST_SETTINGS


@pytest.fixture
def client() -> TestClient:
    app.dependency_overrides[verify_cognito_token] = lambda: "test-user-sub"
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}
