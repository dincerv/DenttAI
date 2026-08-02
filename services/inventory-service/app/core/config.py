from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    REDIS_URL: str = "redis://redis:6379/3"
    JWT_SECRET: str = Field(..., min_length=32)
    JWT_ALGORITHM: str = "HS256"
    SERVICE_PORT: int = 8003
    ENVIRONMENT: str = "development"
    ANOMALY_THRESHOLD_RATIO: float = 0.25


settings = Settings()
