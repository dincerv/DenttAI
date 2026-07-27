'use client';
import { TrendingUp } from 'lucide-react';
import { formatCurrency } from '@/lib/utils';
import { Skeleton } from '@/components/ui/Skeleton';
import type { RecoveredRevenueResponse } from '@/types';

interface Props {
  data: RecoveredRevenueResponse | null;
  loading: boolean;
}

export function RevenueCard({ data, loading }: Props) {
  if (loading) {
    return (
      <div className="rounded-2xl bg-gradient-to-r from-brand-700 via-brand-800 to-brand-900 p-5 text-white shadow-lg">
        <Skeleton className="mb-3 h-4 w-44 bg-brand-600" />
        <Skeleton className="mb-2 h-10 w-56 bg-brand-600" />
        <Skeleton className="h-4 w-40 bg-brand-600" />
      </div>
    );
  }

  return (
    <div className="rounded-2xl bg-gradient-to-r from-brand-700 via-brand-800 to-brand-900 p-5 text-white shadow-lg">
      <div className="mb-1 flex items-center gap-2 text-brand-200">
        <TrendingUp className="h-4 w-4" />
        <span className="text-sm font-medium uppercase tracking-wider">
          Bu Ay Kurtarılan Ciro
        </span>
      </div>

      <p className="mb-1 text-3xl font-extrabold tracking-tight sm:text-4xl">
        {formatCurrency(data?.total_recovered_revenue ?? 0)}
      </p>

      <p className="text-sm text-brand-200">
        {data?.total_recovered_appointments ?? 0} randevu yedek liste sayesinde dolduruldu
      </p>

      {/* Branş dağılımı */}
      {data && data.by_specialty.length > 0 && (
        <div className="mt-4 grid grid-cols-2 gap-2.5 sm:grid-cols-3">
          {data.by_specialty.slice(0, 6).map((s) => (
            <div key={s.specialty} className="rounded-lg border border-white/10 bg-brand-800/50 p-2.5">
              <p className="truncate text-[11px] text-brand-200">{s.specialty}</p>
              <p className="text-sm font-semibold">{formatCurrency(s.revenue)}</p>
              <p className="text-[11px] text-brand-300">{s.count} randevu</p>
            </div>
          ))}
        </div>
      )}

      {data?.cached && (
        <p className="mt-3 text-[11px] text-brand-300">Önbellekten yüklendi</p>
      )}
    </div>
  );
}
