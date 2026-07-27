from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://dentai:dentai_secret@postgres:5432/dentai_db"

    # Redis
    REDIS_URL: str = "redis://:redis_secret@redis:6379/3"

    # JWT (doğrulama için)
    JWT_SECRET: str = "change_me_in_production_at_least_32_chars"
    JWT_ALGORITHM: str = "HS256"

    # Service
    SERVICE_PORT: int = 8003
    ENVIRONMENT: str = "development"

    # Anomali tespiti eşiği — beklenen ömrün bu oranından önce biterken High Waste flaglenir
    ANOMALY_THRESHOLD_RATIO: float = 0.25  # %25'inden önce biterse anomali


settings = Settings()
