import os
from unittest.mock import patch

import pytest

from glean.config import SecretsManagerSource, Settings, configure_langsmith_environment, get_settings
from glean.llm import Feature


class TestSecretsManagerSourceOutsideLambda:
    def test_returns_empty_dict_when_not_in_lambda(self) -> None:
        """Outside Lambda (local dev / CI), source returns nothing so .env takes over."""
        env = {k: v for k, v in os.environ.items() if k != "AWS_LAMBDA_FUNCTION_NAME"}
        with patch.dict(os.environ, env, clear=True):
            source = SecretsManagerSource(Settings)
            assert source() == {}


class TestSecretsManagerSourceInLambda:
    def test_fetches_openrouter_and_recipe_keys(self) -> None:
        lambda_env = {
            "AWS_LAMBDA_FUNCTION_NAME": "glean-api-prod",
            "ENVIRONMENT": "prod",
        }
        with patch.dict(os.environ, lambda_env), patch("glean.config.parameters.get_secret") as mock_get:
            mock_get.side_effect = lambda name: f"val:{name}"
            source = SecretsManagerSource(Settings)
            result = source()

        assert result == {
            "openrouter_api_key": "val:glean/prod/openrouter-api-key",
            "recipe_api_key": "val:glean/prod/recipe-api-key",
        }

    def test_uses_environment_variable_for_secret_path(self) -> None:
        lambda_env = {
            "AWS_LAMBDA_FUNCTION_NAME": "glean-api-dev",
            "ENVIRONMENT": "dev",
        }
        with patch.dict(os.environ, lambda_env), patch("glean.config.parameters.get_secret") as mock_get:
            mock_get.return_value = "dummy"
            source = SecretsManagerSource(Settings)
            source()

        fetched_names = [call.args[0] for call in mock_get.call_args_list]
        assert "glean/dev/openrouter-api-key" in fetched_names
        assert "glean/dev/recipe-api-key" in fetched_names

    def test_fetches_langsmith_key_when_tracing_is_enabled(self) -> None:
        lambda_env = {
            "AWS_LAMBDA_FUNCTION_NAME": "glean-api-prod",
            "ENVIRONMENT": "prod",
            "LANGSMITH_TRACING": "true",
        }
        with patch.dict(os.environ, lambda_env), patch("glean.config.parameters.get_secret") as mock_get:
            mock_get.side_effect = lambda name: f"val:{name}"
            source = SecretsManagerSource(Settings)
            result = source()

        assert result == {
            "openrouter_api_key": "val:glean/prod/openrouter-api-key",
            "recipe_api_key": "val:glean/prod/recipe-api-key",
            "langsmith_api_key": "val:glean/prod/langsmith-api-key",
        }

    def test_skips_langsmith_secret_fetch_when_env_key_is_present(self) -> None:
        lambda_env = {
            "AWS_LAMBDA_FUNCTION_NAME": "glean-api-prod",
            "ENVIRONMENT": "prod",
            "LANGSMITH_TRACING": "true",
            "LANGSMITH_API_KEY": "test-langsmith-key",
        }
        with patch.dict(os.environ, lambda_env), patch("glean.config.parameters.get_secret") as mock_get:
            mock_get.side_effect = lambda name: f"val:{name}"
            source = SecretsManagerSource(Settings)
            result = source()

        assert result == {
            "openrouter_api_key": "val:glean/prod/openrouter-api-key",
            "recipe_api_key": "val:glean/prod/recipe-api-key",
        }

    def test_does_not_fetch_langsmith_key_when_tracing_is_disabled(self) -> None:
        lambda_env = {
            "AWS_LAMBDA_FUNCTION_NAME": "glean-api-prod",
            "ENVIRONMENT": "prod",
            "LANGSMITH_TRACING": "false",
        }
        with patch.dict(os.environ, lambda_env), patch("glean.config.parameters.get_secret") as mock_get:
            mock_get.side_effect = lambda name: f"val:{name}"
            source = SecretsManagerSource(Settings)
            result = source()

        assert result == {
            "openrouter_api_key": "val:glean/prod/openrouter-api-key",
            "recipe_api_key": "val:glean/prod/recipe-api-key",
        }

    def test_raises_if_environment_not_set(self) -> None:
        lambda_env = {"AWS_LAMBDA_FUNCTION_NAME": "glean-api-prod"}
        with patch.dict(os.environ, lambda_env, clear=False):
            os.environ.pop("ENVIRONMENT", None)
            with patch("glean.config.parameters.get_secret"):
                source = SecretsManagerSource(Settings)
                with pytest.raises(KeyError):
                    source()


class TestGetSettings:
    def test_caches_lambda_secret_fetches(self) -> None:
        if hasattr(get_settings, "cache_clear"):
            get_settings.cache_clear()

        lambda_env = {
            "AWS_LAMBDA_FUNCTION_NAME": "glean-api-prod",
            "ENVIRONMENT": "prod",
            "COGNITO_USER_POOL_ID": "pool-id",
            "COGNITO_APP_CLIENT_ID": "client-id",
            "S3_RECEIPTS_BUCKET": "receipts-bucket",
        }
        with patch.dict(os.environ, lambda_env, clear=True), patch("glean.config.parameters.get_secret") as mock_get:
            mock_get.side_effect = lambda name: f"val:{name}"

            first = get_settings()
            second = get_settings()

        assert first is second
        assert mock_get.call_count == 2

        if hasattr(get_settings, "cache_clear"):
            get_settings.cache_clear()


class TestLlmModelPolicyOverrides:
    def test_parses_feature_policy_overrides_from_environment(self) -> None:
        env = {
            "OPENROUTER_API_KEY": "test-key",
            "RECIPE_API_KEY": "test-recipe-api-key",
            "COGNITO_USER_POOL_ID": "pool-id",
            "COGNITO_APP_CLIENT_ID": "client-id",
            "S3_RECEIPTS_BUCKET": "receipts-bucket",
            "LLM_MODEL_POLICY_OVERRIDES": (
                '{"recipe-import":{"production_model":"custom/recipe-prod","eval_model":"custom/recipe-eval"}}'
            ),
        }

        with patch.dict(os.environ, env, clear=True):
            settings = Settings()

        assert settings.llm_model_policy_overrides is not None
        override = settings.llm_model_policy_overrides[Feature.RECIPE_IMPORT]
        assert override.production_model == "custom/recipe-prod"
        assert override.eval_model == "custom/recipe-eval"


class TestConfigureLangSmithEnvironment:
    def test_disables_tracing_when_setting_is_false(self) -> None:
        settings = Settings(
            _env_file=None,
            openrouter_api_key="test-openrouter_api_key",
            recipe_api_key="test-recipe_api_key",
            cognito_user_pool_id="test-cognito_user_pool_id",
            cognito_app_client_id="test-cognito_app_client_id",
            s3_receipts_bucket="test_s3_receipts_bucket",
            langsmith_tracing=False,
        )

        with patch.dict(os.environ, {}, clear=True):
            configure_langsmith_environment(settings)

            assert os.environ["LANGSMITH_TRACING"] == "false"
            assert os.environ["LANGCHAIN_TRACING_V2"] == "false"
            assert "LANGSMITH_API_KEY" not in os.environ

    def test_enables_tracing_with_project_and_key(self) -> None:
        settings = Settings(
            _env_file=None,
            openrouter_api_key="test-openrouter_api_key",
            recipe_api_key="test-recipe_api_key",
            cognito_user_pool_id="test-cognito_user_pool_id",
            cognito_app_client_id="test-cognito_app_client_id",
            s3_receipts_bucket="test_s3_receipts_bucket",
            langsmith_tracing=True,
            langsmith_api_key="test-langsmith-key",
        )

        with patch.dict(os.environ, {"AWS_LAMBDA_FUNCTION_NAME": "glean-api-prod"}, clear=True):
            configure_langsmith_environment(settings)

            assert os.environ["LANGSMITH_TRACING"] == "true"
            assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
            assert os.environ["LANGSMITH_API_KEY"] == "test-langsmith-key"
            assert os.environ["LANGSMITH_PROJECT"] == "glean"
            assert os.environ["LANGCHAIN_CALLBACKS_BACKGROUND"] == "false"
