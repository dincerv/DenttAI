"""
JWT üretimi, doğrulaması ve bcrypt şifre yönetimi.
"""
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# ── Şifre hash bağlamı ───────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT ──────────────────────────────────────────────────

def _build_payload(data: dict[str, Any], expires_delta: timedelta) -> dict[str, Any]:
    payload = data.copy()
    payload["exp"] = datetime.now(UTC) + expires_delta
    payload["iat"] = datetime.now(UTC)
    return payload


def create_access_token(
    clinic_id: UUID | None,
    user_id: UUID,
    role: str,
    doctor_id: UUID | None = None,
    full_name: str | None = None,
    allowed_pages: list[str] | None = None,
    expires_minutes: int | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    claims: dict = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
    }
    if clinic_id is not None:
        claims["clinic_id"] = str(clinic_id)
    if doctor_id is not None:
        claims["doctor_id"] = str(doctor_id)
    if full_name is not None:
        claims["full_name"] = full_name
    if allowed_pages is not None:
        claims["allowed_pages"] = allowed_pages
    if extra_claims:
        claims.update(extra_claims)
    payload = _build_payload(
        claims,
        timedelta(minutes=expires_minutes or settings.JWT_ACCESS_EXPIRE_MINUTES),
    )
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: UUID) -> tuple[str, str]:
    """
    Returns (raw_token, token_hash).
    raw_token → istemciye gönderilir.
    token_hash → veritabanına kaydedilir.
    """
    raw = secrets.token_urlsafe(64)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    return raw, token_hash


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Raises JWTError on any validation failure.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("type") != "access":
            raise JWTError("Not an access token")
        return payload
    except JWTError:
        raise


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
