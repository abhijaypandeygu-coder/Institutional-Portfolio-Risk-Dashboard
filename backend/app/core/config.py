"""Core application settings and environment loader for M01 and M02."""
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Institutional Portfolio Risk Dashboard - Core Settings."""
    APP_NAME: str = Field(default="Institutional Portfolio Risk Dashboard", description="Service name")
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
    API_KEY_ADMIN: str = Field(default="admin_dev_secret_key_2026", description="Admin API key")
    API_KEY_OPERATOR: str = Field(default="operator_dev_secret_key_2026", description="Operator API key")
    API_KEY_READ_ONLY: str = Field(default="readonly_dev_secret_key_2026", description="Read-only API key")

    # Secret Reference Provider Backend: 'ENV', 'VAULT', 'KEYRING'
    SECRETS_PROVIDER_BACKEND: str = Field(default="ENV", description="Secrets provider backend driver")

    # --------------------------------------------------------------------------
    # Alpha Vantage Configuration (M02 Provider Integration Addendum)
    # --------------------------------------------------------------------------
    ALPHA_VANTAGE_API_KEY: Optional[str] = Field(default=None, description="Alpha Vantage API key")
    ALPHA_VANTAGE_BASE_URL: str = Field(default="https://www.alphavantage.co/query", description="Alpha Vantage API endpoint")
    ALPHA_VANTAGE_PLAN: str = Field(default="free", description="Alpha Vantage subscription plan (free/premium)")
    ALPHA_VANTAGE_DAILY_CALL_BUDGET: int = Field(default=20, ge=1, le=1000, description="Internal safety call budget per day")
    ALPHA_VANTAGE_ENABLED: bool = Field(default=True, description="Enable Alpha Vantage provider adapter")

    MARKET_DATA_SIMULATOR_ENABLED: bool = Field(default=True, description="Enable simulated real-time provider")
    MARKET_DATA_DEFAULT_PROVIDER: str = Field(default="alpha_vantage", description="Default market data provider")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
