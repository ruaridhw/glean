from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from dotenv import dotenv_values, find_dotenv

import glean.config as _config

if TYPE_CHECKING:
    from pydantic import SecretStr

pytestmark = pytest.mark.integration

# find_dotenv() walks upward from cwd (backend/) and finds backend/.env.
_ENV = dotenv_values(find_dotenv(raise_error_if_not_found=True))


@pytest.fixture(scope="session")
def test_settings() -> _config.Settings:
    """Override test_settings with real credentials from backend/.env.

    Skips the entire integration suite if the key is absent or not a real
    sk-or-... key.
    """
    key = _ENV.get("OPENROUTER_API_KEY")
    if not key or not key.startswith("sk-or-"):
        pytest.skip("No real OPENROUTER_API_KEY found in backend/.env (expected sk-or-... prefix)")
    return _config.Settings(
        openrouter_api_key=key,
        llm_model=_ENV.get("LLM_MODEL", "google/gemma-4-26b-a4b-it:free"),
        recipe_api_key=_ENV.get("RECIPE_API_KEY", "test-recipe_api_key"),
        cognito_user_pool_id=_ENV.get("COGNITO_USER_POOL_ID", "test-cognito_user_pool_id"),
        cognito_app_client_id=_ENV.get("COGNITO_APP_CLIENT_ID", "test-cognito_app_client_id"),
        s3_receipts_bucket=_ENV.get("S3_RECEIPTS_BUCKET", "test-s3_receipts_bucket"),
    )


@pytest.fixture(scope="session")
def openrouter_api_key(test_settings: _config.Settings) -> SecretStr:
    return test_settings.openrouter_api_key


@pytest.fixture(scope="session")
def llm_model(test_settings: _config.Settings) -> str:
    return test_settings.llm_model
