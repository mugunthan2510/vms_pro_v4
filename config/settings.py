import os
from pydantic import BaseModel

class Settings(BaseModel):
    APP_NAME: str = "VMS PRO V4"
    VERSION: str = "4.0.0"
    ENV: str = os.getenv("ENV", "development")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./vms_pro_v4.db")
    API_PORT: int = int(os.getenv("API_PORT", 8000))

    # Angel One Smart API Credentials (Reading from setx env vars)
    ANGEL_API_KEY: str = os.getenv("SMARTAPI_KEY", "")
    ANGEL_CLIENT_CODE: str = os.getenv("SMARTAPI_CLIENT", "")
    ANGEL_PASSWORD: str = os.getenv("SMARTAPI_PIN", "")
    ANGEL_TOTP_SECRET: str = os.getenv("SMARTAPI_TOTP", "")

    # Telegram Notification Credentials
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

settings = Settings()