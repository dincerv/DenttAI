'use client';
import { Calendar, CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import { formatPercent } from '@/lib/utils';
import { StatCardSkeleton } from '@/components/ui/Skeleton';
import type { AppointmentStatsResponse } from '@/types';

interface Props {
  data: AppointmentStatsResponse | null;
  loading: boolean;
}

export function StatsCards({ data, loading }: Props) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[0, 1, 2, 3].map((i) => <StatCardSkeleton key={i} />)}
      </div>
    );
  }

  const cards = [
    {
      label: 'Toplam Randevu',
      value: data?.total ?? 0,
      sub:   `${data?.upcoming ?? 0} aktif`,
      icon:  Calendar,
      color: 'text-brand-600',
      bg:    'bg-brand-50',
    },
    {
      label: 'Tamamlanan',
      value: data?.completed ?? 0,
      sub:   formatPercent(data?.completion_rate_pct),
      icon:  CheckCircle,
      color: 'text-green-600',
      bg:    'bg-green-50',
    },
    {
      label: 'İptal Edilen',
      value: data?.cancelled ?? 0,
      sub:   formatPercent(data?.cancel_rate_pct),
      icon:  XCircle,
      color: 'text-red-600',
      bg:    'bg-red-50',
    },
    {
      label: 'Gelmedi (No-Show)',
      value: data?.no_show ?? 0,
      sub:   formatPercent(data?.no_show_rate_pct),
      icon:  AlertCircle,
      color: 'text-orange-600',
      bg:    'bg-orange-50',
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {cards.map(({ label, value, sub, icon: Icon, color, bg }) => (
        <div
          key={label}
          className="group rounded-xl border border-slate-200 bg-white p-3.5 shadow-sm transition-shadow hover:shadow"
        >
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="truncate text-[11px] font-semibold uppercase tracking-wide text-slate-500">{label}</p>
            <div className={`inline-flex rounded-md p-1.5 ${bg}`}>
              <Icon className={`h-4 w-4 ${color}`} />
            </div>
          </div>
          <p className="text-2xl font-bold leading-none text-slate-800">{value}</p>
          <p className="mt-1 text-[11px] text-slate-400">{sub}</p>
        </div>
      ))}
    </div>
  );
}
