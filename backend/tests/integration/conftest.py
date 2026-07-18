from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from dotenv import dotenv_values, find_dotenv, load_dotenv

import glean.config as _config
from glean.llm import Feature, LLMRouter

if TYPE_CHECKING:
    from pydantic import SecretStr

pytestmark = pytest.mark.integration

# find_dotenv() walks upward from cwd (backend/) and finds backend/.env when
# credentialed integration tests need it.
_ENV_PATH = find_dotenv()
_ENV = dotenv_values(_ENV_PATH) if _ENV_PATH else {}
# Also export backend/.env into os.environ (without clobbering real shell vars) so
# os.environ-based knobs — GLEAN_EVAL_MODEL, GLEAN_JUDGE_MODEL, GLEAN_VISION_RECEIPT_IMAGE,
# GLEAN_LIVE_RECIPE_URL — can be driven from .env rather than only shell exports.
if _ENV_PATH:
    load_dotenv(_ENV_PATH, override=False)


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
        recipe_api_key=_ENV.get("RECIPE_API_KEY", "test-recipe_api_key"),
        cognito_user_pool_id=_ENV.get("COGNITO_USER_POOL_ID", "test-cognito_user_pool_id"),
        cognito_app_client_id=_ENV.get("COGNITO_APP_CLIENT_ID", "test-cognito_app_client_id"),
        s3_receipts_bucket=_ENV.get("S3_RECEIPTS_BUCKET", "test-s3_receipts_bucket"),
    )


@pytest.fixture(scope="session")
def openrouter_api_key(test_settings: _config.Settings) -> SecretStr:
    return test_settings.openrouter_api_key


@pytest.fixture(scope="session")
def openrouter_smoke_model(test_settings: _config.Settings) -> str:
    return LLMRouter.from_settings(test_settings).model_id_for(Feature.SHOPPING_LIST_DESCRIPTION)
