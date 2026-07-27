from app.routers.auth import router as auth_router
from app.routers.tenants import router as tenants_router
from app.routers.admin import router as admin_router
from app.routers.users import router as users_router

__all__ = ["auth_router", "tenants_router", "admin_router", "users_router"]
