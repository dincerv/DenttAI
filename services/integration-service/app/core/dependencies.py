from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from shared.auth_middleware import get_verified_claims


@dataclass
class CurrentUser:
    id: UUID
    user_id: UUID
    clinic_id: UUID
    role: str
    doctor_id: UUID | None = None


async def get_current_user(claims: dict = Depends(get_verified_claims)) -> CurrentUser:
    """
    Return an object-compatible current user for routers using attribute access
    (e.g. current_user.clinic_id / current_user.id).
    """
    doctor_id = claims.get("doctor_id")
    actor_id = doctor_id or claims["user_id"]
    return CurrentUser(
        id=actor_id,
        user_id=claims["user_id"],
        clinic_id=claims["clinic_id"],
        role=claims["role"],
        doctor_id=doctor_id,
    )


async def get_db_session(db: AsyncSession = Depends(get_db)) -> AsyncSession:
    return db


__all__ = ["CurrentUser", "get_current_user", "get_db"]
