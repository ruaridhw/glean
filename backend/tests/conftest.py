from __future__ import annotations

from typing import TYPE_CHECKING

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from glean.config import Settings, get_settings
from glean.dependencies import verify_cognito_token
from glean.main import app
from glean.rate_limit import limiter
from glean.screening import clear_screen_cache
from tests.infra.cfn import recipes_table_properties

if TYPE_CHECKING:
    from collections.abc import Iterator

RECIPES_TABLE_NAME = "glean-recipes-test"
_REGION = "eu-west-2"
# CloudFormation-only properties that create_table does not take.
_CFN_ONLY = {"TableName", "TableClass", "PointInTimeRecoverySpecification"}

_TEST_SETTINGS = Settings(
    _env_file=None,
    openrouter_api_key="test-openrouter_api_key",
    recipe_api_key="test-recipe_api_key",
    cognito_user_pool_id="test-cognito_user_pool_id",
    cognito_app_client_id="test-cognito_app_client_id",
    s3_receipts_bucket="test-s3_receipts_bucket",
    # Agent sessions run in the request against the in-memory store and saver: no AWS, no queue.
    agent_runner="inline",
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


@pytest.fixture(autouse=True)
def _fresh_rate_limit_window() -> None:
    limiter.reset()


@pytest.fixture(autouse=True)
def _cold_screen_cache() -> Iterator[None]:
    """The screen's cache lives on the module, so a test must never inherit another test's answers."""
    clear_screen_cache()
    yield
    clear_screen_cache()


@pytest.fixture
def recipes_table():
    """The recipes table exactly as template.yaml defines it, in moto."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name=_REGION)
        props = {k: v for k, v in recipes_table_properties().items() if k not in _CFN_ONLY}
        yield dynamodb.create_table(TableName=RECIPES_TABLE_NAME, **props)
