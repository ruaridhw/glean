from fastapi.testclient import TestClient

from glean.config import Settings, get_settings
from glean.main import app


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_reports_the_deployed_commit(test_settings: Settings) -> None:
    """A deploy stamps its commit (with a -dirty marker for uncommitted work) so prod's version is visible."""
    app.dependency_overrides[get_settings] = lambda: test_settings.model_copy(update={"git_sha": "abc1234-dirty"})
    try:
        response = TestClient(app).get("/health")
    finally:
        app.dependency_overrides.clear()
    assert response.json() == {"status": "ok", "commit": "abc1234-dirty"}


def test_health_reports_unknown_commit_when_unstamped(client: TestClient) -> None:
    assert client.get("/health").json()["commit"] == "unknown"


def test_protected_requires_token(test_settings: Settings) -> None:
    """Endpoint protected by verify_cognito_token returns 401 with no token."""
    app.dependency_overrides[get_settings] = lambda: test_settings
    bare_client = TestClient(app)
    response = bare_client.post("/dev/export-db")
    assert response.status_code == 401
    app.dependency_overrides.clear()
