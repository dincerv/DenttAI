"""
DentSoft PMS Adaptörü — Session Bridge.

Kullanıcının tarayıcısında aktif olan DentSoft oturumunun çerez bilgilerini
kullanarak HTTP istekleri yapar.

Config formatı (clinic_integrations.config):
  {
    "base_url": "https://dentsoft.example.com",
    "session_cookie": "cookie_name=cookie_value; ...",
  }
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, date

import certifi
import httpx
from bs4 import BeautifulSoup

from app.adapters.base import (
    PMSAdapter,
    PulledAppointment,
    PulledDoctor,
    PulledPatient,
)

logger = logging.getLogger(__name__)

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"


class DentSoftAdapter(PMSAdapter):
    provider = "dentsoft"

    def __init__(self, config: dict):
        super().__init__(config)
        self.base_url = (config.get("base_url", "")).rstrip("/")
        self.session_cookie = config.get("session_cookie", "")

    def _build_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            verify=certifi.where(),  # ⚠️ Enable SSL verification to prevent MITM attacks
            headers={
                "User-Agent": _UA,
                "Cookie": self.session_cookie,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
            },
        )

    async def test_connection(self) -> bool:
        if not self.base_url or not self.session_cookie:
            logger.warning("DentSoft: base_url veya session_cookie boş")
            return False
        try:
            async with self._build_client() as client:
                resp = await client.get(self.base_url)
                # Login sayfasına yönlendirilme kontrolü
                if resp.status_code == 200 and ("login" not in str(resp.url).lower()):
                    return True
                return False
        except Exception as exc:
            logger.error("DentSoft bağlantı hatası: %s", exc)
            return False

    async def fetch_patients(self) -> list[PulledPatient]:
        if not self.base_url or not self.session_cookie:
            return []
        try:
            async with self._build_client() as client:
                resp = await client.get(f"{self.base_url}/patients")
                if resp.status_code != 200:
                    return []
                # JSON yanıt ise
                try:
                    data = resp.json()
                    items = data if isinstance(data, list) else data.get("patients", data.get("data", []))
                    return [
                        PulledPatient(
                            full_name=p.get("ad_soyad", p.get("full_name", p.get("name", ""))),
                            phone=p.get("telefon", p.get("phone")),
                            email=p.get("email"),
                            external_id=str(p.get("id", "")),
                        )
                        for p in items
                        if p.get("ad_soyad") or p.get("full_name") or p.get("name")
                    ]
                except Exception:
                    pass
                # HTML yanıt ise — tablo parse
                return self._parse_patients_html(resp.text)
        except Exception as exc:
            logger.error("DentSoft hasta çekme hatası: %s", exc)
            return []

    async def fetch_appointments(self, since: datetime | None = None) -> list[PulledAppointment]:
        if not self.base_url or not self.session_cookie:
            return []
        try:
            async with self._build_client() as client:
                resp = await client.get(f"{self.base_url}/appointments")
                if resp.status_code != 200:
                    return []
                try:
                    data = resp.json()
                    items = data if isinstance(data, list) else data.get("appointments", data.get("data", []))
                    return [
                        PulledAppointment(
                            patient_name=a.get("hasta_adi", a.get("patient_name", "")),
                            doctor_name=a.get("doktor_adi", a.get("doctor_name", "")),
                            scheduled_at=datetime.fromisoformat(
                                a.get("tarih", a.get("scheduled_at", a.get("date", "")))
                            ),
                            patient_phone=a.get("telefon", a.get("patient_phone")),
                            notes=a.get("notlar", a.get("notes")),
                            external_id=str(a.get("id", "")),
                        )
                        for a in items
                    ]
                except Exception:
                    pass
                return self._parse_appointments_html(resp.text)
        except Exception as exc:
            logger.error("DentSoft randevu çekme hatası: %s", exc)
            return []

    async def fetch_doctors(self) -> list[PulledDoctor]:
        return []

    # ── HTML Parse ─────────────────────────────────────────

    def _parse_patients_html(self, html: str) -> list[PulledPatient]:
        soup = BeautifulSoup(html, "html.parser")
        patients: list[PulledPatient] = []
        for table in soup.find_all("table"):
            for row in table.find_all("tr")[1:]:
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    name = cells[0].get_text(strip=True)
                    if not name or len(name) < 2:
                        continue
                    phone = None
                    for cell in cells[1:]:
                        text = cell.get_text(strip=True)
                        if re.match(r"^[\d\s\+\-\(\)]{7,15}$", text):
                            phone = text
                            break
                    patients.append(PulledPatient(full_name=name, phone=phone))
        return patients

    def _parse_appointments_html(self, html: str) -> list[PulledAppointment]:
        soup = BeautifulSoup(html, "html.parser")
        appointments: list[PulledAppointment] = []
        today = date.today()
        for table in soup.find_all("table"):
            for row in table.find_all("tr")[1:]:
                cells = row.find_all(["td", "th"])
                if len(cells) >= 3:
                    texts = [c.get_text(strip=True) for c in cells]
                    time_str = next((t for t in texts if re.match(r"^\d{2}:\d{2}$", t)), None)
                    names = [t for t in texts if re.match(r"^[A-Za-zÇçĞğİıÖöŞşÜü\s\.]{3,}$", t)]
                    if time_str and names:
                        h, m = int(time_str[:2]), int(time_str[3:5])
                        appointments.append(PulledAppointment(
                            patient_name=names[0],
                            doctor_name=names[1] if len(names) > 1 else "Bilinmiyor",
                            scheduled_at=datetime(today.year, today.month, today.day, h, m),
                        ))
        return appointments
