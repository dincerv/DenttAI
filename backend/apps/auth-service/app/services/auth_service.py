"""
Auth iş mantığı: register, login, refresh, logout
"""
import re
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from email_validator import validate_email, EmailNotValidError

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.clinic import Clinic
from app.models.user import RefreshToken, User, UserRole

import uuid as _uuid
from app.schemas.auth import (
    ClinicRegisterRequest,
    ClinicRegisterResponse,
    LoginRequest,
    TokenResponse,
)


async def register_clinic(
    data: ClinicRegisterRequest, db: AsyncSession
) -> ClinicRegisterResponse:
    """
    1. Slug benzersizliğini kontrol et
    2. Klinik oluştur (RLS bypass: henüz tenant yok)
    3. Owner kullanıcısı oluştur
    """
    # Email validation (⚠️ prevent invalid email from DB)
    try:
        validated_email = validate_email(data.admin_email.strip()).normalized
    except EmailNotValidError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Geçersiz e-posta adresi formatı",
        )
    
    slug = data.clinic_slug.lower().strip()

    # Slug çakışma kontrolü (RLS bypass için text() kullanılır)
    existing = await db.execute(
        select(Clinic).where(Clinic.slug == slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"'{slug}' slug'ı zaten kullanımda",
        )

    clinic = Clinic(name=data.clinic_name, slug=slug)
    db.add(clinic)
    await db.flush()  # clinic.id üretildi

    user = User(
        clinic_id=clinic.id,
        email=validated_email,  # Use validated + normalized email
        hashed_password=hash_password(data.admin_password),
        full_name=data.admin_full_name,
        role=UserRole.owner,
    )
    db.add(user)
    await db.flush()

    return ClinicRegisterResponse(clinic_id=clinic.id, user_id=user.id)


async def login(data: LoginRequest, db: AsyncSession) -> TokenResponse:
    """
    1. clinic_code varsa code ile, clinic_slug varsa slug ile, yoksa email'e göre klinik bul
    2. Email + şifre kontrol
    3. Access + Refresh token üret
    """
    # Email validation (⚠️ prevent invalid email from causing DB issues)
    try:
        validated_email = validate_email(data.email.strip()).normalized
    except EmailNotValidError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Geçersiz e-posta adresi formatı",
        )
    
    # ── Super admin fast-path (klinik gerekmez) ──────────────────────────
    sa_result = await db.execute(
        select(User).where(
            User.email == validated_email,
            User.clinic_id == None,
            User.is_active == True,
            User.role == UserRole.super_admin,
        )
    )
    sa_user = sa_result.scalar_one_or_none()
    if sa_user:
        if not verify_password(data.password, sa_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Geçersiz email veya şifre",
            )
        sa_token = create_access_token(
            clinic_id=None,
            user_id=sa_user.id,
            role="super_admin",
            full_name=sa_user.full_name,
            allowed_pages=[],
        )
        sa_raw_refresh, sa_refresh_hash = create_refresh_token(sa_user.id)
        sa_expires = datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS)
        db.add(RefreshToken(user_id=sa_user.id, token_hash=sa_refresh_hash, expires_at=sa_expires))
        return TokenResponse(
            access_token=sa_token,
            refresh_token=sa_raw_refresh,
            expires_in=settings.JWT_ACCESS_EXPIRE_MINUTES * 60,
        )

    # ── Normal klinik tabanlı login ───────────────────────────────────────
    # Klinik bul
    clinic = None
    if data.clinic_code:
        clinic_result = await db.execute(
            select(Clinic).where(Clinic.code == data.clinic_code.upper(), Clinic.is_active == True)
        )
        clinic = clinic_result.scalar_one_or_none()
    elif data.clinic_slug:
        # Geriye dönük uyumluluk (eski slug format)
        clinic_result = await db.execute(
            select(Clinic).where(Clinic.slug == data.clinic_slug, Clinic.is_active == True)
        )
        clinic = clinic_result.scalar_one_or_none()
    else:
        # email'e göre kullanıcı ara, oradan kliniği al
        user_result = await db.execute(
            select(User).where(User.email == validated_email, User.is_active == True)
        )
        user_rows = user_result.scalars().all()
        if len(user_rows) > 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Bu e-posta birden fazla klinikte kayıtlı. Lütfen klinik kodunu da girin.",
            )
        user_row = user_rows[0] if user_rows else None
        if user_row:
            clinic_result = await db.execute(
                select(Clinic).where(Clinic.id == user_row.clinic_id, Clinic.is_active == True)
            )
            clinic = clinic_result.scalar_one_or_none()
    if not clinic:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz klinik, email veya şifre",
        )

    # RLS context'ini set et (parameterized query - SQL injection koruması)
    await db.execute(
        text("SELECT set_config('app.current_clinic_id', :cid, true)").bindparams(cid=str(clinic.id)),
    )

    # Kullanıcı bul
    user_result = await db.execute(
        select(User).where(
            User.email == validated_email,
            User.clinic_id == clinic.id,
            User.is_active == True,
        )
    )
    user = user_result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz klinik, email veya şifre",
        )

    # Doktor ise doctor_id'yi doctors tablosundan al (önce user_id ile, sonra full_name fallback)
    doctor_id: _uuid.UUID | None = None
    if user.role.value == "doctor":
        try:
            dr_result = await db.execute(
                text(
                    "SELECT id FROM doctors "
                    "WHERE clinic_id = :cid AND (user_id = :uid OR full_name = :fname) "
                    "LIMIT 1"
                ),
                {"cid": str(clinic.id), "uid": str(user.id), "fname": user.full_name},
            )
            dr_row = dr_result.fetchone()
            if dr_row:
                doctor_id = dr_row[0]
        except Exception:
            pass

    # Token üret
    access_token = create_access_token(
        clinic_id=clinic.id,
        user_id=user.id,
        role=user.role.value,
        doctor_id=doctor_id,
        full_name=user.full_name,
        allowed_pages=user.allowed_pages or [],
    )
    raw_refresh, refresh_hash = create_refresh_token(user.id)

    # Refresh token'ı kaydet
    expires = datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=refresh_hash,
            expires_at=expires,
        )
    )

    await db.commit()
    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        expires_in=settings.JWT_ACCESS_EXPIRE_MINUTES * 60,
    )


async def refresh_access_token(raw_token: str, db: AsyncSession) -> TokenResponse:
    """
    Refresh token hash'ini veritabanında ara; yenileri üret.
    """
    token_hash = hash_refresh_token(raw_token)
    now = datetime.now(UTC)

    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False,
            RefreshToken.expires_at > now,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz veya süresi dolmuş refresh token",
        )

    # Kullanıcı bilgisi
    user_result = await db.execute(
        select(User).where(User.id == record.user_id, User.is_active == True)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Kullanıcı bulunamadı")

    # Eski token'ı iptal et (token rotation)
    record.revoked = True

    # Refresh'te de doctor_id'yi yeniden hesapla
    _doctor_id: _uuid.UUID | None = None
    if user.role.value == "doctor":
        try:
            _dr = await db.execute(
                text(
                    "SELECT id FROM doctors "
                    "WHERE clinic_id = :cid AND (user_id = :uid OR full_name = :fname) "
                    "LIMIT 1"
                ),
                {"cid": str(user.clinic_id), "uid": str(user.id), "fname": user.full_name},
            )
            _dr_row = _dr.fetchone()
            if _dr_row:
                _doctor_id = _dr_row[0]
        except Exception:
            pass

    access_token = create_access_token(
        clinic_id=user.clinic_id,
        user_id=user.id,
        role=user.role.value,
        doctor_id=_doctor_id,
        full_name=user.full_name,
        allowed_pages=user.allowed_pages or [],
    )
    raw_new, new_hash = create_refresh_token(user.id)

    expires = datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=new_hash,
            expires_at=expires,
        )
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_new,
        expires_in=settings.JWT_ACCESS_EXPIRE_MINUTES * 60,
    )


async def logout(raw_token: str, db: AsyncSession) -> None:
    """Refresh token'ı iptal eder."""
    token_hash = hash_refresh_token(raw_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    record = result.scalar_one_or_none()
    if record:
        record.revoked = True
