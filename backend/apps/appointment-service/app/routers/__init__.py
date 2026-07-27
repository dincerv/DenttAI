# routers package
from app.routers.appointments import router as appointments_router
from app.routers.waitlist import router as waitlist_router
from app.routers.patient_notes import router as patient_notes_router

__all__ = ["appointments_router", "waitlist_router", "patient_notes_router"]
