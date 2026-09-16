'use client';
import { formatPercent } from '@/lib/utils';
import { TableRowSkeleton } from '@/components/ui/Skeleton';
import { Badge } from '@/components/ui/Badge';
import type { DoctorPerformanceResponse } from '@/types';

interface Props {
  data: DoctorPerformanceResponse | null;
  loading: boolean;
}

export function DoctorPerformanceTable({ data, loading }: Props) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 px-6 py-4">
        <h2 className="text-sm font-semibold text-slate-700">Hekim Performans Karnesi</h2>
        <p className="text-xs text-slate-400">Bu aya ait veriler — yüksek completion rate üstte</p>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead>
            <tr className="bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
              <th className="px-4 py-3 text-left">Hekim</th>
              <th className="px-4 py-3 text-left">Branş</th>
              <th className="px-4 py-3 text-right">Toplam</th>
              <th className="px-4 py-3 text-right">Tamamlama</th>
              <th className="px-4 py-3 text-right">İptal</th>
              <th className="px-4 py-3 text-right">Sadık Hasta</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              Array.from({ length: 4 }).map((_, i) => <TableRowSkeleton key={i} cols={6} />)
            ) : data?.doctors.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-10 text-center text-sm text-slate-400">
                  Veri bulunamadı
                </td>
              </tr>
            ) : (
              data?.doctors.map((d) => (
                <tr key={d.doctor_id} className="hover:bg-slate-50 transition-colors">
                  <td className="px-4 py-3 font-medium text-slate-800 text-sm">
                    {d.doctor_name}
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-500">{d.specialty ?? '—'}</td>
                  <td className="px-4 py-3 text-right text-sm">{d.total}</td>
                  <td className="px-4 py-3 text-right">
                    <Badge
                      variant={
                        (d.completion_rate_pct ?? 0) >= 75 ? 'green' :
                        (d.completion_rate_pct ?? 0) >= 50 ? 'yellow' : 'red'
                      }
                    >
                      {formatPercent(d.completion_rate_pct)}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span className={`text-sm ${(d.cancel_rate_pct ?? 0) > 20 ? 'text-red-600 font-semibold' : 'text-slate-600'}`}>
                      {formatPercent(d.cancel_rate_pct)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right text-sm">{d.loyal_patient_count}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
