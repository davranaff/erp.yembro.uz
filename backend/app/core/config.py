from __future__ import annotations

from typing import Annotated

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = Field(
        default="development",
        validation_alias=AliasChoices("APP_ENVIRONMENT", "ENVIRONMENT"),
    )
    app_name: str = Field(default="yembro-backend", validation_alias=AliasChoices("APP_NAME", "NAME"))
    api_host: str = Field(default="0.0.0.0", validation_alias=AliasChoices("APP_HOST", "HOST"))
    api_container_port: int = Field(
        default=30000,
        validation_alias=AliasChoices("APP_CONTAINER_PORT", "APP_PORT", "PORT"),
    )
    api_published_port: int = Field(
        default=30000,
        validation_alias=AliasChoices("APP_PUBLISHED_PORT", "APP_PORT", "PORT"),
    )
    log_level: str = Field(default="INFO", validation_alias=AliasChoices("APP_LOG_LEVEL", "LOG_LEVEL"))
    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:30010/yembro",
        validation_alias=AliasChoices("APP_DATABASE_URL", "DATABASE_URL"),
    )
    redis_url: str = Field(
        default="redis://localhost:30011/0",
        validation_alias=AliasChoices("APP_REDIS_URL", "REDIS_URL"),
    )
    postgres_pool_min_size: int = Field(
        default=1,
        validation_alias=AliasChoices("APP_POSTGRES_POOL_MIN_SIZE", "POSTGRES_POOL_MIN_SIZE"),
    )
    postgres_pool_max_size: int = Field(
        default=10,
        validation_alias=AliasChoices("APP_POSTGRES_POOL_MAX_SIZE", "POSTGRES_POOL_MAX_SIZE"),
    )
    request_timeout_seconds: int = Field(
        default=30,
        validation_alias=AliasChoices("APP_REQUEST_TIMEOUT_SECONDS", "REQUEST_TIMEOUT_SECONDS"),
    )
    debug: bool = Field(default=False, validation_alias=AliasChoices("APP_DEBUG"))
    auth_secret_key: str = Field(
        default="development-only-secret-change-me",
        validation_alias=AliasChoices("APP_AUTH_SECRET_KEY", "AUTH_SECRET_KEY"),
    )
    auth_access_token_ttl_minutes: int = Field(
        default=720,
        validation_alias=AliasChoices("APP_AUTH_ACCESS_TOKEN_TTL_MINUTES", "AUTH_ACCESS_TOKEN_TTL_MINUTES"),
    )
    auth_refresh_token_ttl_days: int = Field(
        default=30,
        validation_alias=AliasChoices("APP_AUTH_REFRESH_TOKEN_TTL_DAYS", "AUTH_REFRESH_TOKEN_TTL_DAYS"),
    )
    auth_allow_header_overrides: bool = Field(
        default=False,
        validation_alias=AliasChoices("APP_AUTH_ALLOW_HEADER_OVERRIDES", "AUTH_ALLOW_HEADER_OVERRIDES"),
    )
    public_web_base_url: str = Field(
        default="http://localhost:30080",
        validation_alias=AliasChoices("APP_PUBLIC_WEB_BASE_URL", "PUBLIC_WEB_BASE_URL"),
    )
    public_api_base_url: str = Field(
        default="http://localhost:30000",
        validation_alias=AliasChoices("APP_PUBLIC_API_BASE_URL", "PUBLIC_API_BASE_URL"),
    )
    cors_allow_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        validation_alias=AliasChoices("APP_CORS_ALLOW_ORIGINS", "CORS_ALLOW_ORIGINS"),
    )
    medicine_qr_token_ttl_days: int = Field(
        default=365,
        validation_alias=AliasChoices("APP_MEDICINE_QR_TOKEN_TTL_DAYS", "MEDICINE_QR_TOKEN_TTL_DAYS"),
    )
    storage_backend: str = Field(
        default="auto",
        validation_alias=AliasChoices("APP_STORAGE_BACKEND", "STORAGE_BACKEND"),
    )
    storage_local_root: str = Field(
        default="./uploaded_files",
        validation_alias=AliasChoices("APP_STORAGE_LOCAL_ROOT", "STORAGE_LOCAL_ROOT"),
    )
    storage_max_upload_bytes: int = Field(
        default=10 * 1024 * 1024,
        validation_alias=AliasChoices("APP_STORAGE_MAX_UPLOAD_BYTES", "STORAGE_MAX_UPLOAD_BYTES"),
    )
    storage_s3_endpoint_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("APP_STORAGE_S3_ENDPOINT_URL", "STORAGE_S3_ENDPOINT_URL"),
    )
    storage_s3_region: str = Field(
        default="us-east-1",
        validation_alias=AliasChoices("APP_STORAGE_S3_REGION", "STORAGE_S3_REGION"),
    )
    storage_s3_bucket: str | None = Field(
        default=None,
        validation_alias=AliasChoices("APP_STORAGE_S3_BUCKET", "STORAGE_S3_BUCKET"),
    )
    storage_s3_access_key_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("APP_STORAGE_S3_ACCESS_KEY_ID", "STORAGE_S3_ACCESS_KEY_ID"),
    )
    storage_s3_secret_access_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("APP_STORAGE_S3_SECRET_ACCESS_KEY", "STORAGE_S3_SECRET_ACCESS_KEY"),
    )
    storage_s3_force_path_style: bool = Field(
        default=True,
        validation_alias=AliasChoices("APP_STORAGE_S3_FORCE_PATH_STYLE", "STORAGE_S3_FORCE_PATH_STYLE"),
    )
    telegram_bot_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("APP_TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_TOKEN"),
    )
    telegram_api_base_url: str = Field(
        default="https://api.telegram.org",
        validation_alias=AliasChoices("APP_TELEGRAM_API_BASE_URL", "TELEGRAM_API_BASE_URL"),
    )
    telegram_parse_mode: str | None = Field(
        default=None,
        validation_alias=AliasChoices("APP_TELEGRAM_PARSE_MODE", "TELEGRAM_PARSE_MODE"),
    )
    telegram_webhook_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices("APP_TELEGRAM_WEBHOOK_SECRET", "TELEGRAM_WEBHOOK_SECRET"),
    )
    telegram_link_token_ttl_minutes: int = Field(
        default=30,
        validation_alias=AliasChoices(
            "APP_TELEGRAM_LINK_TOKEN_TTL_MINUTES",
            "TELEGRAM_LINK_TOKEN_TTL_MINUTES",
        ),
    )

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("debug", "auth_allow_header_overrides", mode="before")
    @classmethod
    def _coerce_debug(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip().lower()
            if value in {"true", "1", "yes", "on"}:
                return True
            if value in {"false", "0", "no", "off", "release", "prod", "production"}:
                return False
        return value

    @field_validator("storage_s3_force_path_style", mode="before")
    @classmethod
    def _coerce_storage_s3_force_path_style(cls, value: object) -> object:
        return cls._coerce_debug(value)

    @field_validator("storage_backend", mode="before")
    @classmethod
    def _normalize_storage_backend(cls, value: object) -> str:
        normalized = str(value or "auto").strip().lower()
        if normalized not in {"auto", "local", "s3"}:
            return "auto"
        return normalized

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _normalize_cors_allow_origins(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            parts = [part.strip() for part in value.replace("\n", ",").split(",")]
            return [part for part in parts if part]
        if isinstance(value, (list, tuple, set)):
            return [str(item).strip() for item in value if str(item).strip()]
        normalized = str(value).strip()
        return [normalized] if normalized else []

    @property
    def sqlalchemy_database_url(self) -> str:
        if "postgresql+asyncpg://" in self.database_url:
            return self.database_url
        return self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)


def get_settings() -> Settings:
    return Settings()
