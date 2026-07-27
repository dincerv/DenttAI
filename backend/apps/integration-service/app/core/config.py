from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ──────────────── DATABASE ────────────────
    DATABASE_URL: str = "postgresql+asyncpg://dentai:dentai_secret@postgres:5432/dentai_db"
    
    # ──────────────── JWT/SECURITY ────────────────
    JWT_SECRET: str = "change_me_in_production_at_least_32_chars"
    JWT_ALGORITHM: str = "HS256"
    
    # ──────────────── SERVICE CONFIG ────────────────
    SERVICE_PORT: int = 8005
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    
    # ──────────────── IMPORT/BATCH ────────────────
    IMPORT_BATCH_SIZE: int = 200
    
    # ──────────────── CELERY ────────────────
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_BACKEND_URL: str = "redis://redis:6379/0"
    
    # ──────────────── WHATSAPP ────────────────
    WHATSAPP_BUSINESS_ACCOUNT_ID: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_WEBHOOK_VERIFY_TOKEN: str = "dentai_webhook_secret_token"
    WHATSAPP_APP_SECRET: str = ""
    
    # ──────────────── LLM (WhatsApp AI) ────────────────
    LLM_PROVIDER: str = "gemini"  # gemini | openai
    LLM_MODEL: str = "gemini-1.5-flash"

    # ──────────────── OPENAI ────────────────
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-3.5-turbo"
    OPENAI_MAX_TOKENS: int = 500
    OPENAI_TEMPERATURE: float = 0.2

    # ──────────────── GEMINI ────────────────
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"
    
    # ──────────────── CORS ────────────────
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
    ]


settings = Settings()
