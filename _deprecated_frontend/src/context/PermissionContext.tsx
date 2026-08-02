'use client';
/**
 * PermissionProvider — Per-user yetki yönetimi.
 *
 * Admin (owner) her kullanıcıya ayrı ayrı sayfa erişim yetkisi verebilir.
 * Yetki listesi backend'den allowed_pages olarak gelir.
 * owner ve super_admin her zaman tam erişime sahiptir.
 *
 * Kullanım:
 *   const { can, canAccess } = usePermissions();
 *   if (can('view', 'dashboard')) { ... }
 *   if (canAccess('/dashboard/inventory')) { ... }
 */
import { createContext, useContext, useMemo } from 'react';
import { useAuthContext } from '@/context/AuthContext';

// ── Roller ────────────────────────────────────────────────
export type AppRole = 'super_admin' | 'owner' | 'doctor' | 'assistant';

// ── Modüller ──────────────────────────────────────────────
export type Module =
  | 'dashboard'
  | 'appointments'
  | 'waitlist'
  | 'inventory'
  | 'integrations'
  | 'permissions'
  | 'admin';

// ── Aksiyon Tipleri ───────────────────────────────────────
export type Action = 'view' | 'create' | 'edit' | 'delete';

// ── Modül → Aksiyon eşleştirmesi (sayfa erişimi varsa verilen aksiyonlar) ──
const MODULE_ACTIONS: Record<Module, Action[]> = {
  dashboard:    ['view'],
  appointments: ['view', 'create', 'edit', 'delete'],
  waitlist:     ['view', 'create', 'edit', 'delete'],
  inventory:    ['view', 'create', 'edit', 'delete'],
  integrations: ['view', 'create', 'edit', 'delete'],
  permissions:  ['view', 'create', 'edit', 'delete'],
  admin:        ['view', 'create', 'edit', 'delete'],
};

// ── Tam erişim rolleri ────────────────────────────────────
const FULL_ACCESS_ROLES: AppRole[] = ['super_admin', 'owner'];

// ── Route → Module eşleştirmesi ───────────────────────────
const ROUTE_MODULE_MAP: Record<string, Module> = {
  '/dashboard':              'dashboard',
  '/dashboard/appointments': 'appointments',
  '/dashboard/waitlist':     'waitlist',
  '/dashboard/inventory':    'inventory',
  '/dashboard/integrations': 'integrations',
  '/dashboard/permissions':  'permissions',
  '/dashboard/admin':        'admin',
  '/dashboard/admin/tenants':'admin',
};

// ── Context ───────────────────────────────────────────────
interface PermissionContextValue {
  role: AppRole;
  /** Belirli bir modülde belirli bir aksiyon yapılabilir mi? */
  can: (action: Action, module: Module) => boolean;
  /** Belirli bir route'a erişim var mı? (view yetkisi kontrolü) */
  canAccess: (path: string) => boolean;
  /** Kullanıcının erişebildiği modül listesi */
  allowedModules: Module[];
}

const PermissionContext = createContext<PermissionContextValue | null>(null);

// ── Provider ──────────────────────────────────────────────
export function PermissionProvider({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuthContext();
  const role = (user?.role ?? 'assistant') as AppRole;
  const allowedPages: string[] = user?.allowed_pages ?? [];

  const value = useMemo<PermissionContextValue>(() => {
    // Kullanıcı verisi henüz yüklenmediyse her şeye izin ver (flash 403'ü engelle)
    if (loading) {
      return {
        role,
        can: () => true,
        canAccess: () => true,
        allowedModules: Object.keys(MODULE_ACTIONS) as Module[],
      };
    }

    // owner ve super_admin her zaman tam erişime sahip
    const isFullAccess = FULL_ACCESS_ROLES.includes(role);

    const can = (action: Action, module: Module): boolean => {
      if (isFullAccess) return module !== 'admin' || role === 'super_admin';
      if (!allowedPages.includes(module)) return false;
      // Randevu ekraninda yazma islemleri ayri bir izin anahtarina bagli.
      if (module === 'appointments' && action !== 'view' && !allowedPages.includes('appointments_write')) {
        return false;
      }
      return MODULE_ACTIONS[module]?.includes(action) ?? false;
    };

    const canAccess = (path: string): boolean => {
      // Exact match first
      const module = ROUTE_MODULE_MAP[path];
      if (module) return can('view', module);

      // Prefix match (for nested routes like /dashboard/admin/tenants)
      const sortedRoutes = Object.keys(ROUTE_MODULE_MAP).sort((a, b) => b.length - a.length);
      for (const route of sortedRoutes) {
        if (path.startsWith(route)) {
          return can('view', ROUTE_MODULE_MAP[route]);
        }
      }

      // Unknown routes — allow (no restriction)
      return true;
    };

    const allModules = Object.keys(MODULE_ACTIONS) as Module[];
    const allowedModules = isFullAccess
      ? allModules.filter((mod) => mod !== 'admin' || role === 'super_admin')
      : allModules.filter((mod) => allowedPages.includes(mod));

    return { role, can, canAccess, allowedModules };
  }, [role, allowedPages, loading]);

  return (
    <PermissionContext.Provider value={value}>
      {children}
    </PermissionContext.Provider>
  );
}

// ── Hook ──────────────────────────────────────────────────
export function usePermissions(): PermissionContextValue {
  const ctx = useContext(PermissionContext);
  if (!ctx) {
    throw new Error('usePermissions must be used inside <PermissionProvider>');
  }
  return ctx;
}
