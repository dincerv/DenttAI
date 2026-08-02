from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database — env zorunlu, kaynak kodda secret default yok
    DATABASE_URL: str

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # JWT
    JWT_SECRET: str = Field(..., min_length=32)
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_EXPIRE_DAYS: int = 30

    # Service
    SERVICE_PORT: int = 8001
    ENVIRONMENT: str = "development"

    # Public self-service clinic registration (default: closed)
    ALLOW_PUBLIC_REGISTER: bool = False

    # Reporting defaults
    WHATSAPP_MESSAGE_COST_USD: float = 0.02


settings = Settings()
