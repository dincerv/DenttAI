"""
FastAPI dependency: JWT'den kimliği doğrula ve current_user döndür.
"""
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Bearer token'ı doğrular ve payload'ı döndürür.
    Returns dict with: sub (user_id), clinic_id, role
    """
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz veya süresi dolmuş token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    clinic_id = payload.get("clinic_id")
    role = payload.get("role")

    if not user_id or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token içeriği eksik",
        )
    # clinic_id yalnızca super_admin dışındaki roller için zorunlu
    if not clinic_id and role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token içeriği eksik",
        )

    return {
        "user_id": UUID(user_id),
        "clinic_id": UUID(clinic_id) if clinic_id else None,
        "role": role,
        "impersonation": bool(payload.get("impersonation", False)),
        "impersonated_clinic_id": (
            UUID(payload["impersonated_clinic_id"])
            if payload.get("impersonated_clinic_id")
            else None
        ),
    }


def require_role(*allowed_roles: str):
    """
    Belirli rollere kısıtlayan dependency factory.

    Kullanım:
        @router.get("/", dependencies=[Depends(require_role("owner"))])
    """
    async def _check(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Bu işlem için yetki gerekiyor: {list(allowed_roles)}",
            )
        return current_user

    return _check


def require_permission(page: str):
    """
    Belirli bir sayfaya (modüle) erişim gerektiren dependency.
    Owner ve super_admin otomatik geçer; diğer roller için
    allowed_pages kontrolü yapılır.
    """
    async def _check(
        current_user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> dict:
        role = current_user["role"]
        # Owner ve super_admin her zaman geçer
        if role in ("owner", "super_admin"):
            return current_user

        from app.models.user import User
        await db.execute(
            text("SELECT set_config('app.current_clinic_id', :cid, true)").bindparams(cid=str(current_user['clinic_id'])),
        )
        result = await db.execute(
            select(User.allowed_pages).where(User.id == current_user["user_id"])
        )
        allowed = result.scalar_one_or_none()
        if not allowed or page not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Bu işlem için '{page}' sayfasına erişim yetkisi gerekiyor",
            )
        return current_user

    return _check
