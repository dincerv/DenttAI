from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    JWT_SECRET: str = Field(..., min_length=32)
    CELERY_BROKER_URL: str = "redis://redis:6379/5"
    CELERY_BACKEND_URL: str = "redis://redis:6379/5"
    WHATSAPP_WEBHOOK_VERIFY_TOKEN: str = ""
    WHATSAPP_APP_SECRET: str = ""


settings = Settings()
