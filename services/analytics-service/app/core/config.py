from pydantic import Field, field_validator
from pydantic.aliases import AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_asyncpg_url(url: str) -> str:
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    url = url.replace("sslmode=require", "ssl=require")
    url = url.replace("channel_binding=require", "")
    url = url.replace("&&", "&").replace("?&", "?").rstrip("?&")
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    REDIS_URL: str = "redis://redis:6379/4"
    JWT_SECRET: str = Field(..., min_length=32)
    JWT_ALGORITHM: str = "HS256"
    SERVICE_PORT: int = 8004
    ENVIRONMENT: str = "development"
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    CACHE_TTL_SECONDS: int = 3600

    SPECIALTY_FEE: dict = {
        "Genel Diş": 1500,
        "Ortodonti": 3500,
        "İmplant": 8000,
        "Periodontoloji": 2000,
        "Çocuk Diş": 1200,
        "Ağız Cerrahisi": 4000,
        "Endodonti": 2500,
        "Estetik Diş": 5000,
        "default": 2000,
    }

    AI_PROVIDER: str = Field(
        default="gemini",
        validation_alias=AliasChoices("AI_PROVIDER", "ANALYTICS_AI_PROVIDER"),
    )
    OPENAI_API_KEY: str = Field(
        default="",
        validation_alias=AliasChoices("OPENAI_API_KEY", "ANALYTICS_OPENAI_API_KEY"),
    )
    OPENAI_MODEL: str = Field(
        default="gpt-4o-mini",
        validation_alias=AliasChoices("OPENAI_MODEL", "ANALYTICS_OPENAI_MODEL"),
    )
    OPENAI_TIMEOUT_SECONDS: int = Field(
        default=30,
        validation_alias=AliasChoices("OPENAI_TIMEOUT_SECONDS", "ANALYTICS_OPENAI_TIMEOUT_SECONDS"),
    )
    GEMINI_API_KEY: str = Field(
        default="",
        validation_alias=AliasChoices("GEMINI_API_KEY", "ANALYTICS_GEMINI_API_KEY"),
    )
    GEMINI_MODEL: str = Field(
        default="gemini-1.5-pro",
        validation_alias=AliasChoices("GEMINI_MODEL", "ANALYTICS_GEMINI_MODEL"),
    )

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("DATABASE_URL zorunlu")
        return normalize_asyncpg_url(v.strip())

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]


settings = Settings()
