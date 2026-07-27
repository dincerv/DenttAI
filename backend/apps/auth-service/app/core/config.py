from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://dentai:dentai_secret@postgres:5432/dentai_db"

    # Redis
    REDIS_URL: str = "redis://:redis_secret@redis:6379/0"

    # JWT
    JWT_SECRET: str = "change_me_in_production_at_least_32_chars"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_EXPIRE_DAYS: int = 30

    # Service
    SERVICE_PORT: int = 8001
    ENVIRONMENT: str = "development"

    # Reporting defaults
    WHATSAPP_MESSAGE_COST_USD: float = 0.02


settings = Settings()
