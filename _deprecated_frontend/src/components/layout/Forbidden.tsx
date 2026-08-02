'use client';
/**
 * Forbidden — 403 Yetkisiz Erişim sayfası.
 * Yetkisiz bir route'a URL ile doğrudan erişildiğinde gösterilir.
 */
import { ShieldX } from 'lucide-react';
import Link from 'next/link';

export function Forbidden() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center text-center">
      <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-red-50">
        <ShieldX className="h-10 w-10 text-red-500" />
      </div>
      <h1 className="mb-2 text-2xl font-bold text-slate-800">
        403 — Yetkisiz Erişim
      </h1>
      <p className="mb-6 max-w-md text-sm text-slate-500">
        Bu sayfayı görüntüleme yetkiniz bulunmamaktadır.
        Erişim izni için klinik yöneticinizle iletişime geçin.
      </p>
      <Link
        href="/dashboard"
        className="rounded-lg bg-brand-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-brand-700 transition-colors"
      >
        Ana Sayfaya Dön
      </Link>
    </div>
  );
}
