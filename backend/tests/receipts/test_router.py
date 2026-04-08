# backend/tests/receipts/test_router.py
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from glean.main import app

FIXTURES = Path(__file__).parent / "fixtures"


def _mock_textract_response() -> dict:
    return json.loads((FIXTURES / "receipt_textract.json").read_text())


def _mock_claude_response() -> list[dict]:
    return json.loads((FIXTURES / "receipt_claude.json").read_text())["items"]


@pytest.fixture
def unauth_client() -> TestClient:
    return TestClient(app)


def test_scan_receipt_returns_parsed_items(client: TestClient, auth_headers: dict[str, str]) -> None:
    mock_s3 = MagicMock()
    mock_textract = MagicMock()
    mock_textract.analyze_expense.return_value = _mock_textract_response()

    mock_result = MagicMock()
    mock_result.content = json.dumps(_mock_claude_response())

    def boto3_client_factory(service_name: str, **kwargs):
        if service_name == "s3":
            return mock_s3
        return mock_textract

    with (
        patch("boto3.client", side_effect=boto3_client_factory),
        patch("glean.receipts.service.ChatAnthropic") as MockChatAnthropic,
    ):
        MockChatAnthropic.return_value.invoke.return_value = mock_result
        response = client.post(
            "/receipts/scan",
            headers=auth_headers,
            files={"file": ("receipt.jpg", b"fake-image-bytes", "image/jpeg")},
        )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2
    assert items[0]["name"] == "chicken breast"
    assert items[0]["quantity"] == 500
    assert items[0]["unit"] == "g"
    assert items[0]["unit_price"] == pytest.approx(0.007)
    mock_s3.put_object.assert_called_once()
    mock_s3.delete_object.assert_called_once()


def test_scan_receipt_requires_auth(unauth_client: TestClient) -> None:
    response = unauth_client.post("/receipts/scan", files={"file": ("r.jpg", b"x", "image/jpeg")})
    assert response.status_code == 401


def test_scan_receipt_rejects_non_image(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/receipts/scan",
        headers=auth_headers,
        files={"file": ("data.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400
    assert "image/jpeg" in response.json()["detail"]


def test_scan_receipt_rejects_oversized(client: TestClient, auth_headers: dict[str, str]) -> None:
    oversized_bytes = b"x" * (10 * 1024 * 1024 + 1)
    response = client.post(
        "/receipts/scan",
        headers=auth_headers,
        files={"file": ("big.jpg", oversized_bytes, "image/jpeg")},
    )
    assert response.status_code == 400
    assert "10MB" in response.json()["detail"]


def test_describe_purchase_parses_text(client: TestClient, auth_headers: dict[str, str]) -> None:
    mock_result = MagicMock()
    mock_result.content = json.dumps(_mock_claude_response())

    with patch("glean.receipts.service.ChatAnthropic") as MockChatAnthropic:
        MockChatAnthropic.return_value.invoke.return_value = mock_result
        response = client.post(
            "/receipts/describe",
            headers=auth_headers,
            json={"text": "I bought a kilo of chicken and 2 litres of milk"},
        )

    assert response.status_code == 200
    assert len(response.json()["items"]) == 2
