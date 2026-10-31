"""Core application settings and environment loader for M01."""
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Institutional Portfolio Risk Dashboard - Module 01 Settings."""
    ENVIRONMENT: str = Field(default="development", description="Environment: development, staging, production")
    LOG_LEVEL: str = Field(default="INFO", description="Standard logging level")
    APP_HOST: str = Field(default="0.0.0.0", description="API bind host")
    APP_PORT: int = Field(default=8000, description="API bind port")
    SECRET_KEY: str = Field(default="dev_secret_key_change_in_production_2026", description="Signing key")

    # Database URLs
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./feed_registry.db",
        description="Async database connection string"
    )
    SYNC_DATABASE_URL: str = Field(
        default="sqlite:///./feed_registry.db",
        description="Sync database connection string"
    )

    # API Keys for RBAC (Admin, Operator, ReadOnly)
    ADMIN_API_KEY: str = Field(default="admin_dev_secret_key", description="Admin API key")
    OPERATOR_API_KEY: str = Field(default="operator_dev_secret_key", description="Operator API key")
    READONLY_API_KEY: str = Field(default="readonly_dev_secret_key", description="Read-only API key")

    # Secret Reference Provider Backend: 'ENV', 'VAULT', 'KEYRING'
    SECRETS_PROVIDER_BACKEND: str = Field(default="ENV", description="Secrets provider backend driver")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

