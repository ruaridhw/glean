# backend/tests/receipts/test_router.py
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from glean.config import Settings, get_settings
from glean.dependencies import get_llm_router
from glean.llm import Feature, ImagePart
from glean.main import app
from glean.receipts.schemas import DescribeRequest, ParsedIngredient, ScanResponse
from glean.receipts.service import (
    NORMALISE_SYSTEM_PROMPT,
    VISION_SYSTEM_PROMPT,
    _extract_textract_lines,
    describe_purchase,
    reply_token_limit,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _mock_textract_response() -> dict:
    return json.loads((FIXTURES / "receipt_textract.json").read_text())


def _mock_claude_response() -> list[dict]:
    return json.loads((FIXTURES / "receipt_claude.json").read_text())["items"]


def _mock_scan_response() -> ScanResponse:
    return ScanResponse(items=[ParsedIngredient(**item) for item in _mock_claude_response()])


@pytest.fixture
def unauth_client(test_settings: Settings) -> TestClient:
    app.dependency_overrides[get_settings] = lambda: test_settings
    return TestClient(app)


def test_scan_receipt_returns_parsed_items(client: TestClient, auth_headers: dict[str, str]) -> None:
    mock_s3 = MagicMock()
    mock_textract = MagicMock()
    mock_textract.analyze_expense.return_value = _mock_textract_response()

    def boto3_client_factory(service_name: str, **kwargs):
        if service_name == "s3":
            return mock_s3
        return mock_textract

    llm_router = MagicMock()
    llm_router.invoke.return_value = _mock_scan_response()
    app.dependency_overrides[get_llm_router] = lambda: llm_router
    with patch("boto3.client", side_effect=boto3_client_factory):
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
    assert items[0]["category"] == "red_meat"
    assert items[0]["food_group"] == "protein"
    assert items[1]["category"] == "dairy"
    assert items[1]["food_group"] == "dairy"
    mock_s3.put_object.assert_called_once()
    mock_s3.delete_object.assert_called_once()
    args, _ = llm_router.invoke.call_args
    assert args[0] == Feature.RECEIPT_SCAN
    assert args[1] is ScanResponse


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


def test_scan_receipt_vision_mode(client: TestClient, auth_headers: dict[str, str]) -> None:
    vision_settings = Settings(
        openrouter_api_key="test-key",
        recipe_api_key="test-recipe_api_key",
        cognito_user_pool_id="test-cognito_user_pool_id",
        cognito_app_client_id="test-cognito_app_client_id",
        s3_receipts_bucket="test-s3_receipts_bucket",
        receipt_ocr_mode="vision",
    )
    app.dependency_overrides[get_settings] = lambda: vision_settings
    llm_router = MagicMock()
    llm_router.invoke.return_value = _mock_scan_response()
    app.dependency_overrides[get_llm_router] = lambda: llm_router
    response = client.post(
        "/receipts/scan",
        headers=auth_headers,
        files={"file": ("receipt.jpg", b"fake-image-bytes", "image/jpeg")},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2
    assert items[0]["name"] == "chicken breast"
    args, kwargs = llm_router.invoke.call_args
    assert args[0] == Feature.RECEIPT_SCAN
    assert args[1] is ScanResponse
    assert kwargs["system"] == VISION_SYSTEM_PROMPT
    assert kwargs["user"] == [
        "Extract and normalise all items from this receipt.",
        ImagePart(data=b"fake-image-bytes", mime_type="image/jpeg"),
    ]


def test_describe_purchase_parses_text(client: TestClient, auth_headers: dict[str, str]) -> None:
    llm_router = MagicMock()
    llm_router.invoke.return_value = _mock_scan_response()
    app.dependency_overrides[get_llm_router] = lambda: llm_router
    response = client.post(
        "/receipts/describe",
        headers=auth_headers,
        json={"text": "I bought a kilo of chicken and 2 litres of milk"},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2
    assert items[0]["category"] == "red_meat"
    assert items[0]["food_group"] == "protein"
    args, _ = llm_router.invoke.call_args
    assert args[0] == Feature.PANTRY_PURCHASE_DESCRIPTION
    assert args[1] is ScanResponse


def test_scan_receipt_falls_back_to_other_food_group_for_out_of_taxonomy_category(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """An LLM response outside the 23-category taxonomy must not reach the client verbatim, and
    food_group must still resolve (non-null) so meal-plan generation doesn't 422 on it."""
    mock_s3 = MagicMock()
    mock_textract = MagicMock()
    mock_textract.analyze_expense.return_value = _mock_textract_response()

    def boto3_client_factory(service_name: str, **kwargs):
        if service_name == "s3":
            return mock_s3
        return mock_textract

    llm_router = MagicMock()
    llm_router.invoke.return_value = ScanResponse(
        items=[
            ParsedIngredient(
                name="chicken breast",
                quantity=500,
                unit="g",
                unit_price=0.007,
                confidence=0.92,
                category="artisanal-cheese-boutique",  # not in the taxonomy
            )
        ]
    )
    app.dependency_overrides[get_llm_router] = lambda: llm_router
    with patch("boto3.client", side_effect=boto3_client_factory):
        response = client.post(
            "/receipts/scan",
            headers=auth_headers,
            files={"file": ("receipt.jpg", b"fake-image-bytes", "image/jpeg")},
        )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["category"] is None
    assert item["food_group"] == "other"


def test_describe_purchase_uses_pantry_purchase_feature_metadata() -> None:
    llm_router = MagicMock()
    llm_router.invoke.return_value = _mock_scan_response()

    response = describe_purchase(DescribeRequest(text="I bought chicken and milk"), llm_router=llm_router)

    assert len(response.items) == 2
    args, kwargs = llm_router.invoke.call_args
    assert args[0] == Feature.PANTRY_PURCHASE_DESCRIPTION
    assert args[1] is ScanResponse
    assert kwargs["system"] == NORMALISE_SYSTEM_PROMPT
    assert kwargs["user"] == "Parse this grocery purchase description: I bought chicken and milk"


def test_scan_receipt_asks_the_model_for_a_deterministic_bounded_reply_and_retries_once(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """Replaying a real receipt: at the default sampling about 1 call in 6 ran away until the model's limit
    (13-67 KB over 23-159 s, past Lambda's 30 s) or was cut short into a 1-item answer; at temperature 0 none did.
    A 12-line receipt needs about 1,000 reply tokens, so the limit leaves room without letting a runaway last."""
    mock_textract = MagicMock()
    mock_textract.analyze_expense.return_value = _mock_textract_response()
    llm_router = MagicMock()
    llm_router.invoke.return_value = _mock_scan_response()
    app.dependency_overrides[get_llm_router] = lambda: llm_router

    with patch("boto3.client", side_effect=lambda name, **_: MagicMock() if name == "s3" else mock_textract):
        response = client.post(
            "/receipts/scan",
            headers=auth_headers,
            files={"file": ("receipt.jpg", b"fake-image-bytes", "image/jpeg")},
        )

    assert response.status_code == 200
    kwargs = llm_router.invoke.call_args.kwargs
    assert kwargs["temperature"] == 0
    assert kwargs["max_tokens"] == reply_token_limit(line_count=len(_extract_textract_lines(_mock_textract_response())))
    assert kwargs["attempts"] == 2


def test_the_token_limit_leaves_room_for_the_measured_reply_without_letting_a_runaway_last() -> None:
    # A real 12-line receipt's reply took 770-1,270 tokens; a runaway at 4,096 tokens ends within about 10 s.
    assert 1_500 <= reply_token_limit(line_count=12) <= 4_096


def test_the_token_limit_grows_with_the_receipt() -> None:
    assert reply_token_limit(line_count=12) < reply_token_limit(line_count=40) <= 8_192
    assert reply_token_limit(line_count=0) >= 512
    assert reply_token_limit(line_count=500) == 8_192
