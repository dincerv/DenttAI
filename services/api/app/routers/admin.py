"""
Super Admin Router — /auth/admin
Tüm klinikleri yönet, kliniklere kullanıcı ekle.
Yalnızca super_admin rolüne sahip kullanıcılar erişebilir.
"""
import uuid
import random
import string
from enum import Enum
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import text as sa_text

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.models.clinic import Clinic
from app.models.user import User, UserRole

router = APIRouter(
    prefix="/auth/admin",
    tags=["Super Admin"],
    dependencies=[Depends(require_role("super_admin"))],
)


# ── Pydantic şemaları ─────────────────────────────────────────────────────

class ClinicSummary(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    code: str | None = None
    email_domain: str | None = None
    is_active: bool
    user_count: int
    created_at: Any  # datetime

    model_config = {"from_attributes": True}


class ClinicsListResponse(BaseModel):
    total: int
    items: list[ClinicSummary]


class AddUserRequest(BaseModel):
    email: str = Field(..., pattern=r'^[^@]+@[^@]+$')
    full_name: str = Field(..., min_length=2, max_length=255)
    password: str = Field(..., min_length=6)
    role: UserRole = UserRole.assistant


class AddUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    clinic_id: uuid.UUID

    model_config = {"from_attributes": True}


# ── Endpoint'ler ──────────────────────────────────────────────────────────

@router.get(
    "/clinics",
    response_model=ClinicsListResponse,
    summary="Tüm klinikleri ve kullanıcı sayısını listele",
)
async def list_clinics(
    db: AsyncSession = Depends(get_db),
) -> ClinicsListResponse:
    """Sistemdeki tüm klinikleri kullanıcı sayısıyla döndürür."""
    # Klinikler + alt sorgu olarak user_count
    user_count_subq = (
        select(User.clinic_id, func.count(User.id).label("cnt"))
        .group_by(User.clinic_id)
        .subquery()
    )

    result = await db.execute(
        select(
            Clinic.id,
            Clinic.name,
            Clinic.slug,
            Clinic.code,
            Clinic.email_domain,
            Clinic.is_active,
            Clinic.created_at,
            func.coalesce(user_count_subq.c.cnt, 0).label("user_count"),
        )
        .outerjoin(user_count_subq, Clinic.id == user_count_subq.c.clinic_id)
        .order_by(Clinic.created_at.asc())
    )
    rows = result.mappings().all()

    items = [
        ClinicSummary(
            id=row["id"],
            name=row["name"],
            slug=row["slug"],
            code=row["code"],
            email_domain=row["email_domain"],
            is_active=row["is_active"],
            created_at=row["created_at"],
            user_count=row["user_count"],
        )
        for row in rows
    ]
    return ClinicsListResponse(total=len(items), items=items)


@router.get(
    "/clinics/{clinic_id}/users",
    summary="Bir kliniğin kullanıcılarını listele",
)
async def list_clinic_users(
    clinic_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    result = await db.execute(
        select(User.id, User.email, User.full_name, User.role, User.is_active, User.created_at)
        .where(User.clinic_id == clinic_id)
        .order_by(User.created_at.asc())
    )
    rows = result.mappings().all()
    return [dict(r) for r in rows]


@router.post(
    "/clinics/{clinic_id}/users",
    response_model=AddUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Bir kliniğe yeni kullanıcı ekle",
)
async def add_user_to_clinic(
    clinic_id: uuid.UUID,
    data: AddUserRequest,
    db: AsyncSession = Depends(get_db),
) -> AddUserResponse:
    """Belirtilen kliniğe yeni bir kullanıcı oluşturur."""
    # Klinik var mı?
    clinic = await db.get(Clinic, clinic_id)
    if not clinic:
        raise HTTPException(status_code=404, detail="Klinik bulunamadı")

    # E-posta bu klinikte zaten kullanılıyor mu?
    existing = await db.execute(
        select(User).where(User.email == data.email, User.clinic_id == clinic_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Bu e-posta bu klinikte zaten kayıtlı")

    new_user = User(
        clinic_id=clinic_id,
        email=data.email,
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
        role=data.role,
        is_active=True,
    )
    db.add(new_user)
    await db.flush()  # get new_user.id before committing

    # Doktor rolü ise doctors tablosuna da kaydet
    if data.role == UserRole.doctor:
        await db.execute(
            sa_text("""
                INSERT INTO doctors (clinic_id, full_name, user_id)
                VALUES (:clinic_id, :full_name, :user_id)
                ON CONFLICT DO NOTHING
            """),
            {"clinic_id": str(clinic_id),
             "full_name": data.full_name,
             "user_id": str(new_user.id)},
        )

    await db.commit()
    await db.refresh(new_user)

    return AddUserResponse(
        id=new_user.id,
        email=new_user.email,
        full_name=new_user.full_name,
        role=new_user.role.value,
        clinic_id=new_user.clinic_id,
    )


# ── Yeni klinik oluşturma şeması ─────────────────────────────────────────

class CreateClinicRequest(BaseModel):
    clinic_name: str = Field(..., min_length=2, max_length=255)
    clinic_slug: str | None = Field(None, pattern=r"^[a-z0-9-]+$", min_length=2, max_length=100)
    clinic_code: str | None = Field(None, min_length=4, max_length=6)
    owner_email: str | None = Field(None, pattern=r'^[^@]+@[^@]+$')
    owner_password: str | None = Field(None, min_length=6)
    owner_full_name: str | None = None


class UpdateClinicRequest(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    is_active: bool | None = None


class PlatformStatsResponse(BaseModel):
    total_clinics: int
    active_clinics: int
    total_users: int


class AIUsagePeriod(str, Enum):
    day = "day"
    week = "week"
    month = "month"
    year = "year"


class ClinicAIUsageSummary(BaseModel):
    clinic_id: uuid.UUID
    clinic_name: str
    clinic_slug: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    ai_cost_usd: float
    whatsapp_message_count: int
    whatsapp_cost_usd: float
    total_cost_usd: float
    request_count: int
    last_usage_at: datetime | None


class ClinicsAIUsageResponse(BaseModel):
    period: AIUsagePeriod
    range_start: datetime
    range_end: datetime
    items: list[ClinicAIUsageSummary]


# ── Klinik oluştur ────────────────────────────────────────────────────────

@router.post(
    "/clinics",
    response_model=ClinicSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Yeni klinik oluştur",
)
async def create_clinic(
    data: CreateClinicRequest,
    db: AsyncSession = Depends(get_db),
) -> ClinicSummary:
    """Yeni klinik oluşturur; isteğe bağlı olarak ilk owner kullanıcısını da ekler."""
    # Klinik kodu: istendiğinde belirlenmiş, yoksa benzersiz üret
    code = (data.clinic_code or _generate_code()).upper()
    # Benzersizlik kontrolü
    existing_code = await db.execute(select(Clinic).where(Clinic.code == code))
    if existing_code.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"'{code}' kodu zaten kullanımda")

    # Slug: klinik adından otomatik üret
    import re
    slug_base = data.clinic_name.lower()
    for src, dst in [('ğ','g'),('ü','u'),('ş','s'),('ı','i'),('ö','o'),('ç','c')]:
        slug_base = slug_base.replace(src, dst)
    slug = re.sub(r'[^a-z0-9]+', '-', slug_base).strip('-')[:50]
    # Slug çakışması varsa suffix ekle
    base_slug, suffix = slug, 0
    while (await db.execute(select(Clinic).where(Clinic.slug == slug))).scalar_one_or_none():
        suffix += 1
        slug = f"{base_slug}-{suffix}"

    # Email domain: owner_email'in @ sonrasından al
    email_domain: str | None = None
    if data.owner_email:
        email_domain = data.owner_email.split('@', 1)[1].lower()

    clinic = Clinic(name=data.clinic_name, slug=slug, code=code, email_domain=email_domain)
    db.add(clinic)
    await db.flush()

    has_owner = bool(data.owner_email and data.owner_password and data.owner_full_name)
    if has_owner:
        owner = User(
            clinic_id=clinic.id,
            email=data.owner_email.lower(),  # type: ignore[union-attr]
            hashed_password=hash_password(data.owner_password),  # type: ignore[arg-type]
            full_name=data.owner_full_name,
            role=UserRole.owner,
            is_active=True,
        )
        db.add(owner)
        await db.flush()

    await db.commit()
    await db.refresh(clinic)

    return ClinicSummary(
        id=clinic.id,
        name=clinic.name,
        slug=clinic.slug,
        code=clinic.code,
        email_domain=clinic.email_domain,
        is_active=clinic.is_active,
        created_at=clinic.created_at,
        user_count=1 if has_owner else 0,
    )


# ── Klinik güncelle (ad, aktiflik) ────────────────────────────────────────

@router.patch(
    "/clinics/{clinic_id}",
    response_model=ClinicSummary,
    summary="Klinik güncelle (ad, aktiflik durumu)",
)
async def update_clinic(
    clinic_id: uuid.UUID,
    data: UpdateClinicRequest,
    db: AsyncSession = Depends(get_db),
) -> ClinicSummary:
    """Klinik adını veya aktiflik durumunu günceller."""
    clinic = await db.get(Clinic, clinic_id)
    if not clinic:
        raise HTTPException(status_code=404, detail="Klinik bulunamadı")

    if data.name is not None:
        clinic.name = data.name
    if data.is_active is not None:
        clinic.is_active = data.is_active

    await db.commit()
    await db.refresh(clinic)

    user_count_result = await db.execute(
        select(func.count(User.id)).where(User.clinic_id == clinic_id)
    )
    user_count = user_count_result.scalar_one() or 0

    return ClinicSummary(
        id=clinic.id,
        name=clinic.name,
        slug=clinic.slug,
        code=clinic.code,
        email_domain=clinic.email_domain,
        is_active=clinic.is_active,
        created_at=clinic.created_at,
        user_count=user_count,
    )


# ── Platform istatistikleri ───────────────────────────────────────────────

@router.get(
    "/stats",
    response_model=PlatformStatsResponse,
    summary="Platform geneli istatistikler",
)
async def platform_stats(
    db: AsyncSession = Depends(get_db),
) -> PlatformStatsResponse:
    """Toplam klinik, aktif klinik ve kullanıcı sayısını döndürür."""
    total_result = await db.execute(select(func.count(Clinic.id)))
    total = total_result.scalar_one() or 0

    active_result = await db.execute(
        select(func.count(Clinic.id)).where(Clinic.is_active == True)
    )
    active = active_result.scalar_one() or 0

    users_result = await db.execute(
        select(func.count(User.id)).where(User.role != UserRole.super_admin)
    )
    total_users = users_result.scalar_one() or 0

    return PlatformStatsResponse(
        total_clinics=total,
        active_clinics=active,
        total_users=total_users,
    )


@router.get(
    "/ai-usage",
    response_model=ClinicsAIUsageResponse,
    summary="Klinik bazli AI token ve maliyet raporu",
)
async def clinics_ai_usage(
    period: AIUsagePeriod = AIUsagePeriod.month,
    db: AsyncSession = Depends(get_db),
) -> ClinicsAIUsageResponse:
    """Seçilen döneme göre tüm kliniklerin AI kullanımını döndürür."""
    now = datetime.now(timezone.utc)
    delta_map: dict[AIUsagePeriod, timedelta] = {
        AIUsagePeriod.day: timedelta(days=1),
        AIUsagePeriod.week: timedelta(days=7),
        AIUsagePeriod.month: timedelta(days=30),
        AIUsagePeriod.year: timedelta(days=365),
    }
    range_start = now - delta_map[period]
    whatsapp_unit_cost_usd = max(0.0, float(settings.WHATSAPP_MESSAGE_COST_USD))

    try:
        result = await db.execute(
            sa_text(
                """
                WITH ai AS (
                    SELECT
                        clinic_id,
                        COALESCE(SUM(prompt_tokens), 0)::bigint AS prompt_tokens,
                        COALESCE(SUM(completion_tokens), 0)::bigint AS completion_tokens,
                        COALESCE(SUM(total_tokens), 0)::bigint AS total_tokens,
                        COALESCE(SUM(cost_usd), 0)::double precision AS ai_cost_usd,
                        COALESCE(COUNT(id), 0)::bigint AS request_count,
                        MAX(created_at) AS last_usage_at
                    FROM ai_usage_events
                    WHERE created_at >= :range_start
                      AND created_at <= :range_end
                    GROUP BY clinic_id
                ),
                wa AS (
                    SELECT
                        clinic_id,
                        COALESCE(COUNT(id), 0)::bigint AS whatsapp_message_count,
                        MAX(created_at) AS last_message_at
                    FROM whatsapp_message_log
                    WHERE created_at >= :range_start
                      AND created_at <= :range_end
                      AND status IN ('sent', 'delivered', 'read')
                    GROUP BY clinic_id
                )
                SELECT
                    c.id AS clinic_id,
                    c.name AS clinic_name,
                    c.slug AS clinic_slug,
                    COALESCE(ai.prompt_tokens, 0)::bigint AS prompt_tokens,
                    COALESCE(ai.completion_tokens, 0)::bigint AS completion_tokens,
                    COALESCE(ai.total_tokens, 0)::bigint AS total_tokens,
                    COALESCE(ai.ai_cost_usd, 0)::double precision AS ai_cost_usd,
                    COALESCE(wa.whatsapp_message_count, 0)::bigint AS whatsapp_message_count,
                    (COALESCE(wa.whatsapp_message_count, 0) * :whatsapp_unit_cost_usd)::double precision AS whatsapp_cost_usd,
                    (COALESCE(ai.ai_cost_usd, 0) + (COALESCE(wa.whatsapp_message_count, 0) * :whatsapp_unit_cost_usd))::double precision AS total_cost_usd,
                    COALESCE(ai.request_count, 0)::bigint AS request_count,
                    COALESCE(GREATEST(ai.last_usage_at, wa.last_message_at), ai.last_usage_at, wa.last_message_at) AS last_usage_at
                FROM clinics c
                LEFT JOIN ai ON ai.clinic_id = c.id
                LEFT JOIN wa ON wa.clinic_id = c.id
                ORDER BY total_cost_usd DESC, total_tokens DESC, c.name ASC
                """
            ),
            {
                "range_start": range_start,
                "range_end": now,
                "whatsapp_unit_cost_usd": whatsapp_unit_cost_usd,
            },
        )
        rows = result.mappings().all()
    except ProgrammingError as exc:
        if "whatsapp_message_log" not in str(exc):
            raise
        await db.rollback()
        result = await db.execute(
            sa_text(
                """
                WITH ai AS (
                    SELECT
                        clinic_id,
                        COALESCE(SUM(prompt_tokens), 0)::bigint AS prompt_tokens,
                        COALESCE(SUM(completion_tokens), 0)::bigint AS completion_tokens,
                        COALESCE(SUM(total_tokens), 0)::bigint AS total_tokens,
                        COALESCE(SUM(cost_usd), 0)::double precision AS ai_cost_usd,
                        COALESCE(COUNT(id), 0)::bigint AS request_count,
                        MAX(created_at) AS last_usage_at
                    FROM ai_usage_events
                    WHERE created_at >= :range_start
                      AND created_at <= :range_end
                    GROUP BY clinic_id
                )
                SELECT
                    c.id AS clinic_id,
                    c.name AS clinic_name,
                    c.slug AS clinic_slug,
                    COALESCE(ai.prompt_tokens, 0)::bigint AS prompt_tokens,
                    COALESCE(ai.completion_tokens, 0)::bigint AS completion_tokens,
                    COALESCE(ai.total_tokens, 0)::bigint AS total_tokens,
                    COALESCE(ai.ai_cost_usd, 0)::double precision AS ai_cost_usd,
                    0::bigint AS whatsapp_message_count,
                    0::double precision AS whatsapp_cost_usd,
                    COALESCE(ai.ai_cost_usd, 0)::double precision AS total_cost_usd,
                    COALESCE(ai.request_count, 0)::bigint AS request_count,
                    ai.last_usage_at AS last_usage_at
                FROM clinics c
                LEFT JOIN ai ON ai.clinic_id = c.id
                ORDER BY total_cost_usd DESC, total_tokens DESC, c.name ASC
                """
            ),
            {
                "range_start": range_start,
                "range_end": now,
            },
        )
        rows = result.mappings().all()
    items = [
        ClinicAIUsageSummary(
            clinic_id=row["clinic_id"],
            clinic_name=row["clinic_name"],
            clinic_slug=row["clinic_slug"],
            prompt_tokens=int(row["prompt_tokens"] or 0),
            completion_tokens=int(row["completion_tokens"] or 0),
            total_tokens=int(row["total_tokens"] or 0),
            ai_cost_usd=float(row["ai_cost_usd"] or 0),
            whatsapp_message_count=int(row["whatsapp_message_count"] or 0),
            whatsapp_cost_usd=float(row["whatsapp_cost_usd"] or 0),
            total_cost_usd=float(row["total_cost_usd"] or 0),
            request_count=int(row["request_count"] or 0),
            last_usage_at=row["last_usage_at"],
        )
        for row in rows
    ]

    return ClinicsAIUsageResponse(
        period=period,
        range_start=range_start,
        range_end=now,
        items=items,
    )


# ── Klinik sil ────────────────────────────────────────────────────────────

@router.delete(
    "/clinics/{clinic_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Kliniği ve tüm verilerini sil",
)
async def delete_clinic(
    clinic_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Kliniği ve cascade ile tüm kullanıcı/verilerini siler."""
    clinic = await db.get(Clinic, clinic_id)
    if not clinic:
        raise HTTPException(status_code=404, detail="Klinik bulunamadı")
    # Raw SQL DELETE ile PostgreSQL ON DELETE CASCADE tetiklenir
    await db.execute(sa_text("DELETE FROM clinics WHERE id = :cid"), {"cid": str(clinic_id)})
    await db.commit()


# ── Klinik impersonation token ────────────────────────────────────────────

class ImpersonateResponse(BaseModel):
    access_token: str
    clinic_name: str
    clinic_slug: str


@router.post(
    "/clinics/{clinic_id}/impersonate",
    response_model=ImpersonateResponse,
    summary="Klinik için geçici erişim token'ı üret",
)
async def impersonate_clinic(
    clinic_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ImpersonateResponse:
    """
    Superadmin global kalır; sadece geçici klinik bağlamı taşıyan token üretir.
    Token kısa ömürlüdür ve impersonation claim'i içerir.
    """
    clinic = await db.get(Clinic, clinic_id)
    if not clinic:
        raise HTTPException(status_code=404, detail="Klinik bulunamadı")
    if not clinic.is_active:
        raise HTTPException(status_code=400, detail="Pasif kliniklere erişilemez")

    token = create_access_token(
        clinic_id=clinic.id,
        user_id=current_user["user_id"],
        role="super_admin",
        expires_minutes=15,
        extra_claims={
            "impersonation": True,
            "impersonated_clinic_id": str(clinic.id),
        },
    )
    return ImpersonateResponse(
        access_token=token,
        clinic_name=clinic.name,
        clinic_slug=clinic.slug,
    )

