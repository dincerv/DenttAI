"""
DentAI Flow — Shared Auth Middleware
======================================
Diğer mikroservislerin (Appointment, Inventory, Analytics vb.) import edip
kullanacağı ortak JWT doğrulama ve RLS context ayarlama katmanı.

Kullanım (herhangi bir FastAPI serviste):

    from shared.auth_middleware import get_verified_claims, set_rls_context, require_role

    @router.get("/appointments")
    async def list_appointments(
        claims: dict = Depends(get_verified_claims),
        db: AsyncSession = Depends(get_db),
    ):
        await set_rls_context(db, claims["clinic_id"])
        ...
"""
from __future__ import annotations

import os
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# ── Konfigürasyon ────────────────────────────────────────
# ConfigValidator, başlangıçta tüm zorunlu secrets'ları doğrular.
# Eğer JWT_SECRET set edilmemişse, uygulama başlatılmaz.
try:
    from config_validator import ConfigValidator
    _config = ConfigValidator.validate()
    _JWT_SECRET: str = _config["JWT_SECRET"]
except ImportError:
    # Fallback (sadece test/dev için)
    _JWT_SECRET: str = os.environ.get("JWT_SECRET", "")
    if not _JWT_SECRET:
        raise RuntimeError("JWT_SECRET environment variable is required")

_JWT_ALGORITHM: str = os.environ.get("JWT_ALGORITHM", "HS256")

bearer_scheme = HTTPBearer()


# ── JWT Doğrulama ─────────────────────────────────────────

def _decode_token(token: str) -> dict[str, Any]:
    """
    Token'ı decode et ve temel alanları doğrula.
    Raises HTTPException(401) geçersiz token için.
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            _JWT_SECRET,
            algorithms=[_JWT_ALGORITHM],
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz veya süresi dolmuş token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz token tipi",
        )

    if not payload.get("sub") or not payload.get("role"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token içeriği eksik",
        )

    # clinic_id yalnızca super_admin dışındaki roller için zorunlu
    if payload.get("role") != "super_admin" and not payload.get("clinic_id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token içeriği eksik",
        )

    return payload


async def get_verified_claims(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict[str, Any]:
    """
    FastAPI dependency — Bearer token'ı doğrular ve claim sözlüğü döner.

    Dönen dict:
        {
            "user_id": UUID,
            "clinic_id": UUID,
            "role": str,    # "owner" | "doctor" | "assistant"
        }
    """
    payload = _decode_token(credentials.credentials)
    return {
        "user_id": UUID(payload["sub"]),
        "clinic_id": UUID(payload["clinic_id"]) if payload.get("clinic_id") else None,
        "role": payload["role"],
        "allowed_pages": payload.get("allowed_pages") or [],
        "impersonation": bool(payload.get("impersonation", False)),
        "impersonated_clinic_id": (
            UUID(payload["impersonated_clinic_id"])
            if payload.get("impersonated_clinic_id")
            else None
        ),
        # Optional — present only when role=doctor
        "doctor_id": UUID(payload["doctor_id"]) if payload.get("doctor_id") else None,
        "full_name": payload.get("full_name"),
    }


# ── RLS Context ───────────────────────────────────────────

async def set_rls_context(db: AsyncSession, clinic_id: UUID) -> None:
    """
    PostgreSQL oturumunda RLS context'ini ayarlar.
    Her DB işleminden önce çağrılmalıdır.
    
    ⚠️ Parameterized query kullanılır (SQL injection koruması).

    Kullanım:
        await set_rls_context(db, claims["clinic_id"])
    """
    await db.execute(
        text("SELECT set_config('app.current_clinic_id', :cid, true)").bindparams(cid=str(clinic_id)),
    )


# ── Rol Kontrolü ─────────────────────────────────────────

def require_role(*allowed_roles: str):
    """
    Dependency factory — belirtilen rollere kısıtlar.
    super_admin her zaman geçer.

    Kullanım:
        @router.delete("/", dependencies=[Depends(require_role("owner"))])
    """
    async def _check(
        claims: dict = Depends(get_verified_claims),
    ) -> dict:
        if claims["role"] == "super_admin":
            return claims
        if claims["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Bu işlem için yetki gerekiyor: {list(allowed_roles)}",
            )
        return claims

    return _check


def require_not_role(*blocked_roles: str):
    """
    Dependency factory — belirtilen rolleri engeller, diğerlerine izin verir.

    Kullanım:
        @router.get("/", dependencies=[Depends(require_not_role("assistant"))])
    """
    async def _check(
        claims: dict = Depends(get_verified_claims),
    ) -> dict:
        if claims["role"] in blocked_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu bilgilere erişim yetkiniz bulunmuyor",
            )
        return claims

    return _check


def require_page_permission(page: str):
    """
    Dependency factory — JWT claim içindeki allowed_pages alanından sayfa yetkisi arar.
    super_admin ve owner her zaman geçer.

    Not:
    - Bu kontrol access token claim'ine dayanır.
    - allowed_pages değişikliklerinin yansıması için kullanıcının yeni token alması gerekir.
    """

    async def _check(
        claims: dict = Depends(get_verified_claims),
    ) -> dict:
        role = claims.get("role")
        if role in ("super_admin", "owner"):
            return claims

        allowed_pages = claims.get("allowed_pages") or []
        if page not in allowed_pages:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Bu işlem için '{page}' yetkisi gerekiyor",
            )
        return claims

    return _check
