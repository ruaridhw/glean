from __future__ import annotations

import os
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from aws_lambda_powertools.utilities import parameters
from pydantic import SecretStr  # noqa: TC002 - Pydantic resolves this field type at runtime.
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from glean.llm import Feature, LLMModelPolicy  # noqa: TC001 - Pydantic resolves these field types at runtime.

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo


class SecretsManagerSource(PydanticBaseSettingsSource):
    """Fetches runtime API keys from AWS Secrets Manager.

    Only active when running inside Lambda (AWS_LAMBDA_FUNCTION_NAME is set).
    Falls back to a no-op outside Lambda so local .env continues to work.
    """

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        if not os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
            return {}
        env = os.environ["ENVIRONMENT"]
        values = {
            "openrouter_api_key": parameters.get_secret(f"glean/{env}/openrouter-api-key"),
            "recipe_api_key": parameters.get_secret(f"glean/{env}/recipe-api-key"),
        }
        if _env_flag_enabled(os.environ.get("LANGSMITH_TRACING")) and not os.environ.get("LANGSMITH_API_KEY"):
            values["langsmith_api_key"] = parameters.get_secret(f"glean/{env}/langsmith-api-key")
        return values


class Settings(BaseSettings):
    openrouter_api_key: SecretStr
    recipe_api_key: SecretStr
    recipe_api_base_url: str = "https://recipe-api.com/api/v1"
    aws_region: str = "eu-west-2"
    cognito_user_pool_id: str
    cognito_app_client_id: str
    s3_receipts_bucket: str
    # Durable S3 store for the recipe corpus + HTTP cache. Empty locally / in tests → the
    # `.cache/...` filesystem store is used instead (see recipe_api.blob_store).
    s3_recipe_cache_bucket: str = ""
    log_level: str = "INFO"
    rate_limit_per_hour: int = 20
    llm_model_policy_overrides: dict[Feature, LLMModelPolicy] | None = None
    receipt_ocr_mode: str = "textract"  # "textract" (AWS) or "vision" (OpenRouter vision model)
    langsmith_tracing: bool = False
    langsmith_api_key: SecretStr | None = None
    langsmith_project: str = "glean"
    langsmith_endpoint: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

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


def _env_flag_enabled(value: str | None) -> bool:
    return value is not None and value.strip().lower() in {"1", "true", "yes", "on"}


def _secret_value(secret: SecretStr | None) -> str | None:
    if secret is None:
        return None
    value = secret.get_secret_value()
    return value or None


def _set_optional_env(name: str, value: str | None) -> None:
    if value:
        os.environ[name] = value
    else:
        os.environ.pop(name, None)


def configure_langsmith_environment(settings: Settings) -> None:
    tracing_enabled = "true" if settings.langsmith_tracing else "false"
    os.environ["LANGSMITH_TRACING"] = tracing_enabled
    os.environ["LANGCHAIN_TRACING_V2"] = tracing_enabled

    if not settings.langsmith_tracing:
        return

    _set_optional_env("LANGSMITH_API_KEY", _secret_value(settings.langsmith_api_key))
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    _set_optional_env("LANGSMITH_ENDPOINT", settings.langsmith_endpoint)

    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        os.environ.setdefault("LANGCHAIN_CALLBACKS_BACKGROUND", "false")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()  # ty: ignore[missing-argument]
    configure_langsmith_environment(settings)
    return settings
