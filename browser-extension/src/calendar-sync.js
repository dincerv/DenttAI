/**
 * PMS takvim senkronu — Dentsoft randevuları → DentAI /api/integration/import/appointments.
 *
 * Her periyodik çalışmada:
 *   1) İleri pencere: [bugün-7g, bugün+13h) haftalık parçalar — değişiklikler (saat, iptal, durum) yansır.
 *   2) Geçmiş tarama: imleçten geriye BACKFILL_WEEKS_PER_RUN hafta; BACKFILL_STOP_EMPTY_WEEKS hafta
 *      üst üste boş gelirse biter. İmleç yalnızca gönderim başarılıysa ilerler.
 *
 * calendarSent:<provider> = { [external_id]: hash } — değişmeyen randevu tekrar gönderilmez.
 * calendarShape:<provider> = alan adları/tipleri (PII yok) — eşleme doğrulaması için popup'tan kopyalanır.
 */

import { AuthError, ValidationError, importAppointments } from './dentai-client.js';
import {
  APPOINTMENT_LIST_PATH,
  APPOINTMENT_LIST_RE,
  DOCTOR_LIST_PATH,
  DOCTOR_LIST_RE,
  addDays,
  describeCalendarShape,
  fetchDentsoftCalendarRanges,
  normalizeDoctors,
  normalizeEvent,
  weekRanges,
} from './dentsoft-calendar.js';

const FORWARD_PAST_DAYS = 7;
const FORWARD_FUTURE_DAYS = 91;
const BACKFILL_WEEKS_PER_RUN = 12;
const BACKFILL_STOP_EMPTY_WEEKS = 104;
const BACKFILL_FLOOR = new Date(2000, 0, 1);
const SEND_BATCH = 300;
const MAX_SENT_ENTRIES = 60000;
/** Tek haftalık Dentsoft çekimi için üst süre (ms). Aşılırsa sonraki haftaya geçilir. */
const WEEK_FETCH_TIMEOUT_MS = 20000;

const stateKey = (id) => `calendar:${id}`;
const sentKey = (id) => `calendarSent:${id}`;
const shapeKey = (id) => `calendarShape:${id}`;
const doctorsKey = (id) => `calendarDoctors:${id}`;

const locks = new Map();
function withLock(key, fn) {
  const previous = locks.get(key) ?? Promise.resolve();
  const next = previous.catch(() => {}).then(fn);
  locks.set(key, next.catch(() => {}));
  return next;
}

async function hashOf(value) {
  const bytes = new TextEncoder().encode(JSON.stringify(value));
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(digest)].slice(0, 8).map((b) => b.toString(16).padStart(2, '0')).join('');
}

function today() {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

// ── Hekim önbelleği + şekil teşhisi ───────────────────────────────────────

async function mergeDoctors(providerId, doctors) {
  const { [doctorsKey(providerId)]: cached = [] } = await chrome.storage.local.get(doctorsKey(providerId));
  const byId = new Map(cached.map((d) => [d.external_id, d]));
  for (const d of doctors) byId.set(d.external_id, d);
  const merged = [...byId.values()];
  await chrome.storage.local.set({ [doctorsKey(providerId)]: merged });
  return new Map(merged.map((d) => [d.external_id, d]));
}

async function recordShape(providerId, doctorsJson, eventsJson) {
  const { [shapeKey(providerId)]: previous = {} } = await chrome.storage.local.get(shapeKey(providerId));
  await chrome.storage.local.set({ [shapeKey(providerId)]: describeCalendarShape(doctorsJson, eventsJson, previous) });
}

export async function getCalendarShape(providerId) {
  const { [shapeKey(providerId)]: shape = null } = await chrome.storage.local.get(shapeKey(providerId));
  return shape;
}

export async function resetCalendar(providerId) {
  await chrome.storage.local.remove([stateKey(providerId), sentKey(providerId), shapeKey(providerId), doctorsKey(providerId)]);
}

// ── Gönderim ──────────────────────────────────────────────────────────────

const emptyTotals = () => ({ inserted: 0, updated: 0, unchanged: 0, skipped_invalid: 0, patients_created: 0, doctors_created: 0 });

function addTotals(into, result) {
  for (const key of Object.keys(into)) into[key] += Number(result?.[key] || 0);
  return into;
}

async function sendBatch(providerId, doctors, batch) {
  try {
    return await importAppointments({ source: providerId, doctors, appointments: batch });
  } catch (error) {
    if (!(error instanceof ValidationError)) throw error;
    if (batch.length === 1) return { ...emptyTotals(), skipped_invalid: 1 };
    const mid = Math.ceil(batch.length / 2);
    const left = await sendBatch(providerId, doctors, batch.slice(0, mid));
    const right = await sendBatch(providerId, doctors, batch.slice(mid));
    return addTotals(addTotals(emptyTotals(), left), right);
  }
}

/** Yalnızca yeni/değişmiş randevuları gönderir; başarılı partilerin hash'lerini kaydeder. */
async function sendChanged(providerId, doctors, appointments) {
  const { [sentKey(providerId)]: sent = {} } = await chrome.storage.local.get(sentKey(providerId));
  const changed = [];
  for (const appt of appointments) {
    const h = await hashOf(appt);
    if (sent[appt.external_id] !== h) changed.push({ appt, h });
  }

  const totals = emptyTotals();
  for (let i = 0; i < changed.length; i += SEND_BATCH) {
    const slice = changed.slice(i, i + SEND_BATCH);
    addTotals(totals, await sendBatch(providerId, doctors, slice.map((x) => x.appt)));
    for (const { appt, h } of slice) {
      delete sent[appt.external_id];
      sent[appt.external_id] = h;
    }
    const keys = Object.keys(sent);
    if (keys.length > MAX_SENT_ENTRIES) {
      for (const k of keys.slice(0, keys.length - MAX_SENT_ENTRIES)) delete sent[k];
    }
    await chrome.storage.local.set({ [sentKey(providerId)]: sent });
  }
  return { ...totals, sent: changed.length };
}

// ── Parça işleme ──────────────────────────────────────────────────────────

async function processChunks(providerId, chunks) {
  let doctorsById = await mergeDoctors(providerId, []);
  const appointments = [];
  const perChunkCounts = [];
  let shapeRecorded = false;

  for (const chunk of chunks) {
    const fresh = normalizeDoctors(chunk.doctors);
    if (fresh.length) doctorsById = await mergeDoctors(providerId, fresh);
    const list = Array.isArray(chunk.events) ? chunk.events : chunk.events?.data ?? chunk.events?.events ?? [];
    if (!shapeRecorded && list.length) {
      await recordShape(providerId, chunk.doctors, chunk.events);
      shapeRecorded = true;
    }
    let count = 0;
    for (const ev of list) {
      try {
        const appt = normalizeEvent(ev, doctorsById);
        if (appt) {
          appointments.push(appt);
          count += 1;
        }
      } catch {
        /* tek kayıt hatası tüm parçayı düşürmesin */
      }
    }
    perChunkCounts.push(count);
  }
  return { doctors: [...doctorsById.values()], appointments, perChunkCounts };
}

// ── Periyodik çalışma ─────────────────────────────────────────────────────

function fetchOptions() {
  return { doctorPath: DOCTOR_LIST_PATH, appointmentPath: APPOINTMENT_LIST_PATH, delayMs: 200, v: '66', timeoutMs: 15000 };
}

function withTimeout(promise, ms, reason = 'TIMEOUT') {
  let timer;
  const timeout = new Promise((resolve) => {
    timer = setTimeout(() => resolve({ ok: false, reason }), ms);
  });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}

/**
 * Tek hafta çeker. Tüm aralığı tek executeScript'te göndermek Chrome'da NO_RESULT / takılma üretiyordu.
 */
async function fetchWeek(execute, baseUrl, range) {
  const raw = await withTimeout(
    execute(fetchDentsoftCalendarRanges, [baseUrl, [range], fetchOptions()]),
    WEEK_FETCH_TIMEOUT_MS,
  );
  if (!raw || raw.reason === 'NO_RESULT') return { ok: false, reason: 'NO_RESULT' };
  return raw;
}

async function pullAndSendWeeks(providerId, execute, baseUrl, ranges, updateStatus, statusPatch) {
  const totals = emptyTotals();
  let seen = 0;
  let lastError = null;
  let sessionExpired = false;
  const perChunkCounts = [];

  for (let i = 0; i < ranges.length; i++) {
    const week = await fetchWeek(execute, baseUrl, ranges[i]);
    if (!week?.ok) {
      if (week?.reason === 'SESSION_EXPIRED') {
        sessionExpired = true;
        lastError = 'Dentsoft oturumu kapalı';
        break;
      }
      lastError = `${week?.reason ?? 'HATA'}${week?.message ? `: ${week.message}` : ''}`;
      // Tek hafta başarısız olsa bile diğer haftalara devam et (NO_RESULT / TIMEOUT).
      perChunkCounts.push(0);
      continue;
    }
    const processed = await processChunks(providerId, week.chunks || []);
    seen += processed.appointments.length;
    perChunkCounts.push(...processed.perChunkCounts);
    if (processed.appointments.length || processed.doctors.length) {
      addTotals(totals, await sendChanged(providerId, processed.doctors, processed.appointments));
    }
    if (i % 3 === 2 || i === ranges.length - 1) {
      await updateStatus(providerId, {
        calendar: { ...statusPatch, progress: `${i + 1}/${ranges.length}`, forwardSeen: seen, lastResult: { ...totals, sent: totals.inserted + totals.updated } },
      });
    }
  }
  return { totals, seen, lastError, sessionExpired, perChunkCounts };
}

/**
 * execute(func, args) — background'ın sağladığı çalıştırıcı (açık sekmede MAIN world veya service worker).
 */
export function runCalendarSync(provider, target, execute, updateStatus) {
  return withLock(`calendar:${provider.id}`, async () => {
    const providerId = provider.id;
    const { [stateKey(providerId)]: state = {} } = await chrome.storage.local.get(stateKey(providerId));
    const base = today();
    const status = { lastRunAt: new Date().toISOString(), lastError: null };

    try {
      // 1) İleri pencere — hafta hafta
      const forward = weekRanges(addDays(base, -FORWARD_PAST_DAYS), addDays(base, FORWARD_FUTURE_DAYS));
      const fwd = await pullAndSendWeeks(providerId, execute, target.baseUrl, forward, updateStatus, { ...state, ...status, phase: 'forward' });
      status.forwardSeen = fwd.seen;
      status.lastResult = { ...fwd.totals, sent: fwd.totals.inserted + fwd.totals.updated };
      if (fwd.sessionExpired) {
        status.lastError = fwd.lastError;
        await updateStatus(providerId, { calendar: { ...state, ...status } });
        return;
      }
      if (fwd.lastError && !fwd.seen) {
        status.lastError = fwd.lastError;
      }

      // 2) Geçmiş tarama — hafta hafta
      let { backfillCursor, backfillEmptyWeeks = 0, backfillDone = false } = state;
      if (!backfillDone) {
        const cursor = backfillCursor ? new Date(backfillCursor) : addDays(base, -FORWARD_PAST_DAYS);
        const from = addDays(cursor, -7 * BACKFILL_WEEKS_PER_RUN);
        const back = await pullAndSendWeeks(providerId, execute, target.baseUrl, weekRanges(from, cursor), updateStatus, {
          ...state, ...status, phase: 'backfill', backfillCursor, backfillEmptyWeeks, backfillDone,
        });
        status.backfillLastResult = { ...back.totals, sent: back.totals.inserted + back.totals.updated };
        if (back.sessionExpired) {
          status.lastError = back.lastError;
        } else if (back.seen > 0 || !back.lastError) {
          for (const count of [...back.perChunkCounts].reverse()) {
            backfillEmptyWeeks = count ? 0 : backfillEmptyWeeks + 1;
          }
          backfillCursor = from.toISOString();
          backfillDone = backfillEmptyWeeks >= BACKFILL_STOP_EMPTY_WEEKS || from <= BACKFILL_FLOOR;
        } else if (!status.lastError) {
          status.lastError = `Geçmiş tarama: ${back.lastError}`;
        }
      }
      await updateStatus(providerId, {
        calendar: { ...state, ...status, backfillCursor, backfillEmptyWeeks, backfillDone, phase: null, progress: null },
      });
      await chrome.storage.local.set({ [stateKey(providerId)]: { backfillCursor, backfillEmptyWeeks, backfillDone } });
    } catch (error) {
      status.lastError = error instanceof AuthError ? `AUTH: ${error.message}` : String(error?.message || error);
      await updateStatus(providerId, { calendar: { ...state, ...status } });
    }
  });
}

// ── Gerçek zamanlı: kullanıcı Dentsoft takvimini gezerken yakalanan cevaplar ──

export function isCalendarUrl(url) {
  return DOCTOR_LIST_RE.test(url) || APPOINTMENT_LIST_RE.test(url);
}

export function ingestCalendarIntercept(providerId, url, payload, updateStatus) {
  return withLock(`calendar:${providerId}`, async () => {
    if (DOCTOR_LIST_RE.test(url)) {
      await mergeDoctors(providerId, normalizeDoctors(payload));
      return { ok: true, doctors: true };
    }
    const processed = await processChunks(providerId, [{ doctors: [], events: payload }]);
    if (!processed.appointments.length) return { ok: true, sent: 0 };
    try {
      const result = await sendChanged(providerId, processed.doctors, processed.appointments);
      await updateStatus(providerId, { calendarLive: { at: new Date().toISOString(), ...result } });
      return { ok: true, ...result };
    } catch (error) {
      await updateStatus(providerId, { calendarLive: { at: new Date().toISOString(), error: String(error?.message || error) } });
      return { ok: false };
    }
  });
}
