"""
Dr.Dentes PMS Adaptörü — Session Bridge.

Kullanıcının tarayıcısında aktif olan Dr.Dentes oturumunun çerez bilgilerini
kullanarak HTTP istekleri yapar. Cloudflare Turnstile engelini bypass eder
çünkü zaten doğrulanmış bir oturum kullanılır.

Config formatı (clinic_integrations.config):
  {
    "base_url": "https://drdentes.com",
    "session_cookie": "cookie_name=cookie_value; ...",
    "tenant_id": "210130"
  }

Çerez bilgisi, kullanıcının tarayıcısının DevTools > Application > Cookies
kısmından veya frontend arayüzündeki alandan kopyalanarak girilir.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

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

_DEFAULT_BASE = "https://drdentes.com"
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
_ISTANBUL_TZ = ZoneInfo("Europe/Istanbul")
_DEFAULT_LOOKAHEAD_DAYS = 30
_WINDOW_CHUNK_DAYS = 7


class DrDentesAdapter(PMSAdapter):
    provider = "drdentes"

    def __init__(self, config: dict):
        super().__init__(config)
        raw_url = config.get("base_url", _DEFAULT_BASE)
        if "index.php" in raw_url:
            raw_url = raw_url.split("/index.php")[0]
        self.base_url = raw_url.rstrip("/") or _DEFAULT_BASE
        self.session_cookie = config.get("session_cookie", "")
        self.tenant_id = config.get("tenant_id", "")

    def _build_client(self) -> httpx.AsyncClient:
        """Kullanıcının oturum çerezleriyle yapılandırılmış HTTP istemcisi."""
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
        """Oturum çerezinin hâlâ geçerli olup olmadığını kontrol et."""
        if not self.session_cookie:
            logger.warning("Dr.Dentes: session_cookie boş")
            return False
        try:
            async with self._build_client() as client:
                resp = await client.get(f"{self.base_url}/index.php?menu=Randevu")
                # Giriş sayfasına yönlendirildiyse çerez geçersiz
                if "/giris" in str(resp.url) or "frmGiris" in resp.text:
                    logger.warning("Dr.Dentes: oturum çerezi geçersiz — giriş sayfasına yönlendirildi")
                    return False
                # Randevu sayfası yüklendiyse oturum geçerli
                if resp.status_code == 200 and ("Randevu" in resp.text or "randevu" in resp.text.lower()):
                    return True
                return False
        except Exception as exc:
            logger.error("Dr.Dentes bağlantı hatası: %s", exc)
            return False

    async def fetch_patients(self) -> list[PulledPatient]:
        """Randevu verisinden benzersiz hastaları türet."""
        if not self.session_cookie:
            return []
        try:
            events, _doctor_map, _type_map = await self._fetch_appointment_payload()
            seen: set[tuple[str, str]] = set()
            patients: list[PulledPatient] = []
            for item in events:
                name = str(item.get("title") or "").strip()
                if not name or self._is_blocked_slot(name):
                    continue
                phone = str(item.get("cep1") or item.get("telefon") or "").strip() or None
                key = (name.lower(), phone or "")
                if key in seen:
                    continue
                seen.add(key)
                patients.append(PulledPatient(full_name=name, phone=phone))
            logger.info("Dr.Dentes: %d hasta türetildi", len(patients))
            return patients
        except Exception as exc:
            logger.error("Dr.Dentes hasta çekme hatası: %s", exc)
            return []

    async def fetch_appointments(self, since: datetime | None = None) -> list[PulledAppointment]:
        """Randevuları Dr.Dentes takvim AJAX endpoint'inden çek."""
        if not self.session_cookie:
            return []
        try:
            events, doctor_map, type_map = await self._fetch_appointment_payload(since=since)
            appointments: list[PulledAppointment] = []
            for item in events:
                patient_name = str(item.get("title") or "").strip()
                if not patient_name or self._is_blocked_slot(patient_name):
                    continue
                start_raw = str(item.get("start") or "").strip()
                if not start_raw:
                    continue
                try:
                    scheduled_at = datetime.fromisoformat(start_raw).replace(tzinfo=_ISTANBUL_TZ)
                except ValueError:
                    continue
                doctor_id = str(item.get("id_dishekimi") or "").strip()
                doctor_name = doctor_map.get(doctor_id, "Bilinmiyor")
                phone = str(item.get("cep1") or item.get("telefon") or "").strip() or None
                notes = str(item.get("notlar") or "").strip() or None
                appointment_type = type_map.get(str(item.get("aciklama") or "").strip())
                appointments.append(PulledAppointment(
                    patient_name=patient_name,
                    doctor_name=doctor_name,
                    scheduled_at=scheduled_at,
                    patient_phone=phone,
                    appointment_type=appointment_type,
                    notes=notes,
                    external_id=str(item.get("id") or "") or None,
                ))
            logger.info("Dr.Dentes: %d randevu çekildi", len(appointments))
            return appointments
        except Exception as exc:
            logger.error("Dr.Dentes randevu çekme hatası: %s", exc)
            return []

    async def fetch_doctors(self) -> list[PulledDoctor]:
        try:
            _events, doctor_map, _type_map = await self._fetch_appointment_payload()
            return [
                PulledDoctor(full_name=name, external_id=doctor_id)
                for doctor_id, name in doctor_map.items()
                if name
            ]
        except Exception:
            return []

    async def _fetch_appointment_payload(self, since: datetime | None = None) -> tuple[list[dict], dict[str, str], dict[str, str]]:
        async with self._build_client() as client:
            resp = await client.get(f"{self.base_url}/index.php?menu=Randevu")
            if "/giris" in str(resp.url):
                logger.error("Dr.Dentes: oturum süresi dolmuş")
                return [], {}, {}

            doctor_map = self._extract_doctor_map(resp.text)
            type_map = self._extract_type_map(resp.text)
            doctor_ids = list(doctor_map.keys())
            if not doctor_ids:
                doctor_ids = self._extract_selected_doctor_ids(resp.text)

            payload_by_id: dict[str, dict] = {}
            for start_date, end_date in self._build_date_windows(since):
                for doctor_id in doctor_ids:
                    ajax_resp = await client.post(
                        f"{self.base_url}/ajax.php?randevuSayfasi=1",
                        data={
                            "islem": 1,
                            "id_dishekimi": doctor_id,
                            "tarih[baslangic]": start_date,
                            "tarih[bitis]": end_date,
                        },
                    )
                    payload = ajax_resp.json() if ajax_resp.status_code == 200 else []
                    if not isinstance(payload, list):
                        continue
                    for item in payload:
                        event_id = str(item.get("id") or "")
                        if event_id:
                            payload_by_id[event_id] = item
            return list(payload_by_id.values()), doctor_map, type_map

    def _build_date_windows(self, since: datetime | None = None) -> list[tuple[str, str]]:
        start = date.today()
        if since is not None:
            start = max(start, since.date())

        lookahead_days = self.config.get("sync_days_ahead", _DEFAULT_LOOKAHEAD_DAYS)
        try:
            lookahead_days = max(int(lookahead_days), _WINDOW_CHUNK_DAYS)
        except (TypeError, ValueError):
            lookahead_days = _DEFAULT_LOOKAHEAD_DAYS

        end = start + timedelta(days=lookahead_days)
        windows: list[tuple[str, str]] = []
        cursor = start
        while cursor < end:
            window_end = min(cursor + timedelta(days=_WINDOW_CHUNK_DAYS), end)
            windows.append((cursor.isoformat(), window_end.isoformat()))
            cursor = window_end
        return windows

    def _extract_doctor_map(self, html: str) -> dict[str, str]:
        match = re.search(r"hekimBilgiArr\s*=\s*(\{.*?\}),yetkiRandevu", html, re.DOTALL)
        if not match:
            return {}
        try:
            raw = match.group(1)
            data = json.loads(raw)
            result: dict[str, str] = {}
            for doctor_id, info in data.items():
                if isinstance(info, dict):
                    name = str(info.get("adSoyad") or "").strip()
                    if name:
                        result[str(doctor_id)] = name
            return result
        except Exception:
            return {}

    def _extract_selected_doctor_ids(self, html: str) -> list[str]:
        match = re.search(r"hekimArr\s*=\s*\[(.*?)\]", html, re.DOTALL)
        if not match:
            return []
        raw = match.group(1)
        return [part.strip().strip('"\'') for part in raw.split(",") if part.strip()]

    def _extract_type_map(self, html: str) -> dict[str, str]:
        soup = BeautifulSoup(html, "html.parser")
        mapping: dict[str, str] = {}
        for option in soup.select("select#aciklama option"):
            value = str(option.get("value") or "").strip()
            token = option.get_text(strip=True)
            if not value or not token:
                continue
            mapping[value] = self._normalize_type_label(token)
        return mapping

    def _normalize_type_label(self, token: str) -> str:
        token = token.strip()
        custom = {
            "RANDEVUTIP_APAREY": "Aparey",
            "RANDEVUTIP_APSE": "Apse",
            "RANDEVUTIP_CERRAHI_ISLEM": "Cerrahi İşlem",
            "RANDEVUTIP_DETARTRAJ": "Detartraj",
            "RANDEVUTIP_DIGER": "Diğer",
            "RANDEVUTIP_DISCEKIMI": "Çekim",
            "RANDEVUTIP_DOLGU": "Dolgu",
            "RANDEVUTIP_IMPLANT": "İmplant",
            "RANDEVUTIP_KONTROL": "Kontrol",
            "RANDEVUTIP_MUAYENE": "Muayene",
            "RANDEVUTIP_ORTODONTI": "Ortodonti",
            "RANDEVUTIP_PANSUMAN": "Pansuman",
            "RANDEVUTIP_PROTEZ": "Protez",
            "RANDEVUTIP_YENIHASTA": "Yeni Hasta",
        }
        if token in custom:
            return custom[token]
        if token.startswith("RANDEVUTIP_"):
            raw = token.removeprefix("RANDEVUTIP_").replace("_", " ").strip().title()
            return raw
        return token

    def _is_blocked_slot(self, patient_name: str) -> bool:
        normalized = patient_name.strip().lower()
        return normalized.startswith("kapalı") or normalized == "kapali kapali"

    # ── HTML Parse ─────────────────────────────────────────

    def _parse_patients_html(self, html: str) -> list[PulledPatient]:
        soup = BeautifulSoup(html, "html.parser")
        patients: list[PulledPatient] = []

        # Tablo yapısı
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            for row in rows[1:]:
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    name = cells[0].get_text(strip=True)
                    if not name or len(name) < 2:
                        continue
                    phone = None
                    email = None
                    for cell in cells[1:]:
                        text = cell.get_text(strip=True)
                        if re.match(r"^[\d\s\+\-\(\)]{7,15}$", text):
                            phone = text
                        elif "@" in text:
                            email = text
                    patients.append(PulledPatient(full_name=name, phone=phone, email=email))

        # Div/card yapısı
        if not patients:
            for item in soup.select(".hasta-item, .patient-row, [data-hasta], .list-group-item"):
                name_el = item.select_one(".hasta-adi, .patient-name, .ad-soyad, strong, h5, h6")
                if not name_el:
                    continue
                name = name_el.get_text(strip=True)
                if len(name) < 2:
                    continue
                phone_el = item.select_one(".telefon, .phone, [data-tel]")
                phone = phone_el.get_text(strip=True) if phone_el else None
                patients.append(PulledPatient(full_name=name, phone=phone))

        return patients

    def _parse_appointments_html(self, html: str) -> list[PulledAppointment]:
        soup = BeautifulSoup(html, "html.parser")
        appointments: list[PulledAppointment] = []
        today = date.today()

        # Tablo yapısı
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            for row in rows[1:]:
                cells = row.find_all(["td", "th"])
                if len(cells) >= 3:
                    appt = self._try_parse_row(cells, today)
                    if appt:
                        appointments.append(appt)

        # Div/card/event yapısı
        if not appointments:
            for item in soup.select(
                ".randevu-item, .appointment-card, [data-randevu], "
                ".fc-event, .event-item, .list-group-item"
            ):
                appt = self._try_parse_card(item, today)
                if appt:
                    appointments.append(appt)

        return appointments

    def _try_parse_row(self, cells, today: date) -> PulledAppointment | None:
        try:
            texts = [c.get_text(strip=True) for c in cells]
            time_str = None
            patient_name = None
            doctor_name = None

            for text in texts:
                if re.match(r"^\d{2}:\d{2}$", text) and not time_str:
                    time_str = text
                elif re.match(r"^[A-Za-zÇçĞğİıÖöŞşÜü\s\.]{3,}$", text):
                    if not patient_name:
                        patient_name = text
                    elif not doctor_name:
                        doctor_name = text

            if patient_name and time_str:
                h, m = int(time_str[:2]), int(time_str[3:5])
                scheduled = datetime(today.year, today.month, today.day, h, m)
                return PulledAppointment(
                    patient_name=patient_name,
                    doctor_name=doctor_name or "Bilinmiyor",
                    scheduled_at=scheduled,
                )
        except Exception:
            pass
        return None

    def _try_parse_card(self, item, today: date) -> PulledAppointment | None:
        try:
            text = item.get_text(" ", strip=True)
            time_match = re.search(r"(\d{2}):(\d{2})", text)
            if not time_match:
                return None
            h, m = int(time_match.group(1)), int(time_match.group(2))
            name_el = item.select_one("strong, .hasta-adi, .patient-name, h5, h6, b")
            patient_name = name_el.get_text(strip=True) if name_el else "Bilinmiyor"
            scheduled = datetime(today.year, today.month, today.day, h, m)
            return PulledAppointment(
                patient_name=patient_name,
                doctor_name="Bilinmiyor",
                scheduled_at=scheduled,
            )
        except Exception:
            pass
        return None
