/**
 * DentAI PMS Sync — Background Service Worker (MV3).
 *
 * Akışlar:
 *   1) Periyodik: chrome.alarms (15 dk) → sağlayıcının hasta listesi endpoint'i
 *      - Açık PMS sekmesi varsa: chrome.scripting ile sayfanın MAIN world'ünde fetch
 *        (aynı origin → çerez, SameSite ve Cloudflare sorunları olmaz)
 *      - Yoksa: son görülen origin'e service worker'dan credentials:'include' ile fetch
 *   2) Gerçek zamanlı: content.js'in yakaladığı JSON yanıtları (PMS_INTERCEPT)
 *
 * Her iki akış da aynı hattan geçer: extractItems → toRecord → delta → kuyruk → DentAI POST.
 */

import { PROVIDERS, providerForUrl } from './providers.js';
import { enqueueNewRecords, peekQueue, queueSize, recordDeadLetter, removeFromQueue, resetProvider } from './delta-store.js';
import { AuthError, ValidationError, clearSession, getSessionInfo, importPatients, isAuthenticated, login } from './dentai-client.js';

const ALARM_NAME = 'dentai-pms-sync';
const SYNC_PERIOD_MINUTES = 15;
const BATCH_SIZE = 200;
const originKey = (providerId) => `origin:${providerId}`;
const statusKey = (providerId) => `status:${providerId}`;

// ── Kilit (sağlayıcı bazlı seri çalıştırma) ───────────────────────────────

const locks = new Map();

function withLock(key, fn) {
  const previous = locks.get(key) ?? Promise.resolve();
  const next = previous.catch(() => {}).then(fn);
  locks.set(key, next.catch(() => {}));
  return next;
}

// ── Durum / rozet ─────────────────────────────────────────────────────────

async function updateStatus(providerId, patch) {
  const key = statusKey(providerId);
  const { [key]: current = {} } = await chrome.storage.local.get(key);
  const next = { ...current, ...patch, updatedAt: new Date().toISOString() };
  await chrome.storage.local.set({ [key]: next });
  await refreshBadge();
  return next;
}

async function refreshBadge() {
  const keys = Object.keys(PROVIDERS).map(statusKey);
  const statuses = Object.values(await chrome.storage.local.get(keys));
  const hasError = statuses.some((s) => s?.lastError);
  const pending = statuses.reduce((sum, s) => sum + (s?.queued || 0), 0);
  await chrome.action.setBadgeBackgroundColor({ color: hasError ? '#DC2626' : '#2563EB' });
  await chrome.action.setBadgeText({ text: hasError ? '!' : pending ? String(Math.min(pending, 999)) : '' });
}

// ── Alarm ─────────────────────────────────────────────────────────────────

async function ensureAlarm() {
  const alarm = await chrome.alarms.get(ALARM_NAME);
  if (!alarm || alarm.periodInMinutes !== SYNC_PERIOD_MINUTES) {
    await chrome.alarms.create(ALARM_NAME, { delayInMinutes: 1, periodInMinutes: SYNC_PERIOD_MINUTES });
  }
}

chrome.runtime.onInstalled.addListener(() => {
  ensureAlarm();
  refreshBadge();
});
chrome.runtime.onStartup.addListener(ensureAlarm);

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === ALARM_NAME) syncAll('alarm');
});

// ── Ortak hat: ingest + flush ─────────────────────────────────────────────

async function ingest(provider, json, source) {
  const records = provider
    .extractItems(json)
    .map((raw) => {
      try {
        return provider.toRecord(raw);
      } catch {
        return null;
      }
    })
    .filter(Boolean);

  if (!records.length) return { received: 0, queued: 0 };

  const result = await withLock(provider.id, () => enqueueNewRecords(provider.id, records, provider.deltaStrategy));
  await updateStatus(provider.id, {
    lastIngestAt: new Date().toISOString(),
    lastSource: source,
    lastReceived: result.received,
    lastQueued: result.queued,
    queued: result.queueSize,
  });
  return result;
}

async function sendBatch(providerId, batch) {
  try {
    return await importPatients(batch.map((item) => item.p));
  } catch (error) {
    if (!(error instanceof ValidationError)) throw error;
    if (batch.length === 1) {
      await recordDeadLetter(providerId, error.detail ?? error.message, 1);
      return { inserted: 0, skipped_duplicates: 0, skipped_invalid: 1 };
    }
    const mid = Math.ceil(batch.length / 2);
    const left = await sendBatch(providerId, batch.slice(0, mid));
    const right = await sendBatch(providerId, batch.slice(mid));
    return {
      inserted: (left.inserted || 0) + (right.inserted || 0),
      skipped_duplicates: (left.skipped_duplicates || 0) + (right.skipped_duplicates || 0),
      skipped_invalid: (left.skipped_invalid || 0) + (right.skipped_invalid || 0),
    };
  }
}

function flushQueue(providerId) {
  return withLock(`flush:${providerId}`, async () => {
    const totals = { inserted: 0, skipped_duplicates: 0, skipped_invalid: 0 };
    try {
      for (;;) {
        const batch = await peekQueue(providerId, BATCH_SIZE);
        if (!batch.length) break;
        const result = await sendBatch(providerId, batch);
        totals.inserted += result.inserted || 0;
        totals.skipped_duplicates += result.skipped_duplicates || 0;
        totals.skipped_invalid += result.skipped_invalid || 0;
        await removeFromQueue(providerId, batch.map((item) => item.h));
      }
      await updateStatus(providerId, {
        lastFlushAt: new Date().toISOString(),
        lastFlushResult: totals,
        lastError: null,
        queued: await queueSize(providerId),
      });
    } catch (error) {
      await updateStatus(providerId, {
        lastError: error instanceof AuthError ? `AUTH: ${error.message}` : error.message,
        queued: await queueSize(providerId),
      });
    }
    return totals;
  });
}

// ── Periyodik çekim ───────────────────────────────────────────────────────

async function resolveTarget(provider) {
  const tabs = await chrome.tabs.query({ url: provider.matchPatterns });
  const tab = tabs.find((t) => t.status === 'complete' && !t.discarded && t.url) ?? tabs.find((t) => t.url);
  if (tab) {
    const baseUrl = new URL(tab.url).origin;
    await chrome.storage.local.set({ [originKey(provider.id)]: baseUrl });
    return { tabId: tab.id, baseUrl };
  }
  const { [originKey(provider.id)]: baseUrl } = await chrome.storage.local.get(originKey(provider.id));
  return baseUrl ? { tabId: null, baseUrl } : null;
}

async function executeFetch(provider, target, page) {
  try {
    if (target.tabId !== null) {
      const [injection] = await chrome.scripting.executeScript({
        target: { tabId: target.tabId },
        world: 'MAIN',
        func: provider.periodicFetch,
        args: [target.baseUrl, provider.periodicOptions, page],
      });
      return injection?.result ?? { ok: false, reason: 'NO_RESULT' };
    }
    return await provider.periodicFetch(target.baseUrl, provider.periodicOptions, page);
  } catch (error) {
    return { ok: false, reason: 'FETCH_ERROR', message: String(error?.message || error) };
  }
}

async function runPeriodic(provider) {
  const target = await resolveTarget(provider);
  if (!target) {
    await updateStatus(provider.id, { pmsSession: 'UNKNOWN_ORIGIN' });
    return;
  }

  for (let page = 1; page <= provider.maxPages; page++) {
    const res = await executeFetch(provider, target, page);
    if (!res.ok) {
      await updateStatus(provider.id, {
        pmsSession: res.reason === 'SESSION_EXPIRED' ? 'EXPIRED' : 'ERROR',
        lastPeriodicError: `${res.reason}${res.status ? ` (${res.status})` : ''}${res.message ? `: ${res.message}` : ''}`,
      });
      return;
    }
    const { received, queued } = await ingest(provider, res.data, target.tabId !== null ? 'periodic:tab' : 'periodic:sw');
    await updateStatus(provider.id, { pmsSession: 'OK', lastPeriodicAt: new Date().toISOString(), lastPeriodicError: null });
    if (!received || !queued) break;
  }
}

async function syncAll(trigger) {
  if (!(await isAuthenticated())) return;
  for (const provider of Object.values(PROVIDERS)) {
    try {
      await runPeriodic(provider);
    } catch (error) {
      await updateStatus(provider.id, { lastPeriodicError: String(error?.message || error) });
    }
    await flushQueue(provider.id);
  }
  console.info(`[dentai-sync] ${trigger} tamamlandı`);
}

// ── Mesajlaşma ────────────────────────────────────────────────────────────

async function handleContentMessage(message, sender) {
  const provider = providerForUrl(sender.url);
  if (!provider) return { ok: false };

  if (message.type === 'GET_INTERCEPT_CONFIG') {
    const enabled = await isAuthenticated();
    return { patterns: enabled ? provider.interceptUrlPatterns : [] };
  }

  if (message.type === 'PMS_INTERCEPT') {
    if (!(await isAuthenticated())) return { ok: false };
    if (typeof message.url !== 'string' || typeof message.body !== 'string') return { ok: false };
    if (!provider.interceptUrlPatterns.some((src) => new RegExp(src, 'i').test(message.url))) return { ok: false };
    if (providerForUrl(message.url)?.id !== provider.id) return { ok: false };

    let json;
    try {
      json = JSON.parse(message.body);
    } catch {
      return { ok: false };
    }
    await chrome.storage.local.set({ [originKey(provider.id)]: new URL(sender.url).origin });
    const result = await ingest(provider, json, 'intercept');
    if (result.queued) flushQueue(provider.id);
    return { ok: true, ...result };
  }
  return { ok: false };
}

async function handlePopupMessage(message) {
  switch (message.type) {
    case 'LOGIN': {
      const session = await login(message.payload);
      syncAll('login');
      return { ok: true, session };
    }
    case 'LOGOUT':
      await clearSession();
      return { ok: true };
    case 'SYNC_NOW':
      await syncAll('manual');
      return { ok: true };
    case 'RESET_PROVIDER':
      if (!PROVIDERS[message.providerId]) return { ok: false };
      await resetProvider(message.providerId);
      await updateStatus(message.providerId, { queued: 0, lastError: null });
      return { ok: true };
    case 'GET_STATUS': {
      const keys = Object.keys(PROVIDERS).map(statusKey);
      const stored = await chrome.storage.local.get(keys);
      const providers = Object.values(PROVIDERS).map((p) => ({ id: p.id, label: p.label, ...stored[statusKey(p.id)] }));
      const alarm = await chrome.alarms.get(ALARM_NAME);
      return { ok: true, session: await getSessionInfo(), providers, nextRunAt: alarm?.scheduledTime ?? null };
    }
    default:
      return { ok: false, error: 'Bilinmeyen komut' };
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (sender.id !== chrome.runtime.id || !message?.type) return false;

  const handler = sender.tab ? handleContentMessage(message, sender) : handlePopupMessage(message);
  handler
    .then(sendResponse)
    .catch((error) => sendResponse({ ok: false, error: String(error?.message || error) }));
  return true;
});
