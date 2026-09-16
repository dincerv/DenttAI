"""
DentAI Flow — Monolith API Konfigürasyonu
Tüm mikroservislerin env değişkenleri tek bir Settings sınıfında.
"""
from pydantic import Field, field_validator
from pydantic.aliases import AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_asyncpg_url(url: str) -> str:
    """Neon/libpq URL'lerini SQLAlchemy asyncpg formatına çevir."""
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    # asyncpg sslmode anlamaz; channel_binding sorun çıkarabilir
    url = url.replace("sslmode=require", "ssl=require")
    url = url.replace("channel_binding=require", "")
    url = url.replace("&&", "&").replace("?&", "?").rstrip("?&")
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── DATABASE ──────────────────────────────────────────
    DATABASE_URL: str

    # ── REDIS ─────────────────────────────────────────────
    REDIS_URL: str = "redis://redis:6379/0"

    # ── JWT ───────────────────────────────────────────────
    JWT_SECRET: str = Field(..., min_length=32)
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_EXPIRE_DAYS: int = 30

    # ── SERVICE ───────────────────────────────────────────
    SERVICE_PORT: int = 8000
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ── AUTH ──────────────────────────────────────────────
    # Public self-service clinic registration (default: closed)
    ALLOW_PUBLIC_REGISTER: bool = False

    # ── CORS ──────────────────────────────────────────────
    # Virgülle ayrılmış origin listesi (Vercel + localhost)
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # ── ANALYTICS ─────────────────────────────────────────
    CACHE_TTL_SECONDS: int = 3600
    WHATSAPP_MESSAGE_COST_USD: float = 0.02

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

    # ── AI / LLM ──────────────────────────────────────────
    AI_PROVIDER: str = Field(
        default="gemini",
        validation_alias=AliasChoices("AI_PROVIDER", "ANALYTICS_AI_PROVIDER"),
    )
    LLM_PROVIDER: str = "gemini"  # WhatsApp AI için
    LLM_MODEL: str = "gemini-1.5-flash"

    OPENAI_API_KEY: str = Field(
        default="",
        validation_alias=AliasChoices("OPENAI_API_KEY", "ANALYTICS_OPENAI_API_KEY"),
    )
    OPENAI_MODEL: str = Field(
        default="gpt-4o-mini",
        validation_alias=AliasChoices("OPENAI_MODEL", "ANALYTICS_OPENAI_MODEL"),
    )
    OPENAI_MAX_TOKENS: int = 500
    OPENAI_TEMPERATURE: float = 0.2
    OPENAI_TIMEOUT_SECONDS: int = 30

    GEMINI_API_KEY: str = Field(
        default="",
        validation_alias=AliasChoices("GEMINI_API_KEY", "ANALYTICS_GEMINI_API_KEY"),
    )
    GEMINI_MODEL: str = Field(
        default="gemini-1.5-pro",
        validation_alias=AliasChoices("GEMINI_MODEL", "ANALYTICS_GEMINI_MODEL"),
    )

    # ── WHATSAPP (Meta Cloud API) ──────────────────────────
    WHATSAPP_BUSINESS_ACCOUNT_ID: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_WEBHOOK_VERIFY_TOKEN: str = ""
    WHATSAPP_APP_SECRET: str = ""

    # ── INTEGRATION / IMPORT ──────────────────────────────
    IMPORT_BATCH_SIZE: int = 200

    # ── VALIDATORS ────────────────────────────────────────
    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("DATABASE_URL zorunlu")
        return normalize_asyncpg_url(v.strip())

    # ── PROPERTIES ────────────────────────────────────────
    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() in {"production", "prod", "staging"}


settings = Settings()
