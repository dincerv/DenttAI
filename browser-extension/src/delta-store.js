/**
 * Delta (watermark) + kalıcı gönderim kuyruğu — chrome.storage.local.
 *
 * delta:<provider>  = { lastId, lastCreatedAt, seen: string[] }
 * queue:<provider>  = [{ h, p }]   h: kayıt hash'i, p: ExternalPatient
 * dead:<provider>   = [{ at, error, count }]
 *
 * Watermark, kayıtlar kuyruğa yazıldığı anda aynı storage.set çağrısıyla ilerletilir;
 * kuyruk kalıcı olduğu için backend'e ulaşılamasa bile veri kaybolmaz.
 * `seen` setinde PII değil, SHA-256 hash önekleri tutulur.
 */

const MAX_SEEN = 5000;
const MAX_QUEUE = 20000;
const MAX_DEAD = 50;

const deltaKey = (providerId) => `delta:${providerId}`;
const queueKey = (providerId) => `queue:${providerId}`;
const deadKey = (providerId) => `dead:${providerId}`;

async function sha256(text) {
  const bytes = new TextEncoder().encode(text);
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(digest)]
    .slice(0, 12)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

function identityOf(providerId, record) {
  const p = record.patient;
  if (record.externalId) return `${providerId}|id|${record.externalId}`;
  if (p.national_id) return `${providerId}|tc|${p.national_id}`;
  return `${providerId}|np|${p.full_name.toLocaleLowerCase('tr-TR')}|${(p.phone || '').replace(/\D/g, '')}`;
}

/** ISO 8601, "dd.mm.yyyy[ hh:mm[:ss]]" ve "/Date(ms)/" biçimlerini epoch ms'e çevirir. */
export function parseTimestamp(value) {
  if (!value) return null;
  const text = String(value).trim();

  const aspNet = text.match(/^\/Date\((-?\d+)/);
  if (aspNet) return Number(aspNet[1]);

  const tr = text.match(/^(\d{2})[./](\d{2})[./](\d{4})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?/);
  if (tr) {
    const [, d, m, y, hh = '0', mm = '0', ss = '0'] = tr;
    return new Date(+y, +m - 1, +d, +hh, +mm, +ss).getTime();
  }

  const parsed = Date.parse(text);
  return Number.isNaN(parsed) ? null : parsed;
}

function numericId(externalId) {
  return externalId && /^\d{1,15}$/.test(externalId) ? Number(externalId) : null;
}

async function loadState(providerId) {
  const { [deltaKey(providerId)]: state } = await chrome.storage.local.get(deltaKey(providerId));
  return { lastId: null, lastCreatedAt: null, seen: [], ...state };
}

/**
 * Kayıtları delta'ya göre süzer, yenileri kuyruğa ekler ve watermark'ı ilerletir.
 * Çağıran taraf sağlayıcı bazlı kilit altında çağırmalıdır.
 */
export async function enqueueNewRecords(providerId, records, strategy) {
  const state = await loadState(providerId);
  const { [queueKey(providerId)]: queue = [] } = await chrome.storage.local.get(queueKey(providerId));

  const seen = new Set(state.seen);
  const queued = new Set(queue.map((item) => item.h));
  let { lastId, lastCreatedAt } = state;
  const fresh = [];

  for (const record of records) {
    const hash = await sha256(identityOf(providerId, record));
    const id = numericId(record.externalId);
    const ts = parseTimestamp(record.createdAt);

    let isNew = true;
    if (strategy === 'auto') {
      if (id !== null && state.lastId !== null) isNew = id > state.lastId;
      else if (ts !== null && state.lastCreatedAt !== null) isNew = ts > state.lastCreatedAt;
    }
    if (seen.has(hash) || queued.has(hash)) isNew = false;

    if (id !== null) lastId = lastId === null ? id : Math.max(lastId, id);
    if (ts !== null) lastCreatedAt = lastCreatedAt === null ? ts : Math.max(lastCreatedAt, ts);

    if (isNew) {
      fresh.push({ h: hash, p: record.patient });
      queued.add(hash);
    }
    seen.add(hash);
  }

  const nextQueue = queue.concat(fresh).slice(-MAX_QUEUE);
  const nextSeen = [...seen].slice(-MAX_SEEN);

  await chrome.storage.local.set({
    [deltaKey(providerId)]: { lastId, lastCreatedAt, seen: nextSeen },
    [queueKey(providerId)]: nextQueue,
  });
  return { received: records.length, queued: fresh.length, queueSize: nextQueue.length };
}

export async function peekQueue(providerId, limit) {
  const { [queueKey(providerId)]: queue = [] } = await chrome.storage.local.get(queueKey(providerId));
  return queue.slice(0, limit);
}

export async function queueSize(providerId) {
  const { [queueKey(providerId)]: queue = [] } = await chrome.storage.local.get(queueKey(providerId));
  return queue.length;
}

export async function removeFromQueue(providerId, hashes) {
  const drop = new Set(hashes);
  const { [queueKey(providerId)]: queue = [] } = await chrome.storage.local.get(queueKey(providerId));
  const next = queue.filter((item) => !drop.has(item.h));
  await chrome.storage.local.set({ [queueKey(providerId)]: next });
  return next.length;
}

export async function recordDeadLetter(providerId, error, count) {
  const { [deadKey(providerId)]: dead = [] } = await chrome.storage.local.get(deadKey(providerId));
  const next = dead.concat({ at: new Date().toISOString(), error: String(error).slice(0, 500), count }).slice(-MAX_DEAD);
  await chrome.storage.local.set({ [deadKey(providerId)]: next });
}

export async function resetProvider(providerId) {
  await chrome.storage.local.remove([deltaKey(providerId), queueKey(providerId), deadKey(providerId)]);
}
