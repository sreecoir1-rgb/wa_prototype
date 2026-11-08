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

    # Telegram Bot API Credentials & Multi-Channel Provider
    TELEGRAM_BOT_TOKEN: str = ""
    BROADCAST_PROVIDER: str = "telegram"  # "telegram", "whatsapp", "telegram_user", or "both"

    # Telegram User Account (MTProto / Personal Phone) Credentials
    TELEGRAM_API_ID: int = 0
    TELEGRAM_API_HASH: str = ""
    TELEGRAM_PHONE: str = ""
    TELEGRAM_SESSION_NAME: str = "telegram_user"

    # Webhook Verification & Security
    WEBHOOK_VERIFY_TOKEN: str = ""
    APP_SECRET: str = ""
    SECRET_KEY: str = "dev-secret-key-change-in-production-12345"

    # Admin Authentication
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD_HASH: str = ""

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
