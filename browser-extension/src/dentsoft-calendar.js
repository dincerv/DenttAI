/**
 * Dentsoft takvimi (FullCalendar) → DentAI randevuları.
 *
 * Kaynak uçlar (salt okuma, sayfanın kendi AJAX istekleri):
 *   GET /Calendar/DoctorList/resourceTimeGridDay/0?v=66&start=<ISO>&end=<ISO>       → hekimler (resources)
 *   GET /Calendar/AppointmentList/resourceTimeGridDay/0?v=66&start=<ISO>&end=<ISO>  → randevular (events)
 *
 * Cevap alan adları doğrulanmadığı için normalizasyon toleranslıdır: önce bilinen alan
 * adları, yoksa takvim kutusundaki "Hasta | Tedavi | Not" başlığı kullanılır.
 * describeCalendarShape yalnızca alan adlarını ve tiplerini saklar, değer saklamaz.
 */

export const DOCTOR_LIST_PATH = '/Calendar/DoctorList/resourceTimeGridDay/0';
export const APPOINTMENT_LIST_PATH = '/Calendar/AppointmentList/resourceTimeGridDay/0';
export const DOCTOR_LIST_RE = /\/Calendar\/DoctorList\//i;
export const APPOINTMENT_LIST_RE = /\/Calendar\/AppointmentList\//i;

const TR_OFFSET = '+03:00';

/**
 * Sayfanın MAIN world'ünde (veya service worker'da) çalışır — dış kapsamdan hiçbir şey kullanmamalı.
 * ranges: [{ start, end }] ISO 8601 (saat dilimli).
 */
export async function fetchDentsoftCalendarRanges(baseUrl, ranges, options) {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const delayMs = Number(options?.delayMs) || 250;
  const timeoutMs = Number(options?.timeoutMs) || 15000;
  const loginRe = /\/(login|giris|auth)/i;
  const headers = { Accept: 'application/json, text/javascript, */*; q=0.01', 'X-Requested-With': 'XMLHttpRequest' };

  const get = async (path, start, end) => {
    const url = new URL(path, baseUrl);
    url.searchParams.set('v', String(options?.v || '66'));
    url.searchParams.set('start', start);
    url.searchParams.set('end', end);
    const ctrl = typeof AbortController !== 'undefined' ? new AbortController() : null;
    const timer = ctrl ? setTimeout(() => ctrl.abort(), timeoutMs) : null;
    try {
      const res = await fetch(url.toString(), {
        credentials: 'include',
        headers,
        redirect: 'follow',
        signal: ctrl?.signal,
      });
      if (res.status === 401 || res.status === 403 || loginRe.test(new URL(res.url).pathname)) return { expired: true };
      if (!res.ok) return { error: `HTTP ${res.status}` };
      const text = await res.text();
      if (!text.trim()) return { data: [] };
      try {
        return { data: JSON.parse(text) };
      } catch {
        return /type=["']password["']/i.test(text) ? { expired: true } : { error: 'NOT_JSON' };
      }
    } catch (e) {
      return { error: e?.name === 'AbortError' ? 'TIMEOUT' : String(e?.message || e) };
    } finally {
      if (timer) clearTimeout(timer);
    }
  };

  const chunks = [];
  for (const range of ranges) {
    const doctors = await get(options?.doctorPath, range.start, range.end);
    if (doctors.expired) return { ok: false, reason: 'SESSION_EXPIRED', chunks };
    await sleep(delayMs);
    const events = await get(options?.appointmentPath, range.start, range.end);
    if (events.expired) return { ok: false, reason: 'SESSION_EXPIRED', chunks };
    if (events.error) return { ok: false, reason: 'HTTP_ERROR', message: events.error, chunks };
    chunks.push({ start: range.start, end: range.end, doctors: doctors.data ?? [], events: events.data });
    await sleep(delayMs);
  }
  return { ok: true, chunks };
}

// ── Tarih yardımcıları ────────────────────────────────────────────────────

const pad = (n) => String(n).padStart(2, '0');

/** Yerel takvim günü → "YYYY-MM-DDT00:00:00+03:00". */
export function dayIso(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T00:00:00${TR_OFFSET}`;
}

export function addDays(date, days) {
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  d.setDate(d.getDate() + days);
  return d;
}

/** [from, to) aralığını `stepDays` günlük parçalara böler. */
export function weekRanges(from, to, stepDays = 7) {
  const out = [];
  for (let cur = from; cur < to; cur = addDays(cur, stepDays)) {
    const next = addDays(cur, stepDays);
    out.push({ start: dayIso(cur), end: dayIso(next < to ? next : to) });
  }
  return out;
}

function toIso(value) {
  if (value === null || value === undefined || value === '') return null;
  if (typeof value === 'number') return new Date(value).toISOString();
  const text = String(value).trim();
  const aspNet = text.match(/^\/Date\((-?\d+)/);
  if (aspNet) return new Date(Number(aspNet[1])).toISOString();
  const tr = text.match(/^(\d{2})[./](\d{2})[./](\d{4})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?/);
  if (tr) {
    const [, d, m, y, hh = '00', mm = '00', ss = '00'] = tr;
    return `${y}-${m}-${d}T${hh}:${mm}:${ss}${TR_OFFSET}`;
  }
  const iso = text.replace(' ', 'T');
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?(\.\d+)?$/.test(iso)) return `${iso}${TR_OFFSET}`;
  if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) return `${iso}T00:00:00${TR_OFFSET}`;
  return Number.isNaN(Date.parse(iso)) ? null : iso;
}

// ── Normalizasyon ─────────────────────────────────────────────────────────

function pick(obj, keys) {
  for (const key of keys) {
    const value = obj?.[key];
    if (value !== undefined && value !== null && value !== '') return value;
  }
  return null;
}

function listOf(json) {
  if (Array.isArray(json)) return json;
  if (!json || typeof json !== 'object') return [];
  for (const key of ['data', 'Data', 'events', 'Events', 'resources', 'Resources', 'items', 'Items', 'result', 'Result', 'list', 'List']) {
    if (Array.isArray(json[key])) return json[key];
  }
  return [];
}

function stripHtml(value) {
  return String(value ?? '')
    .replace(/<br\s*\/?>/gi, ' | ')
    .replace(/<[^>]*>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/\s+/g, ' ')
    .trim();
}

function clean(value, max) {
  if (value === null || value === undefined) return null;
  const text = stripHtml(value);
  return text ? text.slice(0, max) : null;
}

function flatten(raw) {
  const ext = raw?.extendedProps && typeof raw.extendedProps === 'object' ? raw.extendedProps : {};
  return { ...ext, ...raw };
}

function doctorName(raw) {
  const name = clean(pick(raw, ['title', 'Title', 'name', 'Name', 'FullName', 'fullName', 'DoctorName', 'UserName', 'NameSurname']), 255);
  if (!name) return null;
  // Başlıktaki "12 / 44" doluluk sayacı isim değildir.
  return name.replace(/\b\d+\s*\/\s*\d+\b/g, '').replace(/\s+/g, ' ').trim() || null;
}

export function normalizeDoctors(json) {
  const out = new Map();
  for (const item of listOf(json)) {
    const raw = flatten(item);
    const id = pick(raw, ['id', 'ID', 'Id', 'resourceId', 'ResourceID', 'UserID', 'DoctorID', 'DoctorId']);
    const name = doctorName(raw);
    if (id === null || !name || name.length < 2) continue;
    out.set(String(id), { external_id: String(id).slice(0, 128), full_name: name });
  }
  return [...out.values()];
}

function mapStatus(text) {
  const v = String(text ?? '').toLocaleLowerCase('tr-TR');
  if (!v) return null;
  if (/gelmedi/.test(v)) return 'no_show';
  if (/(iptal|ertelendi|cancel)/.test(v)) return 'cancelled';
  if (/(klinikten\s*çıkt|klinikten\s*cikt|çıktı|cikti|tamamland|bitti|complete)/.test(v)) return 'completed';
  if (/(hasta\s*geldi|odaya\s*al|geldi|confirm)/.test(v)) return 'confirmed';
  if (/(randevu\s*verildi|yeni\s*hasta|eski\s*hasta|acil|online|recall|bekleniyor|schedul)/.test(v)) return 'scheduled';
  return null;
}

/** Dentsoft lejant etiketini notlara eklemek için (Acil / Online / Recall vb.) */
function statusTags(text) {
  const v = String(text ?? '').toLocaleLowerCase('tr-TR');
  const tags = [];
  if (/acil/.test(v)) tags.push('Acil');
  if (/online/.test(v)) tags.push('Online');
  if (/recall/.test(v)) tags.push('Recall');
  if (/yeni\s*hasta/.test(v)) tags.push('Yeni Hasta');
  if (/eski\s*hasta/.test(v)) tags.push('Eski Hasta');
  return tags;
}

const NON_APPOINTMENT_RE = /(çalışmıyor|calismiyor|izinli|kapalı|kapali)/i;

/**
 * FullCalendar event'i → PmsAppointmentIn. Hasta adı çıkarılamayan veya arka plan/blok
 * kayıtları için null döner.
 */
export function normalizeEvent(item, doctorsById) {
  if (!item || typeof item !== 'object') return null;
  const raw = flatten(item);
  if (raw.display === 'background' || raw.rendering === 'background') return null;

  const titleParts = stripHtml(pick(raw, ['title', 'Title']) ?? '')
    .split('|')
    .map((s) => s.replace(/^[^\p{L}\d(]+/u, '').trim())
    .filter(Boolean);

  const first = pick(raw, ['PatientFirstName', 'PatientName', 'patientName', 'PatientFullName', 'HastaAdi', 'FullName']);
  const last = pick(raw, ['PatientLastName']);
  const patientName = clean([first, last].filter(Boolean).join(' ') || titleParts[0], 255);
  const patientId = pick(raw, ['PatientID', 'PatientId', 'patientId', 'patient_id', 'HastaID']);
  const statusText = pick(raw, ['StatusName', 'statusName', 'AppointmentStatusName', 'Status', 'status', 'AppointmentStatus', 'StatusText', 'className']);

  if (!patientName || patientName.length < 2) return null;
  if (!patientId && NON_APPOINTMENT_RE.test(`${patientName} ${statusText ?? ''}`)) return null;

  const start = toIso(pick(raw, ['start', 'Start', 'StartDate', 'startDate', 'AppointmentDate', 'StartTime']));
  if (!start) return null;
  const end = toIso(pick(raw, ['end', 'End', 'EndDate', 'endDate', 'FinishDate', 'EndTime']));

  const resourceId = pick(raw, ['resourceId', 'ResourceID', 'ResourceId', 'DoctorID', 'DoctorId', 'UserID'])
    ?? (Array.isArray(raw.resourceIds) ? raw.resourceIds[0] : null);
  const doctorId = resourceId !== null ? String(resourceId) : null;
  const doctorLabel = clean(pick(raw, ['DoctorName', 'doctorName', 'UserName', 'Doctor']), 255)
    ?? (doctorId ? doctorsById.get(doctorId)?.full_name ?? null : null);

  const rawId = pick(raw, ['id', 'ID', 'Id', 'AppointmentID', 'AppointmentId', 'appointmentId', 'EventID']);
  const externalId = rawId !== null ? String(rawId) : `${doctorId ?? '-'}|${start}|${patientId ?? patientName}`;

  // Dentsoft kutusu: "Hasta | Tedavi | Not" — title birincil kaynak.
  // AppointmentType çoğu zaman sayısal kod ("1"); bunu tedavi sanma.
  const fieldTreatment = clean(pick(raw, ['TreatmentName', 'Treatment', 'AppointmentTypeName', 'TypeName', 'ProcedureName']), 100);
  const titleTreatment = titleParts[1] ? clean(titleParts[1], 100) : null;
  const treatment = meaningfulText(fieldTreatment) || meaningfulText(titleTreatment);

  const fieldNotes = clean(pick(raw, ['Note', 'Notes', 'Description', 'description', 'AppointmentNote']), 2000);
  const titleNotes = titleParts.length > 2 ? clean(titleParts.slice(2).join(' | '), 2000) : null;
  let baseNotes = meaningfulText(fieldNotes) || meaningfulText(titleNotes);
  // Yanlış parse: "| Protez | 2 ÜYE" → tedavi Protez, not 2 ÜYE
  if (!treatment && baseNotes && /\|/.test(baseNotes)) {
    const scraps = baseNotes.split('|').map((s) => s.trim()).filter(Boolean);
    if (scraps.length) {
      baseNotes = scraps.slice(1).join(' | ') || null;
    }
  }
  const recoveredTreatment = treatment || (() => {
    const scraps = String(fieldNotes || titleNotes || '').split('|').map((s) => s.trim()).filter(Boolean);
    return scraps.find((s) => !/^\d+$/.test(s) && s.length > 1) || null;
  })();
  if (!treatment && recoveredTreatment && baseNotes) {
    const scraps = baseNotes.split('|').map((s) => s.trim()).filter(Boolean);
    baseNotes = scraps.filter((s) => s !== recoveredTreatment).join(' | ') || null;
  }

  const statusLabel = statusText !== null ? stripHtml(statusText) : '';
  const tags = statusTags(`${statusLabel} ${titleParts.join(' ')}`);
  const tagPrefix = tags.length ? `[${tags.join(', ')}]` : '';
  const notes = clean([tagPrefix, baseNotes].filter(Boolean).join(' ').trim(), 2000);
  const isNew =
    raw.IsNewPatient === true
    || raw.isNewPatient === true
    || /yeni\s*hasta/i.test(statusLabel)
    || tags.includes('Yeni Hasta')
    || (raw.IsNewPatient === false || tags.includes('Eski Hasta') ? false : null);

  return {
    external_id: externalId.slice(0, 128),
    start,
    end,
    doctor_external_id: doctorId ? doctorId.slice(0, 128) : null,
    doctor_name: doctorLabel,
    patient_external_id: patientId !== null ? String(patientId).slice(0, 128) : null,
    patient_name: patientName,
    patient_phone: clean(pick(raw, ['ContactMobile', 'PatientPhone', 'Phone', 'phone', 'Gsm', 'Mobile', 'ContactPhone', 'CepTelefon']), 20),
    treatment: clean(recoveredTreatment || treatment, 100),
    notes,
    status: mapStatus(statusLabel) ?? 'scheduled',
    is_new_patient: isNew === null ? false : isNew,
  };
}

/** Sayısal kod / boş / anlamsız değerleri ele. */
function meaningfulText(value) {
  if (!value) return null;
  const t = String(value).trim().replace(/^\|+\s*/, '').replace(/\s*\|+$/, '').trim();
  if (!t || /^\d+$/.test(t)) return null;
  return t;
}

/**
 * Patient/Index kartından profil alanlarını okur — MAIN world, self-contained.
 * patientIds: Dentsoft hasta kimlikleri (URL path segmenti).
 */
export async function fetchDentsoftPatientCards(baseUrl, patientIds, options) {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const delayMs = Number(options?.delayMs) || 180;
  const max = Math.min(patientIds.length, Number(options?.max) || 40);
  const loginRe = /\/(login|giris|auth)/i;

  const parseCard = (html) => {
    const field = (name) => {
      const esc = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      let m = html.match(new RegExp(`name=["']${esc}["'][^>]*value=["']([^"']*)["']`, 'i'));
      if (m?.[1]?.trim()) return m[1].trim();
      m = html.match(new RegExp(`value=["']([^"']*)["'][^>]*name=["']${esc}["']`, 'i'));
      return m?.[1]?.trim() || null;
    };
    const selectVal = (name) => {
      const esc = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const block = html.match(new RegExp(`<select[^>]*name=["']${esc}["'][^>]*>([\\s\\S]*?)<\\/select>`, 'i'));
      if (!block) return null;
      let m = block[1].match(/<option[^>]*selected[^>]*value=["']([^"']*)["']/i);
      if (m?.[1]?.trim()) return m[1].trim();
      m = block[1].match(/<option[^>]*value=["']([^"']*)["'][^>]*selected/i);
      return m?.[1]?.trim() || null;
    };
    const first = (...vals) => vals.find((v) => v !== null && v !== undefined && String(v).trim() !== '') ?? null;
    return {
      firstName: field('PatientFirstName'),
      lastName: field('PatientLastName'),
      nationalId: field('PatientNumber'),
      phone: first(field('ContactMobile'), field('ContactPhone')),
      email: first(field('ContactEmail'), field('Email')),
      birthDate: first(field('PatientBirthDate'), field('BirthDate')),
      sex: first(field('PatientSex'), selectVal('PatientSex')),
      address: first(field('Address'), field('Adres')),
      city: first(field('City'), field('Il'), selectVal('City')),
      district: first(field('District'), field('Ilce'), selectVal('District')),
      country: first(field('Country'), field('Ulke')),
      occupation: first(field('PatientJob'), field('Job')),
      nationality: first(field('PatientNationality'), field('Uyruk')),
      bloodType: first(field('BloodGroup'), selectVal('BloodGroup')),
      fileNumber: first(field('FileNo'), field('PatientFileNo')),
      archiveNumber: first(field('ArchiveID'), field('ArchiveNo')),
      insuranceType: first(field('InsuranceType'), selectVal('InsuranceType')),
      insuranceProvider: first(field('CompanyName'), field('InsuranceProvider')),
    };
  };

  const mapSex = (raw) => {
    const v = String(raw ?? '').trim().toLowerCase();
    if (['1', 'f', 'female', 'kadin', 'kadın', 'k'].includes(v)) return 'female';
    if (['0', '2', 'm', 'male', 'erkek', 'e'].includes(v)) return 'male';
    return v ? 'unknown' : null;
  };
  const mapInsurance = (raw) => {
    const v = String(raw ?? '').trim().toLowerCase();
    if (/(sgk|bagkur|ba[gğ]kur|emekli)/i.test(v)) return 'sgk';
    if (/(ozel|özel|private)/i.test(v)) return 'private';
    if (/(karma|mixed)/i.test(v)) return 'mixed';
    if (/(yok|none)/i.test(v)) return 'none';
    return null;
  };

  const patients = [];
  const seen = new Set();
  for (const id of patientIds) {
    if (patients.length >= max) break;
    const key = String(id);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    try {
      const url = new URL(`/Patient/Index/${encodeURIComponent(key)}`, baseUrl).toString();
      const res = await fetch(url, { credentials: 'include', redirect: 'follow' });
      if (res.status === 401 || res.status === 403 || loginRe.test(new URL(res.url).pathname)) {
        return { ok: false, reason: 'SESSION_EXPIRED', patients };
      }
      if (!res.ok) continue;
      const html = await res.text();
      if (/type=["']password["']/i.test(html) && /frmGiris|login/i.test(html)) {
        return { ok: false, reason: 'SESSION_EXPIRED', patients };
      }
      const card = parseCard(html);
      const fullName = [card.firstName, card.lastName].filter(Boolean).join(' ').trim();
      if (!fullName || fullName.length < 2) continue;
      patients.push({
        full_name: fullName.slice(0, 255),
        phone: card.phone ? String(card.phone).slice(0, 20) : null,
        email: card.email ? String(card.email).slice(0, 255) : null,
        national_id: (() => {
          const tc = card.nationalId ? String(card.nationalId).replace(/\D/g, '') : '';
          return tc.length === 11 ? tc : null;
        })(),
        birth_date: card.birthDate ? String(card.birthDate).slice(0, 16) : null,
        sex: mapSex(card.sex),
        address: card.address ? String(card.address).slice(0, 500) : null,
        city: card.city ? String(card.city).slice(0, 100) : null,
        district: card.district ? String(card.district).slice(0, 100) : null,
        country: card.country ? String(card.country).slice(0, 100) : null,
        occupation: card.occupation ? String(card.occupation).slice(0, 100) : null,
        nationality: card.nationality ? String(card.nationality).slice(0, 100) : null,
        blood_type: card.bloodType ? String(card.bloodType).slice(0, 20) : null,
        file_number: card.fileNumber ? String(card.fileNumber).slice(0, 64) : null,
        archive_number: card.archiveNumber ? String(card.archiveNumber).slice(0, 64) : null,
        insurance_type: mapInsurance(card.insuranceType),
        insurance_provider: card.insuranceProvider ? String(card.insuranceProvider).slice(0, 100) : null,
        external_id: key.slice(0, 128),
      });
    } catch {
      /* tek hasta hatası */
    }
    await sleep(delayMs);
  }
  return { ok: true, patients };
}

export function normalizeCalendar(doctorsJson, eventsJson) {
  const doctors = normalizeDoctors(doctorsJson);
  const byId = new Map(doctors.map((d) => [d.external_id, d]));
  const appointments = listOf(eventsJson)
    .map((ev) => {
      try {
        return normalizeEvent(ev, byId);
      } catch {
        return null;
      }
    })
    .filter(Boolean);
  return { doctors, appointments };
}

// ── Teşhis (PII yok) ──────────────────────────────────────────────────────

function keyTypes(obj) {
  const out = {};
  for (const [k, v] of Object.entries(obj ?? {})) {
    out[k] = Array.isArray(v) ? 'array' : v === null ? 'null' : typeof v;
  }
  return out;
}

/** Alan adları + tipler; durum/renk gibi kategorik alanlardan en fazla 20 farklı değer. */
export function describeCalendarShape(doctorsJson, eventsJson, previous = {}) {
  const doctors = listOf(doctorsJson);
  const events = listOf(eventsJson);
  const firstEvent = events[0] ?? null;
  const statusValues = new Set(previous.statusValues ?? []);
  for (const ev of events) {
    const raw = flatten(ev);
    for (const key of ['StatusName', 'Status', 'status', 'AppointmentStatus', 'className', 'backgroundColor', 'color']) {
      if (raw[key] !== undefined && raw[key] !== null && statusValues.size < 20) {
        statusValues.add(`${key}=${stripHtml(Array.isArray(raw[key]) ? raw[key].join(' ') : raw[key]).slice(0, 60)}`);
      }
    }
  }
  return {
    at: new Date().toISOString(),
    doctorsTopLevel: Array.isArray(doctorsJson) ? 'array' : Object.keys(doctorsJson ?? {}),
    eventsTopLevel: Array.isArray(eventsJson) ? 'array' : Object.keys(eventsJson ?? {}),
    doctorFields: doctors[0] ? keyTypes(doctors[0]) : previous.doctorFields ?? null,
    eventFields: firstEvent ? keyTypes(firstEvent) : previous.eventFields ?? null,
    eventExtendedFields: firstEvent?.extendedProps ? keyTypes(firstEvent.extendedProps) : previous.eventExtendedFields ?? null,
    titleSegments: firstEvent ? stripHtml(pick(flatten(firstEvent), ['title', 'Title']) ?? '').split('|').length : previous.titleSegments ?? null,
    statusValues: [...statusValues],
  };
}
