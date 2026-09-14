from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

_PLACEHOLDER_MASTER_KEY = "REPLACE_ME_WITH_A_REAL_KEY"
_KNOWN_WEAK_KEYS = frozenset({
    _PLACEHOLDER_MASTER_KEY,
    "DEV_ONLY_DEFAULT_MASTER_KEY_REPLACE_ME",
    "dev-api-key-change-me",
    "changeme",
    "secret",
    "test",
    "generate-a-random-key-here",
})
_MIN_MASTER_KEY_LENGTH = 20


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/hypothesis_engine"
    API_MASTER_KEY: str = _PLACEHOLDER_MASTER_KEY
    PROJECT_NAME: str = "HypothesisEngine API"
    API_V1_STR: str = "/api/v1"
    APP_VERSION: str = "1.8.0"
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    @model_validator(mode="after")
    def validate_required_config(self) -> "Settings":
        """Fail fast if critical configuration is missing or invalid."""
        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL must be set")
        if not self.API_MASTER_KEY:
            raise ValueError("API_MASTER_KEY must be set")
        if self.API_MASTER_KEY in _KNOWN_WEAK_KEYS:
            raise ValueError("Generate a random API_MASTER_KEY and set it in your .env file.")
        if len(self.API_MASTER_KEY) < _MIN_MASTER_KEY_LENGTH:
            raise ValueError(
                f"API_MASTER_KEY must be at least {_MIN_MASTER_KEY_LENGTH} characters long."
            )
        return self


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
