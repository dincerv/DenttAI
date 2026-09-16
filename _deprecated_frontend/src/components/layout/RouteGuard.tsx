'use client';
/**
 * RouteGuard — Her dashboard alt-route'u render etmeden önce
 * PermissionContext üzerinden yetki kontrolü yapar.
 * Yetkisiz erişimlerde <Forbidden /> bileşenini gösterir.
 */
import { usePathname } from 'next/navigation';
import { usePermissions } from '@/context/PermissionContext';
import { Forbidden } from '@/components/layout/Forbidden';

export function RouteGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { canAccess } = usePermissions();

  // Asistan '/dashboard' → izinsiz → appointments'a redirect etmek yerine
  // doğrudan Forbidden göster (çünkü sidebar'da link yok, URL ile gelmiş demektir)
  if (!canAccess(pathname)) {
    return <Forbidden />;
  }

  return <>{children}</>;
}
