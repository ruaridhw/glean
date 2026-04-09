import os
from unittest.mock import patch

import pytest

from glean.config import SecretsManagerSource, Settings


class TestSecretsManagerSourceOutsideLambda:
    def test_returns_empty_dict_when_not_in_lambda(self) -> None:
        """Outside Lambda (local dev / CI), source returns nothing so .env takes over."""
        env = {k: v for k, v in os.environ.items() if k != "AWS_LAMBDA_FUNCTION_NAME"}
        with patch.dict(os.environ, env, clear=True):
            source = SecretsManagerSource(Settings)
            assert source() == {}


class TestSecretsManagerSourceInLambda:
    def test_fetches_anthropic_and_recipe_keys(self) -> None:
        lambda_env = {
            "AWS_LAMBDA_FUNCTION_NAME": "glean-api-prod",
            "ENVIRONMENT": "prod",
        }
        with patch.dict(os.environ, lambda_env), patch("glean.config.parameters.get_secret") as mock_get:
            mock_get.side_effect = lambda name: f"val:{name}"
            source = SecretsManagerSource(Settings)
            result = source()

        assert result == {
            "anthropic_api_key": "val:glean/prod/anthropic-api-key",
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
        assert "glean/dev/anthropic-api-key" in fetched_names
        assert "glean/dev/recipe-api-key" in fetched_names

    def test_raises_if_environment_not_set(self) -> None:
        lambda_env = {"AWS_LAMBDA_FUNCTION_NAME": "glean-api-prod"}
        with patch.dict(os.environ, lambda_env, clear=False):
            os.environ.pop("ENVIRONMENT", None)
            with patch("glean.config.parameters.get_secret"):
                source = SecretsManagerSource(Settings)
                with pytest.raises(KeyError):
                    source()
