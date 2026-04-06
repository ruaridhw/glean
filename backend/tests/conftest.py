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
