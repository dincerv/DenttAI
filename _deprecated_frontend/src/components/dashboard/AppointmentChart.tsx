'use client';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { Skeleton } from '@/components/ui/Skeleton';
import type { AppointmentStatsResponse } from '@/types';

interface Props {
  data: AppointmentStatsResponse | null;
  loading: boolean;
}

export function AppointmentChart({ data, loading }: Props) {
  if (loading) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <Skeleton className="mb-3 h-4 w-48" />
        <Skeleton className="h-44 w-full" />
      </div>
    );
  }

  const chartData = data?.by_specialty.map((s) => ({
    name: s.specialty ?? 'Diğer',
    Tamamlanan: s.completed,
    İptal: s.cancelled,
    NoShow: s.no_show,
    total: s.completed + s.cancelled + s.no_show,
  }))
    .sort((a, b) => b.total - a.total)
    .slice(0, 8) ?? [];

  const chartHeight = Math.max(190, chartData.length * 36);

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-slate-700">Branş Bazlı Randevu Dağılımı</h2>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600">
          {chartData.length} branş
        </span>
      </div>
      {chartData.length === 0 ? (
        <p className="py-8 text-center text-sm text-slate-400">Veri bulunamadı</p>
      ) : (
        <ResponsiveContainer width="100%" height={chartHeight}>
          <BarChart layout="vertical" data={chartData} margin={{ top: 0, right: 12, left: 4, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
            <XAxis
              type="number"
              tick={{ fontSize: 11, fill: '#64748b' }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              type="category"
              dataKey="name"
              width={100}
              tick={{ fontSize: 11, fill: '#64748b' }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: 12 }}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="Tamamlanan" stackId="a" fill="#16a34a" radius={[0, 0, 0, 0]} />
            <Bar dataKey="İptal" stackId="a" fill="#ef4444" radius={[0, 0, 0, 0]} />
            <Bar dataKey="NoShow" stackId="a" fill="#f59e0b" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
