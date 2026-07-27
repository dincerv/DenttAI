'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { isImpersonating } from '@/lib/auth';
import { useAuth } from '@/hooks/useAuth';
import { useDashboard } from '@/hooks/useDashboard';
import { useTreatments, useTreatmentsByDoctor, type GroupBy } from '@/hooks/useTreatments';
import { RevenueCard } from '@/components/dashboard/RevenueCard';
import { StatsCards } from '@/components/dashboard/StatsCards';
import { AppointmentChart } from '@/components/dashboard/AppointmentChart';
import { DoctorPerformanceTable } from '@/components/dashboard/DoctorPerformanceTable';
import { Skeleton } from '@/components/ui/Skeleton';
import { useDoctorDashboard } from '@/hooks/useDoctorDashboard';
import {
  Clock, AlertTriangle, Stethoscope, Syringe, Smile,
  Activity, Package, BarChart2, Filter, UserX, TrendingUp,
  LayoutList, PieChart as PieChartIcon, BarChart as BarChartIcon,
  LayoutGrid, Radar as RadarIcon, Info,
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, RadarChart, Radar, PolarGrid,
  PolarAngleAxis, PolarRadiusAxis,
} from 'recharts';
import type { ExpiringCyclesResponse, TreatmentTotals, TreatmentCountsResponse, DoctorTreatmentRow } from '@/types';
import { useInventory } from '@/hooks/useInventory';
import { BatchTooltip } from '@/components/dashboard/BatchTooltip';
import { DoctorTreatmentLog, AllDoctorsTreatmentLog } from '@/components/dashboard/TreatmentLog';
import { ClinicAIChat } from '@/components/dashboard/ClinicAIChat';
import { OwnerInsightsPanel } from '@/components/dashboard/OwnerInsightsPanel';

// ── Medical Blue renk konstanları ────────────────────────────────────────
const TREATMENT_CARDS = [
  { key: 'dolgu',     label: 'Dolgu',      icon: '🦷', color: 'bg-blue-600',    text: 'text-white' },
  { key: 'kanal',     label: 'Kanal',      icon: '🔬', color: 'bg-blue-700',    text: 'text-white' },
  { key: 'implant',   label: 'İmplant',    icon: '⚕️', color: 'bg-blue-800',    text: 'text-white' },
  { key: 'kron',      label: 'Kron',       icon: '👑', color: 'bg-indigo-600',  text: 'text-white' },
  { key: 'cekim',     label: 'Çekim',      icon: '🔧', color: 'bg-blue-500',    text: 'text-white' },
  { key: 'protez',    label: 'Protez',     icon: '🦴', color: 'bg-cyan-600',    text: 'text-white' },
  { key: 'ortodonti', label: 'Ortodonti',  icon: '📐', color: 'bg-sky-600',     text: 'text-white' },
  { key: 'temizlik',  label: 'Temizlik',   icon: '✨', color: 'bg-teal-600',    text: 'text-white' },
] as const;

const FILTER_OPTIONS: { label: string; value: GroupBy }[] = [
  { label: 'Günlük',   value: 'day' },
  { label: 'Haftalık', value: 'week' },
  { label: 'Aylık',    value: 'month' },
  { label: 'Yıllık',   value: 'year' },
];

// ── Tedavi Sayaç Kartları ─────────────────────────────────────────────────
function TreatmentCountCards({
  totals,
  loading,
}: {
  totals: TreatmentTotals | null;
  loading: boolean;
}) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
      {TREATMENT_CARDS.map(({ key, label, icon, color, text }) => (
        <div
          key={key}
          className={`${color} ${text} rounded-xl p-4 flex flex-col items-center justify-center shadow-md`}
        >
          <span className="text-2xl mb-1">{icon}</span>
          {loading ? (
            <div className="h-7 w-10 rounded bg-white/30 animate-pulse" />
          ) : (
            <span className="text-2xl font-bold leading-none">
              {totals ? (totals as unknown as Record<string, number>)[key] ?? 0 : 0}
            </span>
          )}
          <span className="mt-1 text-xs font-medium opacity-90">{label}</span>
        </div>
      ))}
    </div>
  );
}

// ── Dönem Filtre Butonları ────────────────────────────────────────────────
function PeriodFilter({
  value,
  onChange,
}: {
  value: GroupBy;
  onChange: (v: GroupBy) => void;
}) {
  return (
    <div className="flex gap-1 rounded-xl bg-slate-100 p-1">
      {FILTER_OPTIONS.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
            value === opt.value
              ? 'bg-blue-600 text-white shadow-sm'
              : 'text-slate-500 hover:text-slate-700'
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

// ── Süresi Dolmak Üzere Kartı ─────────────────────────────────────────────
function ExpiringCyclesCard({ data }: { data: ExpiringCyclesResponse }) {
  if (data.items.length === 0) return null;
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 shadow-sm overflow-hidden">
      <div className="flex items-center gap-2 border-b border-red-200 bg-red-100/60 px-5 py-3">
        <Clock className="h-4 w-4 text-red-600" />
        <h3 className="text-sm font-semibold text-red-700">Süresi Dolmak Üzere</h3>
        <span className="ml-auto rounded-full bg-red-600 px-2 py-0.5 text-xs font-bold text-white">
          {data.items.length}
        </span>
      </div>
      <div className="divide-y divide-red-100">
        {data.items.map((item) => {
          const pct = item.lifespan_used_pct != null ? Math.round(item.lifespan_used_pct) : null;
          return (
            <div key={item.id} className="flex items-center gap-3 px-5 py-2.5">
              {item.shelf_code && (
                <span className="shrink-0 font-mono text-xs font-bold text-red-700 bg-white border border-red-200 px-2 py-0.5 rounded">
                  {item.shelf_code}
                </span>
              )}
              <span className="flex-1 text-sm font-medium text-slate-800 truncate">{item.name}</span>
              {pct != null && (
                <div className="flex items-center gap-2">
                  <div className="w-20 h-1.5 rounded-full bg-red-200 overflow-hidden">
                    <div className="h-full rounded-full bg-red-500" style={{ width: `${Math.min(pct, 100)}%` }} />
                  </div>
                  <span className="text-xs font-bold text-red-600 w-8 text-right">%{pct}</span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Assistant Dashboard ───────────────────────────────────────────────────
function AssistantDashboard({ expiring }: { expiring: ExpiringCyclesResponse | null }) {
  const router = useRouter();
  return (
    <div className="space-y-6">
      {/* Asistan bilgi başlığı */}
      <div className="rounded-xl border border-blue-200 bg-blue-50 px-6 py-5">
        <div className="flex items-center gap-3 mb-1">
          <Package className="h-6 w-6 text-blue-600" />
          <h2 className="text-lg font-bold text-blue-900">Malzeme & Envanter</h2>
        </div>
        <p className="text-sm text-blue-700">
          Kritik stok durumları ve QR malzeme takibi aşağıda gösterilmektedir.
        </p>
      </div>

      {expiring && <ExpiringCyclesCard data={expiring} />}

      <div
        className="cursor-pointer rounded-xl border-2 border-dashed border-blue-300 p-8 flex flex-col items-center gap-3 hover:bg-blue-50 transition-colors"
        onClick={() => router.push('/dashboard/inventory')}
      >
        <Package className="h-10 w-10 text-blue-400" />
        <p className="text-sm font-semibold text-blue-600">Tam Envanter Sayfasına Git →</p>
      </div>
    </div>
  );
}

// ── Tedavi Performans Bileşeni — 5 görünüm modu ──────────────────────────
const TREATMENT_ROWS = [
  { key: 'dolgu',     label: 'Dolgu',     icon: '🦷', bar: 'bg-blue-500',    hex: '#3b82f6' },
  { key: 'kanal',     label: 'Kanal',     icon: '🔬', bar: 'bg-blue-700',    hex: '#1d4ed8' },
  { key: 'implant',   label: 'İmplant',   icon: '⚕️', bar: 'bg-indigo-500',  hex: '#6366f1' },
  { key: 'kron',      label: 'Kron',      icon: '👑', bar: 'bg-indigo-700',  hex: '#4338ca' },
  { key: 'cekim',     label: 'Çekim',     icon: '🔧', bar: 'bg-cyan-500',    hex: '#06b6d4' },
  { key: 'protez',    label: 'Protez',    icon: '🦴', bar: 'bg-cyan-700',    hex: '#0e7490' },
  { key: 'ortodonti', label: 'Ortodonti', icon: '📐', bar: 'bg-sky-500',     hex: '#0ea5e9' },
  { key: 'temizlik',  label: 'Temizlik',  icon: '✨', bar: 'bg-teal-500',    hex: '#14b8a6' },
] as const;

type ViewMode = 'table' | 'bar' | 'column' | 'pie' | 'radar';

const VIEW_OPTIONS: { mode: ViewMode; icon: React.ReactNode; label: string }[] = [
  { mode: 'table',  icon: <LayoutList  className="h-4 w-4" />, label: 'Tablo' },
  { mode: 'bar',    icon: <BarChartIcon className="h-4 w-4" />, label: 'Yatay Çubuk' },
  { mode: 'column', icon: <BarChart2   className="h-4 w-4" />, label: 'Sütun' },
  { mode: 'pie',    icon: <PieChartIcon className="h-4 w-4" />, label: 'Pasta' },
  { mode: 'radar',  icon: <RadarIcon   className="h-4 w-4" />, label: 'Radar' },
];

function TreatmentPerformanceTable({
  data,
  loading,
}: {
  data: TreatmentCountsResponse | null;
  loading: boolean;
}) {
  const [viewMode, setViewMode] = useState<ViewMode>('table');

  if (loading) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <div className="border-b border-slate-100 px-5 py-3 flex gap-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-8 w-20 rounded-lg bg-slate-100 animate-pulse" />
          ))}
        </div>
        <div className="p-6 space-y-3">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="flex items-center gap-4">
              <div className="h-4 w-24 rounded bg-slate-100 animate-pulse" />
              <div className="flex-1 h-2.5 rounded-full bg-slate-100 animate-pulse" />
              <div className="h-4 w-8 rounded bg-slate-100 animate-pulse" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  const totals = data?.totals;
  if (!totals) return null;

  const rows = [...TREATMENT_ROWS]
    .map((r) => ({ ...r, count: (totals as unknown as Record<string, number>)[r.key] ?? 0 }))
    .sort((a, b) => b.count - a.count);

  const activeRows = rows.filter((r) => r.count > 0);
  const total = totals.total_completed;
  const max   = Math.max(...rows.map((r) => r.count), 1);
  const trend = data?.trend ?? [];

  // Başlık satırı — görünüm seçici
  const Header = () => (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 bg-slate-50 px-5 py-3">
      <div className="flex items-center gap-2">
        <TrendingUp className="h-4 w-4 text-blue-600" />
        <span className="text-sm font-semibold text-slate-700">
          Tedavi Dağılımım
          {data?.period_start && (
            <span className="ml-2 font-normal text-slate-400 text-xs">
              {new Date(data.period_start).toLocaleDateString('tr-TR')}
              {' – '}
              {new Date(data.period_end).toLocaleDateString('tr-TR')}
            </span>
          )}
        </span>
        <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-semibold text-blue-700">
          {total} toplam
        </span>
      </div>
      {/* Görünüm seçici */}
      <div className="flex gap-1 rounded-xl bg-slate-100 p-1">
        {VIEW_OPTIONS.map(({ mode, icon, label }) => (
          <button
            key={mode}
            onClick={() => setViewMode(mode)}
            title={label}
            className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-all ${
              viewMode === mode
                ? 'bg-white text-blue-700 shadow-sm'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {icon}
            <span className="hidden sm:inline">{label}</span>
          </button>
        ))}
      </div>
    </div>
  );

  // ── Mod 1: Tablo ──
  const TableView = () => (
    <table className="min-w-full">
      <thead>
        <tr className="border-b border-slate-100 bg-slate-50/50">
          <th className="px-5 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-400 w-32">Tedavi</th>
          <th className="px-5 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-400">Dağılım</th>
          <th className="px-5 py-2.5 text-right text-xs font-semibold uppercase tracking-wide text-slate-400 w-16">Adet</th>
          <th className="px-5 py-2.5 text-right text-xs font-semibold uppercase tracking-wide text-slate-400 w-16">Oran</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-50">
        {rows.map((r, idx) => {
          const pct  = total > 0 ? Math.round((r.count / total) * 100) : 0;
          const barW = max > 0 ? Math.round((r.count / max) * 100) : 0;
          return (
            <tr key={r.key} className={`transition-colors ${r.count > 0 ? 'hover:bg-slate-50' : 'opacity-35'}`}>
              <td className="px-5 py-3">
                <div className="flex items-center gap-2">
                  {idx === 0 && r.count > 0 && (
                    <span className="flex h-4 w-4 items-center justify-center rounded-full bg-amber-400 text-xs font-bold text-white">1</span>
                  )}
                  <span className="text-base">{r.icon}</span>
                  <span className="text-sm font-medium text-slate-800">{r.label}</span>
                </div>
              </td>
              <td className="px-5 py-3">
                <div className="h-2.5 w-full rounded-full bg-slate-100 overflow-hidden">
                  <div className={`h-full rounded-full transition-all duration-500 ${r.bar}`} style={{ width: `${barW}%` }} />
                </div>
              </td>
              <td className="px-5 py-3 text-right text-sm font-bold text-slate-800">{r.count}</td>
              <td className="px-5 py-3 text-right">
                <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                  pct >= 30 ? 'bg-blue-100 text-blue-700' :
                  pct >= 15 ? 'bg-indigo-100 text-indigo-700' :
                  pct > 0   ? 'bg-slate-100 text-slate-500' : 'text-slate-300'
                }`}>{pct > 0 ? `%${pct}` : '—'}</span>
              </td>
            </tr>
          );
        })}
      </tbody>
      {total > 0 && (
        <tfoot>
          <tr className="border-t-2 border-slate-200 bg-slate-50">
            <td colSpan={2} className="px-5 py-2.5 text-xs font-semibold uppercase tracking-wide text-slate-500">Toplam</td>
            <td className="px-5 py-2.5 text-right text-sm font-bold text-blue-700">{total}</td>
            <td className="px-5 py-2.5 text-right text-xs font-semibold text-slate-500">%100</td>
          </tr>
        </tfoot>
      )}
    </table>
  );

  // ── Mod 2: Yatay çubuk grafik ──
  const BarView = () => (
    <div className="p-5">
      <ResponsiveContainer width="100%" height={Math.max(activeRows.length * 44, 200)}>
        <BarChart
          layout="vertical"
          data={rows.filter(r => r.count > 0).map(r => ({ name: `${r.icon} ${r.label}`, value: r.count, fill: r.hex }))}
          margin={{ top: 0, right: 32, left: 16, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
          <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
          <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 12, fill: '#475569' }} axisLine={false} tickLine={false} />
          <Tooltip
            formatter={(v: number) => [`${v} adet`, 'Tamamlanan']}
            contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: 12 }}
          />
          <Bar dataKey="value" radius={[0, 4, 4, 0]} label={{ position: 'right', fontSize: 11, fill: '#475569' }}>
            {rows.filter(r => r.count > 0).map((r) => (
              <Cell key={r.key} fill={r.hex} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );

  // ── Mod 3: Dikey sütun grafik ──
  const ColumnView = () => (
    <div className="p-5">
      <ResponsiveContainer width="100%" height={260}>
        <BarChart
          data={rows.map(r => ({ name: r.label, value: r.count, icon: r.icon, fill: r.hex }))}
          margin={{ top: 8, right: 8, left: 0, bottom: 8 }}
        >
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
          <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#475569' }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
          <Tooltip
            formatter={(v: number) => [`${v} adet`, 'Tamamlanan']}
            contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: 12 }}
          />
          <Bar dataKey="value" radius={[4, 4, 0, 0]} label={{ position: 'top', fontSize: 11, fill: '#475569' }}>
            {rows.map((r) => <Cell key={r.key} fill={r.hex} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );

  // ── Mod 4: Pasta (Donut) grafik ──
  const RADIAN = Math.PI / 180;
  const renderCustomLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent }: {
    cx: number; cy: number; midAngle: number; innerRadius: number; outerRadius: number; percent: number;
  }) => {
    if (percent < 0.05) return null;
    const r  = innerRadius + (outerRadius - innerRadius) * 0.5;
    const x  = cx + r * Math.cos(-midAngle * RADIAN);
    const y  = cy + r * Math.sin(-midAngle * RADIAN);
    return (
      <text x={x} y={y} fill="white" textAnchor="middle" dominantBaseline="central" fontSize={11} fontWeight="bold">
        {`%${Math.round(percent * 100)}`}
      </text>
    );
  };

  const PieView = () => (
    <div className="p-5">
      {activeRows.length === 0 ? (
        <p className="py-10 text-center text-sm text-slate-400">Veri yok</p>
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <PieChart>
            <Pie
              data={activeRows.map(r => ({ name: `${r.icon} ${r.label}`, value: r.count, fill: r.hex }))}
              cx="50%" cy="50%"
              innerRadius={60} outerRadius={110}
              paddingAngle={2}
              dataKey="value"
              labelLine={false}
              label={renderCustomLabel}
            >
              {activeRows.map((r) => <Cell key={r.key} fill={r.hex} />)}
            </Pie>
            <Tooltip
              formatter={(v: number, name: string) => [`${v} adet`, name]}
              contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: 12 }}
            />
            <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
          </PieChart>
        </ResponsiveContainer>
      )}
    </div>
  );

  // ── Mod 5: Radar grafik ──
  const RadarView = () => (
    <div className="p-5">
      {activeRows.length < 3 ? (
        <p className="py-10 text-center text-sm text-slate-400">Radar için en az 3 tedavi türü gerekli</p>
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <RadarChart data={rows.map(r => ({ subject: `${r.icon} ${r.label}`, A: r.count, fullMark: max }))}>
            <PolarGrid stroke="#e2e8f0" />
            <PolarAngleAxis dataKey="subject" tick={{ fontSize: 11, fill: '#475569' }} />
            <PolarRadiusAxis angle={90} domain={[0, max]} tick={{ fontSize: 10, fill: '#94a3b8' }} />
            <Radar name="Tedavi" dataKey="A" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.25} strokeWidth={2} />
            <Tooltip
              formatter={(v: number) => [`${v} adet`, 'Tamamlanan']}
              contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: 12 }}
            />
          </RadarChart>
        </ResponsiveContainer>
      )}
    </div>
  );

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <Header />
        {total === 0 && viewMode !== 'radar' ? (
          <p className="py-10 text-center text-sm text-slate-400">Bu dönemde tamamlanan tedavi kaydı bulunmuyor.</p>
        ) : (
          <>
            {viewMode === 'table'  && <TableView />}
            {viewMode === 'bar'    && <BarView />}
            {viewMode === 'column' && <ColumnView />}
            {viewMode === 'pie'    && <PieView />}
            {viewMode === 'radar'  && <RadarView />}
          </>
        )}
      </div>

      {/* Dönem trend tablosu */}
      {trend.length > 1 && (
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
          <div className="border-b border-slate-100 bg-slate-50 px-5 py-3">
            <h3 className="text-sm font-semibold text-slate-700">Dönem Trendi</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-xs">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50/50">
                  <th className="px-4 py-2 text-left font-semibold uppercase tracking-wide text-slate-400">Dönem</th>
                  {TREATMENT_ROWS.map((r) => (
                    <th key={r.key} className="px-3 py-2 text-right font-semibold uppercase tracking-wide text-slate-400" title={r.label}>{r.icon}</th>
                  ))}
                  <th className="px-3 py-2 text-right font-semibold uppercase tracking-wide text-slate-500">Top.</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {trend.slice().reverse().map((p) => (
                  <tr key={p.period} className="hover:bg-slate-50">
                    <td className="px-4 py-2 font-medium text-slate-700 whitespace-nowrap">{p.period}</td>
                    {TREATMENT_ROWS.map((r) => (
                      <td key={r.key} className="px-3 py-2 text-right text-slate-600">
                        {(p as unknown as Record<string, number>)[r.key] || '—'}
                      </td>
                    ))}
                    <td className="px-3 py-2 text-right font-bold text-blue-700">{p.total_completed}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Hekim Bazlı Tedavi Tablosu (Sahip görünümü) ─────────────────────────
const TREAT_COLS: { key: keyof DoctorTreatmentRow; label: string; icon: string; hex: string }[] = [
  { key: 'dolgu',     label: 'Dolgu',      icon: '🦷', hex: '#3b82f6' },
  { key: 'kanal',     label: 'Kanal',      icon: '🔬', hex: '#1d4ed8' },
  { key: 'implant',   label: 'İmplant',    icon: '⚕️', hex: '#6366f1' },
  { key: 'kron',      label: 'Kron',       icon: '👑', hex: '#4338ca' },
  { key: 'cekim',     label: 'Çekim',      icon: '🔧', hex: '#06b6d4' },
  { key: 'protez',    label: 'Protez',     icon: '🦴', hex: '#0e7490' },
  { key: 'ortodonti', label: 'Ortodonti',  icon: '📐', hex: '#0ea5e9' },
  { key: 'temizlik',  label: 'Temizlik',   icon: '✨', hex: '#14b8a6' },
];

// Her hekim için ayırt edici renk paleti
const DOC_COLORS = [
  '#3b82f6', '#f59e0b', '#10b981', '#ef4444',
  '#8b5cf6', '#06b6d4', '#f97316', '#ec4899',
];

type DoctorViewMode = 'heat' | 'grouped' | 'stacked' | 'pie' | 'radar';

const DOCTOR_VIEW_OPTIONS: { mode: DoctorViewMode; icon: React.ReactNode; label: string }[] = [
  { mode: 'heat',    icon: <LayoutList   className="h-4 w-4" />, label: 'Tablo' },
  { mode: 'grouped', icon: <BarChart2    className="h-4 w-4" />, label: 'Gruplu' },
  { mode: 'stacked', icon: <BarChartIcon className="h-4 w-4" />, label: 'Yığılı' },
  { mode: 'pie',     icon: <PieChartIcon className="h-4 w-4" />, label: 'Pasta' },
  { mode: 'radar',   icon: <RadarIcon    className="h-4 w-4" />, label: 'Radar' },
];

function DoctorTreatmentsTable({
  doctors,
  loading,
}: {
  doctors: DoctorTreatmentRow[] | undefined;
  loading: boolean;
}) {
  const [viewMode, setViewMode] = useState<DoctorViewMode>('heat');

  if (loading) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <div className="border-b border-slate-100 bg-slate-50 px-5 py-3 flex gap-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-8 w-20 rounded-lg bg-slate-100 animate-pulse" />
          ))}
        </div>
        {[...Array(3)].map((_, i) => (
          <div key={i} className="flex gap-4 px-5 py-3 border-b border-slate-50">
            <div className="h-4 w-32 rounded bg-slate-100 animate-pulse" />
            {[...Array(8)].map((_, j) => (
              <div key={j} className="h-4 w-10 rounded bg-slate-100 animate-pulse" />
            ))}
          </div>
        ))}
      </div>
    );
  }

  if (!doctors || doctors.length === 0) return null;

  const totalCompleted = doctors.reduce((s, d) => s + d.total_completed, 0);

  // Sütun maxları (heatmap renk yoğunluğu)
  const colMax: Record<string, number> = {};
  TREAT_COLS.forEach(({ key }) => {
    colMax[key as string] = Math.max(...doctors.map((d) => (d[key] as number) ?? 0), 1);
  });

  // Başlık + görünüm seçici
  const Header = () => (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 bg-slate-50 px-5 py-3">
      <div className="flex items-center gap-2">
        <Activity className="h-4 w-4 text-blue-600" />
        <span className="text-sm font-semibold text-slate-700">Hekim Bazlı Tedavi Dağılımı</span>
        <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-semibold text-blue-700">
          {doctors.length} hekim · {totalCompleted} tedavi
        </span>
      </div>
      <div className="flex gap-1 rounded-xl bg-slate-100 p-1">
        {DOCTOR_VIEW_OPTIONS.map(({ mode, icon, label }) => (
          <button
            key={mode}
            onClick={() => setViewMode(mode)}
            title={label}
            className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-all ${
              viewMode === mode
                ? 'bg-white text-blue-700 shadow-sm'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {icon}
            <span className="hidden sm:inline">{label}</span>
          </button>
        ))}
      </div>
    </div>
  );

  // ── Mod 1: Isı Haritası Tablosu ──
  const HeatmapView = () => (
    <div className="overflow-x-auto">
      <table className="min-w-full">
        <thead>
          <tr className="border-b border-slate-100 bg-slate-50/60">
            <th className="sticky left-0 z-10 bg-slate-50/90 px-5 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-400 min-w-[160px]">Hekim</th>
            {TREAT_COLS.map((c) => (
              <th key={c.key as string} className="px-3 py-2.5 text-center text-sm" title={c.label}>
                {c.icon}
              </th>
            ))}
            <th className="px-4 py-2.5 text-right text-xs font-semibold uppercase tracking-wide text-slate-400">Toplam</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-50">
          {doctors.map((doc) => (
            <tr key={doc.doctor_id} className="hover:bg-blue-50/30 transition-colors">
              <td className="sticky left-0 z-10 bg-white px-5 py-3">
                <div className="font-medium text-slate-800 text-sm">{doc.doctor_name}</div>
                {doc.specialty && <div className="text-xs text-slate-400">{doc.specialty}</div>}
              </td>
              {TREAT_COLS.map(({ key }) => {
                const val = (doc[key] as number) ?? 0;
                const intensity = colMax[key as string] > 0 ? val / colMax[key as string] : 0;
                const bg =
                  intensity >= 0.75 ? 'bg-blue-600 text-white' :
                  intensity >= 0.45 ? 'bg-blue-300 text-blue-900' :
                  intensity > 0     ? 'bg-blue-100 text-blue-700' :
                                      'text-slate-300';
                return (
                  <td key={key as string} className="px-3 py-3 text-center">
                    <span className={`inline-flex h-7 w-9 items-center justify-center rounded-md text-xs font-bold ${bg}`}>
                      {val > 0 ? val : '—'}
                    </span>
                  </td>
                );
              })}
              <td className="px-4 py-3 text-right text-sm font-bold text-blue-700">{doc.total_completed}</td>
            </tr>
          ))}
        </tbody>
        {doctors.length > 1 && (
          <tfoot>
            <tr className="border-t-2 border-slate-200 bg-slate-50">
              <td className="sticky left-0 bg-slate-50 px-5 py-2.5 text-xs font-semibold uppercase tracking-wide text-slate-500">Klinik Toplamı</td>
              {TREAT_COLS.map(({ key }) => {
                const total = doctors.reduce((s, d) => s + ((d[key] as number) ?? 0), 0);
                return (
                  <td key={key as string} className="px-3 py-2.5 text-center text-xs font-bold text-slate-600">
                    {total > 0 ? total : '—'}
                  </td>
                );
              })}
              <td className="px-4 py-2.5 text-right text-sm font-bold text-blue-700">{totalCompleted}</td>
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  );

  // ── Mod 2: Gruplu Sütun — tedavi türü bazında her hekim ayrı bar ──
  const GroupedView = () => {
    const chartData = TREAT_COLS.map(({ key, label, icon }) => {
      const entry: Record<string, string | number> = { name: `${icon} ${label}` };
      doctors.forEach((doc) => {
        entry[doc.doctor_name] = (doc[key] as number) ?? 0;
      });
      return entry;
    });
    return (
      <div className="p-5">
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
            <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#475569' }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: 12 }} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            {doctors.map((doc, i) => (
              <Bar key={doc.doctor_id} dataKey={doc.doctor_name} fill={DOC_COLORS[i % DOC_COLORS.length]} radius={[3, 3, 0, 0]} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  };

  // ── Mod 3: Yatay Yığılı — hekim bazında tedavi türleri yığılı ──
  const StackedView = () => {
    const chartData = doctors.map((doc) => {
      const entry: Record<string, string | number> = { name: doc.doctor_name };
      TREAT_COLS.forEach(({ key, label }) => {
        entry[label] = (doc[key] as number) ?? 0;
      });
      return entry;
    });
    return (
      <div className="p-5">
        <ResponsiveContainer width="100%" height={Math.max(doctors.length * 52, 180)}>
          <BarChart layout="vertical" data={chartData} margin={{ top: 0, right: 40, left: 8, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
            <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
            <YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 12, fill: '#475569' }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: 12 }} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {TREAT_COLS.map(({ label, hex }) => (
              <Bar key={label} dataKey={label} stackId="a" fill={hex} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  };

  // ── Mod 4: Pasta — toplam tedavi sayısına göre hekim payları ──
  const RADIAN = Math.PI / 180;
  const renderPieLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent }: {
    cx: number; cy: number; midAngle: number; innerRadius: number; outerRadius: number; percent: number;
  }) => {
    if (percent < 0.05) return null;
    const r = innerRadius + (outerRadius - innerRadius) * 0.5;
    const x = cx + r * Math.cos(-midAngle * RADIAN);
    const y = cy + r * Math.sin(-midAngle * RADIAN);
    return (
      <text x={x} y={y} fill="white" textAnchor="middle" dominantBaseline="central" fontSize={11} fontWeight="bold">
        {`%${Math.round(percent * 100)}`}
      </text>
    );
  };
  const PieView = () => (
    <div className="p-5">
      {totalCompleted === 0 ? (
        <p className="py-10 text-center text-sm text-slate-400">Veri yok</p>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <PieChart>
            <Pie
              data={doctors.filter((d) => d.total_completed > 0).map((doc, i) => ({
                name: doc.doctor_name,
                value: doc.total_completed,
                fill: DOC_COLORS[i % DOC_COLORS.length],
              }))}
              cx="50%" cy="50%"
              innerRadius={65} outerRadius={115}
              paddingAngle={2}
              dataKey="value"
              labelLine={false}
              label={renderPieLabel}
            >
              {doctors.filter((d) => d.total_completed > 0).map((doc, i) => (
                <Cell key={doc.doctor_id} fill={DOC_COLORS[i % DOC_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              formatter={(v: number, name: string) => [`${v} tedavi`, name]}
              contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: 12 }}
            />
            <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
          </PieChart>
        </ResponsiveContainer>
      )}
    </div>
  );

  // ── Mod 5: Radar — tedavi türü bazında hekim karşılaştırması ──
  const RadarView = () => {
    const maxVal = Math.max(...TREAT_COLS.flatMap(({ key }) => doctors.map((d) => (d[key] as number) ?? 0)), 1);
    const radarData = TREAT_COLS.map(({ key, label, icon }) => {
      const entry: Record<string, string | number> = { subject: `${icon} ${label}`, fullMark: maxVal };
      doctors.forEach((doc) => { entry[doc.doctor_name] = (doc[key] as number) ?? 0; });
      return entry;
    });
    return (
      <div className="p-5">
        {TREAT_COLS.length < 3 ? (
          <p className="py-10 text-center text-sm text-slate-400">Radar için en az 3 tedavi türü gerekli</p>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="#e2e8f0" />
              <PolarAngleAxis dataKey="subject" tick={{ fontSize: 11, fill: '#475569' }} />
              <PolarRadiusAxis angle={90} domain={[0, maxVal]} tick={{ fontSize: 10, fill: '#94a3b8' }} />
              {doctors.map((doc, i) => (
                <Radar
                  key={doc.doctor_id}
                  name={doc.doctor_name}
                  dataKey={doc.doctor_name}
                  stroke={DOC_COLORS[i % DOC_COLORS.length]}
                  fill={DOC_COLORS[i % DOC_COLORS.length]}
                  fillOpacity={0.15}
                  strokeWidth={2}
                />
              ))}
              <Tooltip contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
            </RadarChart>
          </ResponsiveContainer>
        )}
      </div>
    );
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      <Header />
      {viewMode === 'heat'    && <HeatmapView />}
      {viewMode === 'grouped' && <GroupedView />}
      {viewMode === 'stacked' && <StackedView />}
      {viewMode === 'pie'     && <PieView />}
      {viewMode === 'radar'   && <RadarView />}
    </div>
  );
}

// ── Doctor Dashboard ──────────────────────────────────────────────────────
function DoctorDashboard({ fullName }: { fullName: string }) {
  const [groupBy, setGroupBy] = useState<GroupBy>('month');
  const { stats, treatData, loading, notLinked } = useDoctorDashboard(groupBy);

  if (notLinked) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border border-amber-200 bg-amber-50 py-16 text-center">
        <UserX className="h-12 w-12 text-amber-400 mb-4" />
        <h2 className="text-lg font-semibold text-amber-800">Doktor kaydı eşleştirilmemiş</h2>
        <p className="mt-2 text-sm text-amber-600 max-w-sm">
          Hesabınız henüz bir doktor kaydıyla ilişkilendirilmemiş. Lütfen klinik yöneticinizle iletişime geçin.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Başlık + filtre */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-blue-900">Performansım</h2>
          <p className="text-sm text-slate-500 mt-0.5">{fullName}</p>
        </div>
        <PeriodFilter value={groupBy} onChange={setGroupBy} />
      </div>

      {/* Tedavi sayaç kartları — sadece bu doktora ait */}
      <div>
        <p className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-3 flex items-center gap-1.5">
          <Activity className="h-3.5 w-3.5" /> Tedavi Sayaçlarım
        </p>
        <TreatmentCountCards totals={treatData?.totals ?? null} loading={loading} />
      </div>

      {/* Özet istatistikler */}
      {!loading && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { label: 'Toplam Tamamlanan', value: treatData?.totals.total_completed ?? 0, color: 'text-blue-700' },
            { label: 'Randevu (dönem)',   value: stats?.total ?? 0,               color: 'text-slate-700' },
            { label: 'Tamamlanma Oranı', value: stats?.completion_rate_pct ? `%${stats.completion_rate_pct}` : '—', color: 'text-green-700' },
            { label: 'İptal Oranı',       value: stats?.cancel_rate_pct ? `%${stats.cancel_rate_pct}` : '—',       color: 'text-red-600' },
          ].map(({ label, value, color }) => (
            <div key={label} className="rounded-xl border border-slate-200 bg-white px-3 py-3 shadow-sm">
              <p className="text-[11px] text-slate-500 mb-1">{label}</p>
              <p className={`text-xl font-bold leading-none ${color}`}>{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Tedavi performans tablosu */}
      <TreatmentPerformanceTable data={treatData} loading={loading} />

      {/* Tedavi kayıtlarım — doktorun girdiği notlar */}
      <DoctorTreatmentLog />
    </div>
  );
}

// ── Owner Dashboard ───────────────────────────────────────────────────────
// ── Envanter Batch Özet Kartı (Dashboard) ─────────────────────────────────
function InventorySummaryCard() {
  const { batchSummaries, loading } = useInventory();
  const router = useRouter();

  if (loading) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <div className="border-b border-slate-100 bg-slate-50 px-5 py-3 flex items-center gap-2">
          <Package className="h-4 w-4 text-blue-600" />
          <span className="text-sm font-semibold text-slate-700">Stok Durumu</span>
        </div>
        <div className="p-4 space-y-2">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-8 rounded-lg bg-slate-100 animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  const lowStock = batchSummaries.filter((s) => s.is_low_stock);
  const sktWarn = batchSummaries.filter((s) =>
    s.days_until_nearest_expiry != null && s.days_until_nearest_expiry >= 0 && s.days_until_nearest_expiry <= 30
  );
  const sktExpired = batchSummaries.filter((s) =>
    s.days_until_nearest_expiry != null && s.days_until_nearest_expiry < 0
  );
  const criticalItems = [...sktExpired, ...sktWarn, ...lowStock]
    .filter((v, i, a) => a.findIndex((x) => x.name === v.name) === i)
    .slice(0, 6);

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      <div className="border-b border-slate-100 bg-slate-50 px-5 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Package className="h-4 w-4 text-blue-600" />
          <span className="text-sm font-semibold text-slate-700">Stok Durumu</span>
          <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-semibold text-blue-700">
            {batchSummaries.length} ürün
          </span>
        </div>
        <div className="flex items-center gap-2">
          {lowStock.length > 0 && (
            <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700 animate-pulse">
              {lowStock.length} düşük
            </span>
          )}
          {sktWarn.length > 0 && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-700">
              {sktWarn.length} SKT yakın
            </span>
          )}
        </div>
      </div>

      {criticalItems.length > 0 ? (
        <div className="divide-y divide-slate-50">
          {criticalItems.map((s) => {
            const isExpired = s.days_until_nearest_expiry != null && s.days_until_nearest_expiry < 0;
            const isSktWarn = s.days_until_nearest_expiry != null && s.days_until_nearest_expiry >= 0 && s.days_until_nearest_expiry <= 30;
            return (
              <div key={s.name} className="flex items-center gap-3 px-5 py-2.5 hover:bg-slate-50 transition-colors">
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-medium text-slate-800 truncate block">{s.name}</span>
                  <span className="text-[10px] text-slate-400">{s.batches.length} parti</span>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <span className={`text-sm font-bold ${s.is_low_stock ? 'text-red-600' : 'text-slate-700'}`}>
                    {s.total_quantity}
                  </span>
                  <span className="text-xs text-slate-400">{s.unit}</span>
                  <BatchTooltip summary={s} />
                </div>
                {isExpired && (
                  <span className="shrink-0 rounded-full bg-red-100 px-1.5 py-0.5 text-[10px] font-bold text-red-700">SKT!</span>
                )}
                {!isExpired && isSktWarn && (
                  <span className="shrink-0 rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-700">{s.days_until_nearest_expiry}g</span>
                )}
                {s.is_low_stock && !isExpired && !isSktWarn && (
                  <AlertTriangle className="h-3.5 w-3.5 text-red-500 shrink-0" />
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="px-5 py-6 text-center text-sm text-slate-400">
          Tüm stoklar normal seviyede
        </div>
      )}

      <div
        className="border-t border-slate-100 bg-slate-50/50 px-5 py-2.5 text-center cursor-pointer hover:bg-blue-50 transition-colors"
        onClick={() => router.push('/dashboard/inventory')}
      >
        <span className="text-xs font-semibold text-blue-600">Tam Envanter →</span>
      </div>
    </div>
  );
}

function OwnerDashboard() {
  const [groupBy, setGroupBy] = useState<GroupBy>('month');
  const { revenue, stats, doctorPerf, expiring, newPatients, loading } = useDashboard();
  const { data: treatData, loading: treatLoading } = useTreatments(groupBy);
  const { data: byDoctorData, loading: byDoctorLoading } = useTreatmentsByDoctor(groupBy);

  return (
    <div className="space-y-4">
      {/* Başlık + filtre */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-blue-900">Klinik Genel Bakış</h2>
          <p className="text-sm text-slate-500 mt-0.5">Tüm hekimler & finansal özet</p>
        </div>
        <PeriodFilter value={groupBy} onChange={setGroupBy} />
      </div>

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-12">
        <div className="xl:col-span-7">
          {/* Hero — kurtarılan ciro */}
          <RevenueCard data={revenue} loading={loading} />
        </div>
        <div className="space-y-3 xl:col-span-5">
          {/* Stat kartları */}
          <StatsCards data={stats} loading={loading} />

          {/* Yeni Hasta Özetleri */}
          <div className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-sm">
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-widest text-slate-400">Hasta Tipi Dağılımı</p>
            <div className="grid grid-cols-2 gap-2">
          {[
            { label: 'Bugün', value: newPatients?.day ?? { new_count: 0, old_count: 0 } },
            { label: 'Bu Hafta', value: newPatients?.week ?? { new_count: 0, old_count: 0 } },
            { label: 'Bu Ay', value: newPatients?.month ?? { new_count: 0, old_count: 0 } },
            { label: 'Bu Yıl', value: newPatients?.year ?? { new_count: 0, old_count: 0 } },
          ].map((item) => (
            <div key={item.label} className="rounded-lg border border-blue-100 bg-blue-50/30 p-2.5">
              <p className="text-[11px] font-medium text-slate-500">{item.label}</p>
              <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-700">
                  Yeni: {item.value.new_count}
                </span>
                <span className="rounded-full bg-red-100 px-2 py-0.5 text-[11px] font-semibold text-red-700">
                  Eski: {item.value.old_count}
                </span>
              </div>
            </div>
          ))}
            </div>
          </div>
        </div>
      </div>

      {/* Tedavi sayaçları — klinik geneli */}
      <div>
        <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-widest text-slate-400">
          <BarChart2 className="h-3.5 w-3.5" /> Klinik Tedavi Sayaçları
        </p>
        <TreatmentCountCards totals={treatData?.totals ?? null} loading={treatLoading} />
      </div>

      {/* Süresi dolmak üzere */}
      {!loading && expiring && <ExpiringCyclesCard data={expiring} />}

      {/* Envanter batch özeti */}
      <InventorySummaryCard />

      {/* Hekim bazlı tedavi dağılımı */}
      <DoctorTreatmentsTable doctors={byDoctorData?.doctors} loading={byDoctorLoading} />

      {/* Grafik + Doktor tablo */}
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-12">
        <div className="xl:col-span-5">
          <AppointmentChart data={stats ?? null} loading={loading} />
        </div>
        <div className="xl:col-span-7">
          <DoctorPerformanceTable data={doctorPerf} loading={loading} />
        </div>
      </div>

      {/* AI Proaktif İçgörüler — klinik sahibi için */}
      <OwnerInsightsPanel />

      {/* Klinik sahibi / superadmin AI analiz asistanı */}
      <ClinicAIChat />

      {/* Hekim Tedavi Kayıtları — tüm doktorların günlükleri */}
      <AllDoctorsTreatmentLog />
    </div>
  );
}

// ── Ana Sayfa — Rol yönlendirmesi ─────────────────────────────────────────
export default function DashboardPage() {
  const router = useRouter();
  const { user, claims, loading: authLoading } = useAuth();
  const role = user?.role ?? claims?.role ?? 'assistant';

  useEffect(() => {
    if (!authLoading && role === 'super_admin' && !isImpersonating()) {
      router.replace('/dashboard/admin/tenants');
    }
  }, [authLoading, role, router]);

  if (authLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48 rounded-lg" />
        <div className="grid grid-cols-4 gap-4">
          {[0,1,2,3].map(i => <Skeleton key={i} className="h-24 rounded-xl" />)}
        </div>
      </div>
    );
  }

  if (role === 'super_admin' && !isImpersonating()) {
    return null;
  }

  if (role === 'assistant') {
    // Asistan → sadece envanter dashboard
    return <AssistantWrapper />;
  }

  if (role === 'doctor') {
    return <DoctorDashboard fullName={user?.full_name ?? claims?.full_name ?? 'Hekim'} />;
  }

  // owner
  return <OwnerDashboard />;
}

function AssistantWrapper() {
  const { expiring } = useDashboard();
  return <AssistantDashboard expiring={expiring} />;
}
