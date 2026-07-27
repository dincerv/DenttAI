"""
Integration Service Routers

Main router organization:
- PMS entegrasyon router (_pms.py): DentSoft/harici sistem senkronizasyonu
- WhatsApp entegrasyon router (whatsapp.py): Mesajlaşma, SSS, hasta geri bildirimi
"""
from fastapi import APIRouter

# PMS entegrasyon router (mevcut)
from app.routers._pms import router as pms_router

# WhatsApp entegrasyon router (yeni)
from app.routers.whatsapp import router as whatsapp_router

# Ana router - tüm routers combine
router = APIRouter()
router.include_router(pms_router)
router.include_router(whatsapp_router)

__all__ = ["router"]
