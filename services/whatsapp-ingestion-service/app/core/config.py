from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://dentai:dentai_secret@postgres:5432/dentai_db"
    JWT_SECRET: str = "change_me_in_production"
    CELERY_BROKER_URL: str = "redis://redis:6379/5"
    CELERY_BACKEND_URL: str = "redis://redis:6379/5"
    WHATSAPP_WEBHOOK_VERIFY_TOKEN: str = "dentai_webhook_secret_token"
    WHATSAPP_APP_SECRET: str = ""


settings = Settings()
