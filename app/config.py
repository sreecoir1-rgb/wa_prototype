"""
Application configuration loaded from environment variables and .env file.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central settings class for WhatsApp Broadcaster.
    Reads values from system environment variables or a local .env file.
    """
    # WhatsApp Business Cloud API Credentials
    WHATSAPP_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_BUSINESS_ACCOUNT_ID: str = ""

    # Webhook Verification & Security
    WEBHOOK_VERIFY_TOKEN: str = ""
    APP_SECRET: str = ""
    SECRET_KEY: str = ""

    # Database
    DATABASE_URL: str = "sqlite:///./app.db"

    # Simulation flag: when True, messages are logged/simulated without contacting Meta
    DRY_RUN: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Singleton settings instance for use across the application
settings = Settings()
