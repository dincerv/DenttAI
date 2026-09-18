'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Calendar,
  ListOrdered,
  Package,
  LogOut,
  Stethoscope,
  ShieldCheck,
  Cable,
  Building2,
  Banknote,
  FileText,
  Pill,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuth } from '@/hooks/useAuth';
import { usePermissions, type Module } from '@/context/PermissionContext';

type NavItem = {
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  module: Module;
};

const NAV_ITEMS: NavItem[] = [
  { href: '/dashboard',              icon: LayoutDashboard, label: 'Dashboard',      module: 'dashboard' },
  { href: '/dashboard/appointments', icon: Calendar,        label: 'Randevular',     module: 'appointments' },
  { href: '/dashboard/waitlist',     icon: ListOrdered,     label: 'Yedek Liste',    module: 'waitlist' },
  { href: '/dashboard/inventory',    icon: Package,         label: 'Envanter',       module: 'inventory' },
  { href: '/dashboard/payments',     icon: Banknote,        label: 'Ödemeler',       module: 'payments' },
  { href: '/dashboard/invoices',     icon: FileText,        label: 'Faturalar',      module: 'invoices' },
  { href: '/dashboard/prescriptions',icon: Pill,            label: 'e-Reçete',       module: 'prescriptions' },
  { href: '/dashboard/integrations', icon: Cable,           label: 'Entegrasyonlar', module: 'integrations' },
  { href: '/dashboard/permissions',  icon: ShieldCheck,     label: 'Yetkiler',       module: 'permissions' },
  { href: '/dashboard/admin/tenants',icon: Building2,       label: 'Klinikler',      module: 'admin' },
];

const ROLE_LABELS: Record<string, string> = {
  super_admin: 'Süper Admin',
  owner: 'Klinik Sahibi',
  doctor: 'Doktor',
  assistant: 'Asistan',
};

interface SidebarProps {
  /** Mobilde sidebar görünür mü? */
  open: boolean;
  /** Mobilde overlay/kapatma butonuna tıklandığında */
  onClose: () => void;
}

export function Sidebar({ open, onClose }: SidebarProps) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { can } = usePermissions();

  return (
    <aside
      className={cn(
        // Temel: fixed, tam yükseklik, beyaz arka plan üstünde koyu
        'fixed inset-y-0 left-0 z-40 flex w-64 flex-col bg-brand-900 text-white',
        // Geçiş animasyonu
        'transition-transform duration-300 ease-in-out',
        // Desktop (lg+): her zaman görünür
        'lg:translate-x-0',
        // Mobil: open state'ine göre göster/gizle
        open ? 'translate-x-0' : '-translate-x-full',
      )}
    >
      {/* Logo + mobil kapatma butonu */}
      <div className="flex h-16 items-center gap-3 border-b border-brand-800 px-6">
        <Stethoscope className="h-7 w-7 shrink-0 text-brand-300" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-bold leading-tight">DentAI Flow</p>
          <p className="text-xs text-brand-400">Klinik Yönetim Paneli</p>
        </div>
        {/* Sadece mobilde gösterilir */}
        <button
          onClick={onClose}
          aria-label="Menüyü kapat"
          className="lg:hidden ml-auto rounded-lg p-1.5 text-brand-300 hover:bg-brand-800 hover:text-white transition-colors"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Navigation — yetki matrisine göre dinamik */}
      <nav className="flex-1 overflow-y-auto px-4 py-6">
        <ul className="space-y-1">
          {NAV_ITEMS.filter((item) => can('view', item.module)).map(({ href, icon: Icon, label }) => {
            const active = pathname === href || (href !== '/dashboard' && pathname.startsWith(href));
            return (
              <li key={href}>
                <Link
                  href={href}
                  onClick={onClose}
                  className={cn(
                    'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                    active
                      ? 'bg-brand-700 text-white'
                      : 'text-brand-300 hover:bg-brand-800 hover:text-white',
                  )}
                >
                  <Icon className="h-5 w-5 flex-shrink-0" />
                  {label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Footer — user info + logout */}
      <div className="border-t border-brand-800 px-4 py-4">
        {user && (
          <div className="mb-3 rounded-lg bg-brand-800 p-3">
            <p className="truncate text-sm font-medium">{user.full_name}</p>
            <p className="truncate text-xs text-brand-400">{user.email}</p>
            <div className="mt-1 flex items-center gap-2">
              <span className="inline-block rounded-full bg-brand-600 px-2 py-0.5 text-xs">
                {ROLE_LABELS[user.role] ?? user.role}
              </span>
              {user.clinic_code && (
                <span className="inline-block rounded-full bg-brand-700 px-2 py-0.5 text-xs font-mono text-brand-300">
                  {user.clinic_code}
                </span>
              )}
            </div>
          </div>
        )}
        <button
          onClick={logout}
          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-brand-300 hover:bg-brand-800 hover:text-white transition-colors"
        >
          <LogOut className="h-4 w-4" />
          Çıkış Yap
        </button>
      </div>
    </aside>
  );
}
