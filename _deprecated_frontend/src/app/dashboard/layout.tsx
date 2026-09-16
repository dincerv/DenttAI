'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { isAuthenticated, getImpersonationClinic, clearImpersonation } from '@/lib/auth';
import { Sidebar } from '@/components/layout/Sidebar';
import { Topbar } from '@/components/layout/Topbar';
import { PermissionProvider } from '@/context/PermissionContext';
import { RouteGuard } from '@/components/layout/RouteGuard';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [impClinic, setImpClinic] = useState<{ name: string; slug: string } | null>(null);

  // Client-side auth guard
  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace('/login');
    }
    setImpClinic(getImpersonationClinic());
  }, [router]);

  function exitImpersonation() {
    clearImpersonation();
    router.push('/dashboard/admin/tenants');
    // Force reload so the request interceptor uses the original token
    window.location.href = '/dashboard/admin/tenants';
  }

  return (
    <PermissionProvider>
      <div className="flex h-screen overflow-hidden bg-slate-50">
        <Sidebar />
        <div className="flex flex-1 flex-col overflow-hidden pl-64">
          {impClinic && (
            <div className="flex shrink-0 items-center justify-between bg-amber-500 px-5 py-2 text-sm text-white">
              <span>
                <strong>👁 {impClinic.name}</strong>
                <span className="ml-1 opacity-80">(@{impClinic.slug}) kliniğini görüntülüyorsunuz</span>
              </span>
              <button
                onClick={exitImpersonation}
                className="rounded-lg border border-white/40 px-3 py-1 text-xs font-semibold hover:bg-white/20"
              >
                ← Admin Paneline Dön
              </button>
            </div>
          )}
          <Topbar />
          <main className="flex-1 overflow-y-auto p-6">
            <RouteGuard>
              {children}
            </RouteGuard>
          </main>
        </div>
      </div>
    </PermissionProvider>
  );
}
