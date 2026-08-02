'use client';
/**
 * RouteGuard — Her dashboard alt-route'u render etmeden önce
 * PermissionContext üzerinden yetki kontrolü yapar.
 * Yetkisiz erişimlerde <Forbidden /> bileşenini gösterir.
 */
import { usePathname } from 'next/navigation';
import { useAuthContext } from '@/context/AuthContext';
import { usePermissions } from '@/context/PermissionContext';
import { Forbidden } from '@/components/layout/Forbidden';
import { Skeleton } from '@/components/ui/Skeleton';

export function RouteGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { loading } = useAuthContext();
  const { canAccess } = usePermissions();

  if (loading) {
    return (
      <div className="space-y-4 p-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  if (!canAccess(pathname)) {
    return <Forbidden />;
  }

  return <>{children}</>;
}
