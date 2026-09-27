/**
 * DentAI Flow API istemcisi — login, token rotation, hasta içe aktarma.
 *
 * Endpoint'ler (services/api):
 *   POST /api/auth/login                   → TokenResponse
 *   GET  /api/auth/health                  → X-CSRF-Token header
 *   POST /api/auth/refresh                 → TokenResponse (Bearer olmadığı için CSRF ister)
 *   POST /api/integration/import/patients  → ImportResult (Bearer ile CSRF muaf)
 */

export const DEFAULT_API_BASE = 'https://denttai-production.up.railway.app';
const AUTH_KEY = 'dentai:auth';
const CONFIG_KEY = 'dentai:config';
const REFRESH_SKEW_MS = 60_000;

export class AuthError extends Error {}

export class ValidationError extends Error {
  constructor(message, detail) {
    super(message);
    this.detail = detail;
  }
}

let refreshInFlight = null;

function normalizeBase(url) {
  return String(url || DEFAULT_API_BASE).trim().replace(/\/+$/, '');
}

function decodeJwt(token) {
  try {
    const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = payload + '='.repeat((4 - (payload.length % 4)) % 4);
    return JSON.parse(atob(padded));
  } catch {
    return null;
  }
}

async function errorDetail(res) {
  try {
    const body = await res.json();
    if (typeof body?.detail === 'string') return body.detail;
    return JSON.stringify(body?.detail ?? body).slice(0, 500);
  } catch {
    return `HTTP ${res.status}`;
  }
}

export async function getApiBase() {
  const { [CONFIG_KEY]: config } = await chrome.storage.local.get(CONFIG_KEY);
  return normalizeBase(config?.apiBaseUrl);
}

async function saveTokens(tokenResponse) {
  const auth = {
    accessToken: tokenResponse.access_token,
    refreshToken: tokenResponse.refresh_token,
    expiresAt: Date.now() + Number(tokenResponse.expires_in || 0) * 1000,
  };
  await chrome.storage.local.set({ [AUTH_KEY]: auth });
  return auth;
}

async function loadTokens() {
  const { [AUTH_KEY]: auth } = await chrome.storage.local.get(AUTH_KEY);
  return auth ?? null;
}

export async function clearSession() {
  await chrome.storage.local.remove(AUTH_KEY);
}

export async function getSessionInfo() {
  const auth = await loadTokens();
  if (!auth?.refreshToken) return null;
  const claims = decodeJwt(auth.accessToken) ?? {};
  return {
    email: claims.email ?? null,
    role: claims.role ?? null,
    clinicId: claims.clinic_id ?? null,
    apiBaseUrl: await getApiBase(),
  };
}

export async function isAuthenticated() {
  return Boolean((await loadTokens())?.refreshToken);
}

export async function login({ apiBaseUrl, email, password, clinicCode }) {
  const base = normalizeBase(apiBaseUrl);
  const granted = await chrome.permissions.contains({ origins: [`${base}/*`] });
  if (!granted) {
    throw new AuthError(`${base} manifest host_permissions listesinde değil.`);
  }

  const res = await fetch(`${base}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, clinic_code: clinicCode || null }),
  });
  if (!res.ok) throw new AuthError(await errorDetail(res));

  await chrome.storage.local.set({ [CONFIG_KEY]: { apiBaseUrl: base } });
  await saveTokens(await res.json());
  return getSessionInfo();
}

async function fetchCsrfToken(base) {
  try {
    const res = await fetch(`${base}/api/auth/health`);
    return res.headers.get('X-CSRF-Token') || '';
  } catch {
    return '';
  }
}

async function refreshTokens() {
  const auth = await loadTokens();
  if (!auth?.refreshToken) throw new AuthError('DentAI oturumu yok');

  const base = await getApiBase();
  const csrf = await fetchCsrfToken(base);
  const headers = { 'Content-Type': 'application/json' };
  if (csrf) headers['X-CSRF-Token'] = csrf;

  const res = await fetch(`${base}/api/auth/refresh`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ refresh_token: auth.refreshToken }),
  });
  if (res.status === 401 || res.status === 403) {
    await clearSession();
    throw new AuthError('DentAI oturumu sona erdi, tekrar giriş yapın');
  }
  if (!res.ok) throw new Error(`Token yenilenemedi: HTTP ${res.status}`);
  return saveTokens(await res.json());
}

async function getAccessToken({ force = false } = {}) {
  const auth = await loadTokens();
  if (!auth?.refreshToken) throw new AuthError('DentAI oturumu yok');
  if (!force && auth.accessToken && auth.expiresAt - REFRESH_SKEW_MS > Date.now()) {
    return auth.accessToken;
  }
  refreshInFlight ??= refreshTokens().finally(() => {
    refreshInFlight = null;
  });
  return (await refreshInFlight).accessToken;
}

export async function importPatients(patients) {
  const base = await getApiBase();
  const post = (token) =>
    fetch(`${base}/api/integration/import/patients`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ patients }),
    });

  let res = await post(await getAccessToken());
  if (res.status === 401) res = await post(await getAccessToken({ force: true }));

  if (res.status === 401 || res.status === 403) throw new AuthError(await errorDetail(res));
  if (res.status === 422) throw new ValidationError('Kayıtlar doğrulanamadı', await errorDetail(res));
  if (!res.ok) throw new Error(`DentAI import başarısız: HTTP ${res.status}`);
  return res.json();
}
