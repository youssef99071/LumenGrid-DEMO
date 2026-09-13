"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "LumenGrid"
    app_env: str = "development"
    debug: bool = True
    sandbox_mode: bool = True

    database_url: str = "sqlite:///./lumengrid.db"

    nac_api_url: str = "https://network-as-code.p-eu.rapidapi.com"
    nac_client_id: str = ""
    nac_client_secret: str = ""
    nac_rapidapi_key: str = ""
    opencellid_api_key: str = ""

    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    nac_max_retries: int = 3
    nac_retry_wait_seconds: float = 1.0

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
