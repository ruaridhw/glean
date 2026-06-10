from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from glean.llm import Feature, create_chat_model, message_content_as_text, validate_model


class TestCreateChatModel:
    def test_returns_chat_open_router(self) -> None:
        api_key = SecretStr("test-key")
        with patch("glean.llm.ChatOpenRouter") as mock_cls:
            model = create_chat_model("anthropic/claude-sonnet-4.6", api_key=api_key)
            mock_cls.assert_called_once_with(
                model="anthropic/claude-sonnet-4.6", openrouter_api_key=api_key, max_retries=0
            )
            assert model is mock_cls.return_value

    def test_forwards_kwargs(self) -> None:
        api_key = SecretStr("test-key")
        with patch("glean.llm.ChatOpenRouter") as mock_cls:
            create_chat_model("anthropic/claude-sonnet-4.6", api_key=api_key, max_tokens=20, temperature=0.5)
            mock_cls.assert_called_once_with(
                model="anthropic/claude-sonnet-4.6",
                openrouter_api_key=api_key,
                max_tokens=20,
                temperature=0.5,
                max_retries=0,
            )

    def test_caller_can_override_max_retries(self) -> None:
        api_key = SecretStr("test-key")
        with patch("glean.llm.ChatOpenRouter") as mock_cls:
            create_chat_model("anthropic/claude-sonnet-4.6", api_key=api_key, max_retries=2)
            mock_cls.assert_called_once_with(
                model="anthropic/claude-sonnet-4.6",
                openrouter_api_key=api_key,
                max_retries=2,
            )


class TestFeatureMetadata:
    def test_ai_workflow_feature_values_match_langsmith_tags(self) -> None:
        assert Feature.RECEIPT_SCAN == "receipt-scan"
        assert Feature.PANTRY_PURCHASE_DESCRIPTION == "pantry-purchase-description"
        assert Feature.MEAL_PLAN_GENERATION == "meal-plan-generation"
        assert Feature.SHOPPING_LIST_DESCRIPTION == "shopping-list-description"
        assert Feature.RECIPE_IMPORT == "recipe-import"


class TestMessageContentAsText:
    def test_returns_text_content(self) -> None:
        assert message_content_as_text('{"items": []}') == '{"items": []}'

    def test_rejects_structured_content(self) -> None:
        with pytest.raises(TypeError, match="Expected text content"):
            message_content_as_text([{"type": "text", "text": "not plain text"}])


def _mock_model_objects(model_ids: list[str]) -> list[MagicMock]:
    return [MagicMock(id=mid) for mid in model_ids]


class TestValidateModel:
    def test_valid_model_passes(self) -> None:
        mock_client = MagicMock()
        mock_client.models.list.return_value.data = _mock_model_objects(
            ["anthropic/claude-sonnet-4.6", "google/gemma-4-26b-a4b-it:free"]
        )
        with patch("glean.llm.OpenRouter", return_value=mock_client):
            validate_model("anthropic/claude-sonnet-4.6", api_key=SecretStr("test-key"))

    def test_unknown_model_raises(self) -> None:
        mock_client = MagicMock()
        mock_client.models.list.return_value.data = _mock_model_objects(["anthropic/claude-sonnet-4.6"])
        with (
            patch("glean.llm.OpenRouter", return_value=mock_client),
            pytest.raises(ValueError, match="Unknown OpenRouter model"),
        ):
            validate_model("nonexistent/model-99", api_key=SecretStr("test-key"))
