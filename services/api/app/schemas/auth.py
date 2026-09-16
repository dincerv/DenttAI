"""
Pydantic şeması: Auth (login, register, token)
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user import UserRole


# ── Register ─────────────────────────────────────────────

class ClinicRegisterRequest(BaseModel):
    """Yeni klinik + ilk admin kullanıcısı oluşturur."""
    clinic_name: str = Field(..., min_length=2, max_length=255)
    clinic_slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    admin_full_name: str = Field(..., min_length=2, max_length=255)
    admin_email: EmailStr
    admin_password: str = Field(..., min_length=8)

    @field_validator("admin_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isdigit() for c in v):
            raise ValueError("Şifre en az bir rakam içermelidir")
        if not any(c.isupper() for c in v):
            raise ValueError("Şifre en az bir büyük harf içermelidir")
        return v


class ClinicRegisterResponse(BaseModel):
    clinic_id: uuid.UUID
    user_id: uuid.UUID
    message: str = "Klinik başarıyla oluşturuldu"


# ── Login ────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str = Field(..., pattern=r'^[^@]+@[^@]+')
    password: str
    clinic_slug: str | None = Field(None, description="Eski format (uyumluluk)")
    clinic_code: str | None = Field(None, description="6 haneli klinik kodu")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # saniye cinsinden


# ── Refresh ──────────────────────────────────────────────

class RefreshRequest(BaseModel):
    refresh_token: str


# ── Current user ─────────────────────────────────────────

class CurrentUserResponse(BaseModel):
    user_id: uuid.UUID
    clinic_id: uuid.UUID | None = None
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    allowed_pages: list[str]
    clinic_code: str | None = None
    clinic_email_domain: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}

    @classmethod
    def from_user(cls, obj, clinic_code: str | None = None, clinic_email_domain: str | None = None):
        data = {
            "user_id": obj.id,
            "clinic_id": obj.clinic_id,
            "email": obj.email,
            "full_name": obj.full_name,
            "role": obj.role,
            "is_active": obj.is_active,
            "allowed_pages": obj.allowed_pages or [],
            "clinic_code": clinic_code,
            "clinic_email_domain": clinic_email_domain,
            "created_at": obj.created_at,
        }
        return cls(**data)

    @classmethod
    def model_validate(cls, obj, **kwargs):  # type: ignore[override]
        # User ORM nesnesinin `id` alanını `user_id` olarak eşleştir
        if hasattr(obj, "id") and not hasattr(obj, "user_id"):
            data = {
                "user_id": obj.id,
                "clinic_id": obj.clinic_id,
                "email": obj.email,
                "full_name": obj.full_name,
                "role": obj.role,
                "is_active": obj.is_active,
                "allowed_pages": obj.allowed_pages or [],
                "clinic_code": None,
                "clinic_email_domain": None,
                "created_at": obj.created_at,
            }
            return cls(**data)
        return super().model_validate(obj, **kwargs)
