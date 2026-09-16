'use client';
/**
 * AuthContext — auth durumu tek bir yerden yönetilir.
 * Sidebar, Topbar, Page gibi tüm bileşenler bu context'i tüketir;
 * bu sayede her mount yalnızca TEK bir /auth/me isteği tetiklenir.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react';
import { useRouter } from 'next/navigation';
import { authApi } from '@/lib/api-client';
import {
  clearTokens,
  getCurrentClaims,
  isAuthenticated,
  setTokens,
} from '@/lib/auth';
import type { JwtClaims } from '@/lib/auth';
import type { MeResponse } from '@/types';

// ── Tip ───────────────────────────────────────────────────
interface AuthState {
  user: MeResponse | null;
  claims: JwtClaims | null;
  loading: boolean;
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string, clinicCode?: string) => Promise<void>;
  logout: () => void;
}

// ── Context ───────────────────────────────────────────────
const AuthContext = createContext<AuthContextValue | null>(null);

// ── Provider ──────────────────────────────────────────────
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [state, setState] = useState<AuthState>({
    user: null,
    claims: null,
    loading: true,
  });

  // Uygulama ilk yüklendiğinde TEK SEFER /auth/me çek
  useEffect(() => {
    if (!isAuthenticated()) {
      setState({ user: null, claims: null, loading: false });
      return;
    }
    authApi
      .me()
      .then((res) => {
        setState({ user: res.data, claims: getCurrentClaims(), loading: false });
      })
      .catch(() => {
        clearTokens();
        setState({ user: null, claims: null, loading: false });
      });
  }, []);

  const login = useCallback(
    async (email: string, password: string, clinicCode?: string) => {
      const res = await authApi.login(email, password, clinicCode);
      setTokens(res.data.access_token, res.data.refresh_token);
      const meRes = await authApi.me();
      setState({ user: meRes.data, claims: getCurrentClaims(), loading: false });
      router.push('/dashboard');
    },
    [router],
  );

  const logout = useCallback(() => {
    authApi
      .logout()
      .catch(() => undefined)
      .finally(() => {
        clearTokens();
        setState({ user: null, claims: null, loading: false });
        router.push('/login');
      });
  }, [router]);

  return (
    <AuthContext.Provider value={{ ...state, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

// ── Hook ──────────────────────────────────────────────────
export function useAuthContext(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuthContext must be used inside <AuthProvider>');
  }
  return ctx;
}
