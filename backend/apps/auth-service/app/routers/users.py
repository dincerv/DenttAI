"""
Owner Router — /auth/users
Klinik yöneticisinin (owner) kendi kliniğindeki kullanıcıları yönetmesini sağlar.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_permission, require_role
from app.core.security import hash_password
from app.models.user import User, UserRole

router = APIRouter(prefix="/auth/users", tags=["Kullanıcı Yönetimi"])

# ── Page permissions map ───────────────────────────────────────────────────
# Her kullanıcının hangi sayfalara erişebileceği kullanıcının rolüne göre
# otomatik üretilir; owner tüm sayfalara, assistant daha kısıtlı.
ROLE_DEFAULT_PAGES: dict[str, list[str]] = {
    "owner":        ["dashboard", "appointments", "appointments_write", "waitlist", "inventory", "permissions"],
    "doctor":       ["dashboard", "appointments", "appointments_write", "waitlist"],
    "assistant":    ["appointments", "waitlist", "inventory"],
}


# ── Pydantic şemaları ──────────────────────────────────────────────────────

class UserSummary(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    allowed_pages: list[str]
    created_at: str

    model_config = {"from_attributes": True}


class CreateUserRequest(BaseModel):
    email: str = Field(..., pattern=r'^[^@]+@[^@]+$')
    full_name: str = Field(..., min_length=2, max_length=255)
    password: str = Field(..., min_length=6)
    role: UserRole = UserRole.assistant


class UpdateUserRequest(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None
    full_name: str | None = Field(None, min_length=2, max_length=255)


class ChangePasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Şifre en az bir büyük harf içermelidir")
        if not any(c.islower() for c in v):
            raise ValueError("Şifre en az bir küçük harf içermelidir")
        if not any(c.isdigit() for c in v):
            raise ValueError("Şifre en az bir rakam içermelidir")
        return v


# ── Helper ────────────────────────────────────────────────────────────────

async def _set_rls(db: AsyncSession, clinic_id: str) -> None:
    """Set RLS context with parameterized query (SQL injection protection)."""
    await db.execute(text("SELECT set_config('app.current_clinic_id', :cid, true)").bindparams(cid=str(clinic_id)))


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("", response_model=list[UserSummary])
async def list_users(
    current_user: dict = Depends(require_permission("permissions")),
    db: AsyncSession = Depends(get_db),
):
    """Kliniğe ait tüm kullanıcıları listeler (owner hariç süper adminler gösterilmez)."""
    await _set_rls(db, str(current_user["clinic_id"]))
    result = await db.execute(
        select(User)
        .where(User.clinic_id == current_user["clinic_id"])
        .order_by(User.created_at)
    )
    users = result.scalars().all()
    # Non-superadmin users cannot see super_admin accounts
    caller_role = current_user.get("role", "")
    if caller_role != "super_admin":
        users = [u for u in users if u.role != UserRole.super_admin]
    return [
        UserSummary(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            role=u.role.value,
            is_active=u.is_active,
            allowed_pages=u.allowed_pages or ROLE_DEFAULT_PAGES.get(u.role.value, []),
            created_at=u.created_at.isoformat(),
        )
        for u in users
    ]


@router.post("", response_model=UserSummary, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    current_user: dict = Depends(require_permission("permissions")),
    db: AsyncSession = Depends(get_db),
):
    """Kliniğe yeni kullanıcı ekler."""
    await _set_rls(db, str(current_user["clinic_id"]))

    # Aynı email + clinic unique kontrolü
    existing = await db.execute(
        select(User).where(
            User.email == body.email,
            User.clinic_id == current_user["clinic_id"],
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu e-posta adresi kliniğe zaten kayıtlı",
        )

    user = User(
        clinic_id=current_user["clinic_id"],
        email=body.email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        role=body.role,
        is_active=True,
        allowed_pages=ROLE_DEFAULT_PAGES.get(body.role.value, []),
    )
    db.add(user)
    await db.flush()  # get user.id without committing yet

    # Doktor rolü ise doctors tablosuna da ekle (doctor_id JWT'ye dahil edilsin)
    if body.role == UserRole.doctor:
        await db.execute(
            text("""
                INSERT INTO doctors (clinic_id, full_name, user_id)
                VALUES (:clinic_id, :full_name, :user_id)
                ON CONFLICT DO NOTHING
            """),
            {"clinic_id": str(current_user["clinic_id"]),
             "full_name": body.full_name,
             "user_id": str(user.id)},
        )

    await db.commit()
    await db.refresh(user)
    return UserSummary(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        is_active=user.is_active,
        allowed_pages=user.allowed_pages or ROLE_DEFAULT_PAGES.get(user.role.value, []),
        created_at=user.created_at.isoformat(),
    )


@router.patch("/{user_id}", response_model=UserSummary)
async def update_user(
    user_id: uuid.UUID,
    body: UpdateUserRequest,
    current_user: dict = Depends(require_permission("permissions")),
    db: AsyncSession = Depends(get_db),
):
    """Kullanıcının rolünü, aktifliğini veya adını günceller."""
    await _set_rls(db, str(current_user["clinic_id"]))

    user = await db.get(User, user_id)
    if not user or user.clinic_id != current_user["clinic_id"]:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

    # super_admin cannot be modified by non-superadmins
    if user.role == UserRole.super_admin and current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Süper admin hesabını düzenleyemezsiniz")

    # Owner kendi hesabını değiştiremez
    if user.id == current_user["user_id"]:
        raise HTTPException(status_code=400, detail="Kendi hesabınızı bu endpoint ile düzenleyemezsiniz")

    old_role = user.role

    if body.role is not None:
        user.role = body.role
        # Rol değiştiğinde allowed_pages'i yeni rolün default'una sıfırla
        if body.role != old_role:
            user.allowed_pages = ROLE_DEFAULT_PAGES.get(body.role.value, [])
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.full_name is not None:
        user.full_name = body.full_name

    # Rol doctor'a çevrildi → doctors tablosuna ekle (yoksa)
    if body.role == UserRole.doctor and old_role != UserRole.doctor:
        await db.execute(
            text("""
                INSERT INTO doctors (clinic_id, full_name, user_id)
                VALUES (:clinic_id, :full_name, :user_id)
                ON CONFLICT DO NOTHING
            """),
            {"clinic_id": str(user.clinic_id),
             "full_name": user.full_name,
             "user_id": str(user.id)},
        )

    # Rol doctor'dan başka bir role çevrildi → doctors tablosundan sil
    elif old_role == UserRole.doctor and body.role is not None and body.role != UserRole.doctor:
        await db.execute(
            text("DELETE FROM doctors WHERE user_id = :user_id"),
            {"user_id": str(user.id)},
        )

    await db.commit()
    await db.refresh(user)
    return UserSummary(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        is_active=user.is_active,
        allowed_pages=user.allowed_pages or ROLE_DEFAULT_PAGES.get(user.role.value, []),
        created_at=user.created_at.isoformat(),
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    current_user: dict = Depends(require_permission("permissions")),
    db: AsyncSession = Depends(get_db),
):
    """Kullanıcıyı klinikten siler."""
    await _set_rls(db, str(current_user["clinic_id"]))

    user = await db.get(User, user_id)
    if not user or user.clinic_id != current_user["clinic_id"]:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

    if user.id == current_user["user_id"]:
        raise HTTPException(status_code=400, detail="Kendi hesabınızı silemezsiniz")

    # super_admin cannot be deleted by non-superadmins
    if user.role == UserRole.super_admin and current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Süper admin hesabını silemezsiniz")

    # Doktor ise doctors tablosundan da temizle
    if user.role == UserRole.doctor:
        await db.execute(
            text("DELETE FROM doctors WHERE user_id = :uid"),
            {"uid": str(user.id)},
        )

    await db.delete(user)
    await db.commit()


@router.patch("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_user_password(
    user_id: uuid.UUID,
    body: ChangePasswordRequest,
    current_user: dict = Depends(require_permission("permissions")),
    db: AsyncSession = Depends(get_db),
):
    """Klinik kullanıcısının şifresini sıfırlar. Yeni şifre yalnızca hash'i olarak saklanır."""
    await _set_rls(db, str(current_user["clinic_id"]))

    user = await db.get(User, user_id)
    if not user or user.clinic_id != current_user["clinic_id"]:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

    # super_admin password cannot be changed by non-superadmins
    if user.role == UserRole.super_admin and current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Süper admin şifresini değiştiremezsiniz")

    # Şifreyi hemen hash'e çevir; plain-text'i artık tutmuyoruz
    user.hashed_password = hash_password(body.new_password)
    await db.commit()
    # Yanıtta hiçbir şifre verisi dönmez (204 No Content)


# ── Allowed Pages (per-user permissions) ──────────────────

# Geçerli sayfa isimleri — bilinmeyen değer kabul edilmez
VALID_PAGES = {"dashboard", "appointments", "appointments_write", "waitlist", "inventory", "permissions"}


class UpdatePermissionsRequest(BaseModel):
    allowed_pages: list[str]

    @field_validator("allowed_pages")
    @classmethod
    def validate_pages(cls, v: list[str]) -> list[str]:
        invalid = set(v) - VALID_PAGES
        if invalid:
            raise ValueError(f"Geçersiz sayfa(lar): {', '.join(sorted(invalid))}")
        return v


@router.patch("/{user_id}/permissions", response_model=UserSummary)
async def update_user_permissions(
    user_id: uuid.UUID,
    body: UpdatePermissionsRequest,
    current_user: dict = Depends(require_permission("permissions")),
    db: AsyncSession = Depends(get_db),
):
    """Kullanıcının erişebileceği sayfaları günceller. Yalnızca owner yapabilir."""
    await _set_rls(db, str(current_user["clinic_id"]))

    user = await db.get(User, user_id)
    if not user or user.clinic_id != current_user["clinic_id"]:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

    # Owner kendi yetkilerini kısıtlayamaz
    if user.id == current_user["user_id"]:
        raise HTTPException(status_code=400, detail="Kendi yetkilerinizi değiştiremezsiniz")

    user.allowed_pages = body.allowed_pages
    await db.commit()
    await db.refresh(user)
    return UserSummary(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        is_active=user.is_active,
        allowed_pages=user.allowed_pages or [],
        created_at=user.created_at.isoformat(),
    )
