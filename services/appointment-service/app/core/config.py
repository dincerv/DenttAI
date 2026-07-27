from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://dentai:dentai_secret@postgres:5432/dentai_db"

    # Redis
    REDIS_URL: str = "redis://:redis_secret@redis:6379/1"

    # RabbitMQ
    RABBITMQ_URL: str = "amqp://dentai:rabbitmq_secret@rabbitmq:5672/"
    RABBITMQ_EXCHANGE: str = "dentai.events"

    # JWT (doğrulama için — auth-service ile aynı secret)
    JWT_SECRET: str = "change_me_in_production_at_least_32_chars"
    JWT_ALGORITHM: str = "HS256"

    # Service
    SERVICE_PORT: int = 8002
    ENVIRONMENT: str = "development"


settings = Settings()
