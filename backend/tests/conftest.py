import os

os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
os.environ.setdefault("RECIPE_API_KEY", "test-key")
os.environ.setdefault("COGNITO_USER_POOL_ID", "us-east-1_test")
os.environ.setdefault("COGNITO_APP_CLIENT_ID", "test-client-id")
os.environ.setdefault("S3_RECEIPTS_BUCKET", "test-bucket")

import pytest
from fastapi.testclient import TestClient

from glean.dependencies import verify_cognito_token
from glean.main import app


@pytest.fixture
def client() -> TestClient:
    app.dependency_overrides[verify_cognito_token] = lambda: "test-user-sub"
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}
