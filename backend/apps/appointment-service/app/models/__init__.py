# models package
from app.models.appointment import Appointment, AppointmentStatus
from app.models.waitlist import Waitlist

__all__ = ["Appointment", "AppointmentStatus", "Waitlist"]
