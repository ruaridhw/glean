import unittest.mock as mock
from io import BytesIO

from fastapi.testclient import TestClient

from glean.config import Settings, get_settings
from glean.main import app


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_protected_requires_token(test_settings: Settings) -> None:
    """Endpoint protected by verify_cognito_token returns 401 with no token."""
    app.dependency_overrides[get_settings] = lambda: test_settings
    bare_client = TestClient(app)
    response = bare_client.post("/dev/export-db")
    assert response.status_code == 401
    app.dependency_overrides.clear()


def test_protected_succeeds_with_valid_token(client: TestClient, auth_headers: dict) -> None:
    """With dependency override in place, a protected endpoint accepts the request."""
    with mock.patch("glean.dev.router.boto3") as mock_boto3:
        mock_s3 = mock.MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_s3.put_object.return_value = {}

        response = client.post(
            "/dev/export-db",
            files={"file": ("glean.db", BytesIO(b"SQLite data"), "application/octet-stream")},
            headers=auth_headers,
        )
    assert response.status_code == 200
    assert response.json()["status"] == "uploaded"
