from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from glean.config import Settings, get_settings
from glean.dependencies import verify_cognito_token
from glean.main import app

_TEST_SETTINGS = Settings(
    _env_file=None,
    openrouter_api_key="test-openrouter_api_key",
    recipe_api_key="test-recipe_api_key",
    cognito_user_pool_id="test-cognito_user_pool_id",
    cognito_app_client_id="test-cognito_app_client_id",
    s3_receipts_bucket="test-s3_receipts_bucket",
)


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    return _TEST_SETTINGS


@pytest.fixture
def client() -> TestClient:
    app.dependency_overrides[get_settings] = lambda: _TEST_SETTINGS
    app.dependency_overrides[verify_cognito_token] = lambda: "test-user-sub"
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}
