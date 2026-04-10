from __future__ import annotations

import os
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from aws_lambda_powertools.utilities import parameters
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo


class SecretsManagerSource(PydanticBaseSettingsSource):
    """Fetches openrouter_api_key and recipe_api_key from AWS Secrets Manager.

    Only active when running inside Lambda (AWS_LAMBDA_FUNCTION_NAME is set).
    Falls back to a no-op outside Lambda so local .env continues to work.
    """

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        if not os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
            return {}
        env = os.environ["ENVIRONMENT"]
        return {
            "openrouter_api_key": parameters.get_secret(f"glean/{env}/openrouter-api-key"),
            "recipe_api_key": parameters.get_secret(f"glean/{env}/recipe-api-key"),
        }


class Settings(BaseSettings):
    openrouter_api_key: str
    recipe_api_key: str
    recipe_api_base_url: str = "https://recipe-api.com/api/v1"
    aws_region: str = "eu-west-2"
    cognito_user_pool_id: str
    cognito_app_client_id: str
    s3_receipts_bucket: str
    log_level: str = "INFO"
    rate_limit_per_hour: int = 20
    llm_model: str = "anthropic/claude-sonnet-4.6"
    langchain_project: str = "glean-dev"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            SecretsManagerSource(settings_cls),
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
