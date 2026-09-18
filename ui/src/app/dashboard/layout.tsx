'use client';
import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { isAuthenticated, getImpersonationClinic, clearImpersonation } from '@/lib/auth';
import { Sidebar } from '@/components/layout/Sidebar';
import { Topbar } from '@/components/layout/Topbar';
import { PermissionProvider } from '@/context/PermissionContext';
import { RouteGuard } from '@/components/layout/RouteGuard';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [impClinic, setImpClinic] = useState<{ name: string; slug: string } | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace('/login');
    }
    setImpClinic(getImpersonationClinic());
  }, [router]);

  const toggleSidebar = useCallback(() => setSidebarOpen((v) => !v), []);
  const closeSidebar  = useCallback(() => setSidebarOpen(false), []);

  function exitImpersonation() {
    clearImpersonation();
    router.push('/dashboard/admin/tenants');
    window.location.href = '/dashboard/admin/tenants';
  }

  return (
    <PermissionProvider>
      <div className="flex h-screen overflow-hidden bg-slate-50">
        <Sidebar open={sidebarOpen} onClose={closeSidebar} />

        {/* Mobil overlay — sidebar açıkken arka planı karartır */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 z-30 bg-black/50 lg:hidden"
            onClick={closeSidebar}
            aria-hidden="true"
          />
        )}

        {/* İçerik alanı: desktop'ta sidebar'ın sağında, mobilde tam genişlik */}
        <div className="flex flex-1 flex-col overflow-hidden lg:pl-64">
          {impClinic && (
            <div className="flex shrink-0 items-center justify-between bg-amber-500 px-4 sm:px-5 py-2 text-xs sm:text-sm text-white">
              <span className="truncate">
                <strong>👁 {impClinic.name}</strong>
                <span className="ml-1 opacity-80 hidden sm:inline">(@{impClinic.slug}) kliniğini görüntülüyorsunuz</span>
              </span>
              <button
                onClick={exitImpersonation}
                className="ml-2 flex-shrink-0 rounded-lg border border-white/40 px-3 py-1 text-xs font-semibold hover:bg-white/20"
              >
                ← Geri Dön
              </button>
            </div>
          )}

          <Topbar onMenuToggle={toggleSidebar} />

          <main className="flex-1 overflow-y-auto p-4 sm:p-6">
            <RouteGuard>
              {children}
            </RouteGuard>
          </main>
        </div>
      </div>
    </PermissionProvider>
  );
}
