from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from glean.config import Settings
from glean.llm import (
    DEFAULT_LLM_MODEL_POLICY,
    Feature,
    LLMModelPolicy,
    LLMRouter,
    ModelPurpose,
    create_chat_model,
    message_content_as_text,
    validate_model,
)


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


class TestLLMRouter:
    def test_default_policy_matches_issue_77_model_choices(self) -> None:
        assert DEFAULT_LLM_MODEL_POLICY[Feature.SHOPPING_LIST_DESCRIPTION].production_model == (
            "google/gemini-2.5-flash-lite"
        )
        assert DEFAULT_LLM_MODEL_POLICY[Feature.SHOPPING_LIST_DESCRIPTION].eval_model == (
            "google/gemini-3.1-flash-lite"
        )
        assert DEFAULT_LLM_MODEL_POLICY[Feature.PANTRY_PURCHASE_DESCRIPTION].production_model == (
            "google/gemini-2.5-flash-lite"
        )
        assert DEFAULT_LLM_MODEL_POLICY[Feature.PANTRY_PURCHASE_DESCRIPTION].eval_model == (
            "google/gemini-3.1-flash-lite"
        )
        assert DEFAULT_LLM_MODEL_POLICY[Feature.RECEIPT_SCAN].production_model == "google/gemini-3.1-flash-lite"
        assert DEFAULT_LLM_MODEL_POLICY[Feature.RECEIPT_SCAN].eval_model == "google/gemini-3.5-flash"
        assert DEFAULT_LLM_MODEL_POLICY[Feature.RECIPE_IMPORT].production_model == "qwen/qwen3.7-plus"
        assert DEFAULT_LLM_MODEL_POLICY[Feature.RECIPE_IMPORT].eval_model == "z-ai/glm-5.2"
        assert DEFAULT_LLM_MODEL_POLICY[Feature.MEAL_PLAN_GENERATION].production_model == "qwen/qwen3.7-plus"
        assert DEFAULT_LLM_MODEL_POLICY[Feature.MEAL_PLAN_GENERATION].eval_model == "z-ai/glm-5.2"

    def test_creates_chat_model_for_feature_and_purpose(self) -> None:
        api_key = SecretStr("test-key")
        router = LLMRouter(api_key=api_key)

        with patch("glean.llm.ChatOpenRouter") as mock_cls:
            model = router.chat_model(Feature.RECIPE_IMPORT, purpose=ModelPurpose.EVAL)

        mock_cls.assert_called_once_with(
            model="z-ai/glm-5.2",
            openrouter_api_key=api_key,
            max_retries=0,
        )
        assert model is mock_cls.return_value

    def test_from_settings_applies_feature_policy_overrides(self) -> None:
        settings = Settings(
            openrouter_api_key="test-key",
            recipe_api_key="test-recipe_api_key",
            cognito_user_pool_id="test-cognito_user_pool_id",
            cognito_app_client_id="test-cognito_app_client_id",
            s3_receipts_bucket="test-s3_receipts_bucket",
            llm_model_policy_overrides={
                Feature.RECIPE_IMPORT: LLMModelPolicy(
                    production_model="custom/recipe-prod",
                    eval_model="custom/recipe-eval",
                )
            },
        )

        router = LLMRouter.from_settings(settings)

        assert router.model_id_for(Feature.RECIPE_IMPORT) == "custom/recipe-prod"
        assert router.model_id_for(Feature.RECIPE_IMPORT, purpose=ModelPurpose.EVAL) == "custom/recipe-eval"
        assert router.model_id_for(Feature.MEAL_PLAN_GENERATION) == "qwen/qwen3.7-plus"


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
