/**
 * Auth helpers - secure token storage, decode, and impersonation utilities.
 * Access token is kept in memory with sessionStorage fallback.
 */

let accessTokenMemory: string | null = null;

const ACCESS_TOKEN_SESSION_KEY = 'dentai_access_token_session';
const IMP_TOKEN_SESSION_KEY = 'dentai_imp_token';
const IMP_CLINIC_SESSION_KEY = 'dentai_imp_clinic';
/** Middleware'in görebileceği oturum bayrağı (JWT değil; sadece varlık kontrolü) */
export const SESSION_COOKIE_NAME = 'dentai_session';

function setSessionCookie(): void {
  // Path=/; SameSite=Lax — Next.js middleware (localhost:3000) okuyabilir
  document.cookie = `${SESSION_COOKIE_NAME}=1; Path=/; SameSite=Lax; Max-Age=${60 * 60 * 24 * 30}`;
}

function clearSessionCookie(): void {
  document.cookie = `${SESSION_COOKIE_NAME}=; Path=/; SameSite=Lax; Max-Age=0`;
}

export function setTokens(accessToken: string, refreshToken: string): void {
  if (typeof window === 'undefined') return;
  void refreshToken; // refresh token is stored in httpOnly cookie by backend
  accessTokenMemory = accessToken;
  setSessionCookie();
  try {
    sessionStorage.setItem(ACCESS_TOKEN_SESSION_KEY, accessToken);
  } catch {
    // Session storage can be disabled; memory fallback is still available.
  }
}

export function getAccessToken(): string | null {
  if (typeof window === 'undefined') return null;
  if (accessTokenMemory) return accessTokenMemory;
  try {
    const token = sessionStorage.getItem(ACCESS_TOKEN_SESSION_KEY);
    accessTokenMemory = token;
    // Eski oturumlar için middleware cookie'sini yenile
    if (token) setSessionCookie();
    return token;
  } catch {
    return null;
  }
}

export function getRefreshToken(): string | null {
  // Kept for backward compatibility. Refresh token now lives in httpOnly cookie.
  return null;
}

export function clearTokens(): void {
  if (typeof window === 'undefined') return;
  accessTokenMemory = null;
  clearSessionCookie();
  try {
    sessionStorage.removeItem(ACCESS_TOKEN_SESSION_KEY);
  } catch {
    // no-op
  }
}

export interface JwtClaims {
  user_id: string;
  clinic_id: string | null | undefined;
  role: string;
  email: string;
  full_name?: string;
  impersonation?: boolean;
  impersonated_clinic_id?: string;
  exp: number;
}

function base64UrlDecode(str: string): string {
  const padded = str.replace(/-/g, '+').replace(/_/g, '/');
  const padLength = (4 - (padded.length % 4)) % 4;
  return atob(padded + '='.repeat(padLength));
}

export function decodeToken(token: string): JwtClaims | null {
  try {
    const [, payloadB64] = token.split('.');
    const payload = JSON.parse(base64UrlDecode(payloadB64));
    return payload as JwtClaims;
  } catch {
    return null;
  }
}

export function getCurrentClaims(): JwtClaims | null {
  const token = getAccessToken();
  if (!token) return null;
  return decodeToken(token);
}

export function isTokenExpired(token: string): boolean {
  const claims = decodeToken(token);
  if (!claims) return true;
  return claims.exp * 1000 < Date.now();
}

export function isAuthenticated(): boolean {
  const token = getAccessToken();
  if (!token) return false;
  return !isTokenExpired(token);
}

export function setImpersonation(token: string, clinicName: string, clinicSlug: string): void {
  if (typeof window === 'undefined') return;
  try {
    sessionStorage.setItem(IMP_TOKEN_SESSION_KEY, token);
    sessionStorage.setItem(IMP_CLINIC_SESSION_KEY, JSON.stringify({ name: clinicName, slug: clinicSlug }));
  } catch {
    // no-op
  }
}

export function getImpersonationToken(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return sessionStorage.getItem(IMP_TOKEN_SESSION_KEY);
  } catch {
    return null;
  }
}

export function getImpersonationClinic(): { name: string; slug: string } | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = sessionStorage.getItem(IMP_CLINIC_SESSION_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function clearImpersonation(): void {
  if (typeof window === 'undefined') return;
  try {
    sessionStorage.removeItem(IMP_TOKEN_SESSION_KEY);
    sessionStorage.removeItem(IMP_CLINIC_SESSION_KEY);
  } catch {
    // no-op
  }
}

export function isImpersonating(): boolean {
  return !!getImpersonationToken();
}
