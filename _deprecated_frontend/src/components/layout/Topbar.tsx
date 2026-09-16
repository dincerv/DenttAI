'use client';
import { usePathname } from 'next/navigation';
import { Bell } from 'lucide-react';
import { format } from 'date-fns';
import { tr } from 'date-fns/locale';
import { useAuth } from '@/hooks/useAuth';

const BASE_TITLES: Record<string, string> = {
  '/dashboard/appointments':        'Randevular',
  '/dashboard/waitlist':            'Yedek Liste',
  '/dashboard/inventory':           'Envanter',
  '/dashboard/admin/tenants':       'Admin Paneli — Klinikler',
};

const DASHBOARD_TITLE_BY_ROLE: Record<string, string> = {
  doctor:      'Performansım',
  owner:       'Klinik Genel Bakış',
  super_admin: 'Klinik Genel Bakış',
  assistant:   'Operasyon Paneli',
};

export function Topbar() {
  const pathname = usePathname();
  const { user } = useAuth();
  const role  = user?.role ?? 'owner';
  const title = BASE_TITLES[pathname] ?? (
    pathname === '/dashboard' ? (DASHBOARD_TITLE_BY_ROLE[role] ?? 'Dashboard') : 'DentAI Flow'
  );
  const today = format(new Date(), "d MMMM yyyy, EEEE", { locale: tr });

  return (
    <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-6 shadow-sm">
      <div>
        <h1 className="text-lg font-semibold text-slate-800">{title}</h1>
        <p className="text-xs text-slate-500 capitalize">{today}</p>
      </div>
      <div className="flex items-center gap-3">
        <button
          aria-label="Bildirimler"
          className="relative rounded-full p-2 text-slate-500 hover:bg-slate-100 transition-colors"
        >
          <Bell className="h-5 w-5" />
          <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-red-500" />
        </button>
      </div>
    </header>
  );
}
