"""
DentAI Flow Monolith — shared.auth_middleware uyumluluk katmanı.

Eski mikroservislerdeki kod:
    from shared.auth_middleware import get_verified_claims, set_rls_context, require_role

Monolith içinde bu modül, app.core.dependencies ve app.core.database'den
re-export yaparak tüm router dosyalarının değiştirilmesini önler.
"""
# get_verified_claims → get_current_user ile aynı imza, aynı dönüş değeri
from app.core.dependencies import get_current_user as get_verified_claims
from app.core.dependencies import require_role, require_permission as require_page_permission
from app.core.database import set_rls_context

# require_not_role — eski mikroservis uyumluluğu için
from fastapi import Depends, HTTPException, status


def require_not_role(*blocked_roles: str):
    """
    Dependency factory — belirtilen rolleri engeller.
    Eski mikroservislerle uyumluluk için.
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


__all__ = [
    "get_verified_claims",
    "set_rls_context",
    "require_role",
    "require_not_role",
    "require_page_permission",
]
