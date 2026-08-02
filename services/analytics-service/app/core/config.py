from pydantic import Field
from pydantic.aliases import AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database — env zorunlu
    DATABASE_URL: str

    # Redis
    REDIS_URL: str = "redis://redis:6379/4"

    # JWT (doğrulama için) — env zorunlu, min 32 karakter
    JWT_SECRET: str = Field(..., min_length=32)
    JWT_ALGORITHM: str = "HS256"

    # Service
    SERVICE_PORT: int = 8004
    ENVIRONMENT: str = "development"

    # Cache TTL — ağır raporlar 1 saat önbellekte tutulur
    CACHE_TTL_SECONDS: int = 3600

    # Recovered Revenue — branş bazlı varsayılan seans ücretleri (TRY)
    # Gerçek senaryoda doctors.fee_per_session gibi bir sütun kullanılabilir;
    # MVP'de branş adına göre sabit tarife uygulanır.
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

    # AI Chat (optional)
    AI_PROVIDER: str = Field(
        default="gemini",
        validation_alias=AliasChoices("AI_PROVIDER", "ANALYTICS_AI_PROVIDER"),
    )  # openai | gemini
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

settings = Settings()
