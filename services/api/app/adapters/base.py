"""
Abstract PMS adapter — tüm harici klinik yazılımları bu sınıfı implemente eder.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PulledPatient:
    full_name: str
    phone: str | None = None
    email: str | None = None
    external_id: str | None = None


@dataclass
class PulledAppointment:
    patient_name: str
    doctor_name: str
    scheduled_at: datetime
    patient_phone: str | None = None
    specialty: str | None = None
    appointment_type: str | None = None
    notes: str | None = None
    external_id: str | None = None


@dataclass
class PulledDoctor:
    full_name: str
    specialty: str | None = None
    external_id: str | None = None


@dataclass
class SyncResult:
    provider: str
    patients_pulled: int = 0
    patients_inserted: int = 0
    appointments_pulled: int = 0
    appointments_inserted: int = 0
    doctors_pulled: int = 0
    errors: list[str] = field(default_factory=list)
    synced_at: datetime | None = None


class PMSAdapter(abc.ABC):
    """
    Harici klinik yazılım adaptörü. Her PMS sağlayıcısı bu sınıfı
    implemente eder.

    config: clinic_integrations tablosundaki JSON config alanı (credentials, base_url, vb.)
    """

    provider: str = "unknown"

    def __init__(self, config: dict):
        self.config = config

    @abc.abstractmethod
    async def test_connection(self) -> bool:
        """Bağlantıyı test et. Başarılıysa True döner."""
        ...

    @abc.abstractmethod
    async def fetch_patients(self) -> list[PulledPatient]:
        """Harici sistemden hastaları çek."""
        ...

    @abc.abstractmethod
    async def fetch_appointments(self, since: datetime | None = None) -> list[PulledAppointment]:
        """Harici sistemden randevuları çek. since verilirse sadece o tarihten sonrakileri al."""
        ...

    @abc.abstractmethod
    async def fetch_doctors(self) -> list[PulledDoctor]:
        """Harici sistemden doktor listesini çek."""
        ...
