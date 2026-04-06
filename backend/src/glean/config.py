from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    anthropic_api_key: str
    recipe_api_key: str
    recipe_api_base_url: str = "https://recipe-api.com/api/v1"
    aws_region: str = "eu-west-2"
    cognito_user_pool_id: str
    cognito_app_client_id: str
    s3_receipts_bucket: str
    log_level: str = "INFO"
    rate_limit_per_hour: int = 20

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
