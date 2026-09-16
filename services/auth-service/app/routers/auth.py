"""
Auth router: /auth/register, /auth/login, /auth/refresh, /auth/logout, /auth/me
"""
from typing import Optional

from fastapi import APIRouter, Depends, status, Request, Response, Cookie, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.auth import (
    ClinicRegisterRequest,
    ClinicRegisterResponse,
    CurrentUserResponse,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
)
from app.services.auth_service import (
    login,
    logout,
    refresh_access_token,
    register_clinic,
)
from app.models.user import User
from app.models.clinic import Clinic
from sqlalchemy import select, text

# ── Rate Limiting ──────────────────────────────────────
from shared.rate_limiter import rate_limit

router = APIRouter(prefix="/auth", tags=["Auth"])

REFRESH_COOKIE_NAME = "dentai_refresh_token"


def _cookie_security() -> dict:
    """
    Cross-site (Vercel UI → Railway API) için production'da
    SameSite=None + Secure zorunlu. Localhost'ta Lax yeterli.
    """
    if settings.is_production:
        return {"secure": True, "samesite": "none"}
    return {"secure": False, "samesite": "lax"}


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Store refresh token in httpOnly cookie (XSS-safe)."""
    sec = _cookie_security()
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=sec["secure"],
        samesite=sec["samesite"],
        max_age=60 * 60 * 24 * 30,
        path="/",
    )


def _clear_refresh_cookie(response: Response) -> None:
    sec = _cookie_security()
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/",
        secure=sec["secure"],
        samesite=sec["samesite"],
    )

@router.post(
    "/register",
    response_model=ClinicRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Yeni klinik ve admin kullanıcısı oluştur",
)
@rate_limit(max_requests=5, window_seconds=3600)  # 5 registrations per hour
async def register(
    request: Request,
    data: ClinicRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> ClinicRegisterResponse:
    if not settings.ALLOW_PUBLIC_REGISTER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public registration is disabled",
        )
    return await register_clinic(data, db)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Email/Şifre ile giriş yap — Access & Refresh Token döner",
)
@rate_limit(max_requests=10, window_seconds=60)  # 10 login attempts per minute
async def login_endpoint(
    request: Request,
    response: Response,
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    token_response = await login(data, db)
    _set_refresh_cookie(response, token_response.refresh_token)
    return token_response


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh token ile yeni Access Token al (token rotation)",
)
@rate_limit(max_requests=30, window_seconds=60)  # 30 refreshes per minute
async def refresh_endpoint(
    request: Request,
    response: Response,
    data: dict | None = Body(default=None),
    refresh_cookie: Optional[str] = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    refresh_token = (data.get("refresh_token") if data else None) or refresh_cookie
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")

    token_response = await refresh_access_token(refresh_token, db)
    _set_refresh_cookie(response, token_response.refresh_token)
    return token_response


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Refresh token'ı iptal et",
)
async def logout_endpoint(
    response: Response,
    data: dict | None = Body(default=None),
    refresh_cookie: Optional[str] = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> None:
    refresh_token = (data.get("refresh_token") if data else None) or refresh_cookie
    if refresh_token:
        await logout(refresh_token, db)
    _clear_refresh_cookie(response)


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="Mevcut kullanıcı bilgilerini döndür",
)
async def me(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CurrentUserResponse:
    if current_user.get('clinic_id'):
        await db.execute(
            text("SELECT set_config('app.current_clinic_id', :cid, true)").bindparams(cid=str(current_user['clinic_id'])),
        )
    result = await db.execute(
        select(User).where(User.id == current_user["user_id"])
    )
    user = result.scalar_one_or_none()
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    # Fetch clinic code and email_domain
    clinic_code = None
    clinic_email_domain = None
    if user.clinic_id:
        clinic_result = await db.execute(
            select(Clinic.code, Clinic.email_domain).where(Clinic.id == user.clinic_id)
        )
        clinic_row = clinic_result.one_or_none()
        clinic_code = clinic_row[0] if clinic_row else None
        clinic_email_domain = clinic_row[1] if clinic_row else None
    return CurrentUserResponse.from_user(user, clinic_code=clinic_code, clinic_email_domain=clinic_email_domain)
