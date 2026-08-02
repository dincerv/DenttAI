'use client';

import { useEffect, useState, useCallback } from 'react';
import {
  Lightbulb,
  TrendingUp,
  Package,
  Users,
  Calendar,
  Activity,
  RefreshCw,
  AlertTriangle,
  AlertCircle,
  Info,
  Sparkles,
  Bot,
} from 'lucide-react';
import { analyticsApi } from '@/lib/api-client';
import type { InsightCard, InsightSeverity, InsightCategory, ClinicInsightsResponse } from '@/types';

// ── Yardımcı helpers ──────────────────────────────────────────────────────────

const CATEGORY_ICONS: Record<InsightCategory, React.ReactNode> = {
  appointment: <Calendar className="h-5 w-5" />,
  revenue:     <TrendingUp className="h-5 w-5" />,
  patient:     <Users className="h-5 w-5" />,
  inventory:   <Package className="h-5 w-5" />,
  performance: <Activity className="h-5 w-5" />,
};

const CATEGORY_LABELS: Record<InsightCategory, string> = {
  appointment: 'Randevu',
  revenue:     'Gelir',
  patient:     'Hasta',
  inventory:   'Envanter',
  performance: 'Performans',
};

const SEVERITY_CONFIG: Record<InsightSeverity, {
  label: string;
  badge: string;
  border: string;
  bg: string;
  iconColor: string;
  Icon: React.ElementType;
}> = {
  critical: {
    label:     'Kritik',
    badge:     'bg-red-100 text-red-700',
    border:    'border-red-200',
    bg:        'bg-red-50',
    iconColor: 'text-red-600',
    Icon:      AlertCircle,
  },
  warning: {
    label:     'Uyarı',
    badge:     'bg-amber-100 text-amber-700',
    border:    'border-amber-200',
    bg:        'bg-amber-50',
    iconColor: 'text-amber-600',
    Icon:      AlertTriangle,
  },
  info: {
    label:     'Bilgi',
    badge:     'bg-blue-100 text-blue-700',
    border:    'border-blue-200',
    bg:        'bg-blue-50',
    iconColor: 'text-blue-600',
    Icon:      Info,
  },
};

// ── Alt bileşenler ────────────────────────────────────────────────────────────

function InsightCardUI({ card }: { card: InsightCard }) {
  const sev = SEVERITY_CONFIG[card.severity] || SEVERITY_CONFIG.info;
  const SevIcon = sev.Icon;

  return (
    <div className={`rounded-xl border ${sev.border} ${sev.bg} p-4 flex flex-col gap-2`}>
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 text-slate-700">
          <span className={sev.iconColor}>
            {CATEGORY_ICONS[card.category] || <Lightbulb className="h-5 w-5" />}
          </span>
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
            {CATEGORY_LABELS[card.category] || card.category}
          </span>
        </div>
        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${sev.badge} flex items-center gap-1`}>
          <SevIcon className="h-3 w-3" />
          {sev.label}
        </span>
      </div>

      {/* Title */}
      <h4 className="font-semibold text-slate-800 text-sm leading-snug">{card.title}</h4>

      {/* Metric highlight */}
      {card.metric_label && card.metric_value && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">{card.metric_label}:</span>
          <span className={`text-base font-bold ${sev.iconColor}`}>{card.metric_value}</span>
        </div>
      )}

      {/* Description */}
      <p className="text-xs text-slate-600 leading-relaxed">{card.description}</p>

      {/* Action */}
      {card.action && (
        <div className="mt-1 rounded-lg bg-white/70 border border-white/80 px-3 py-2">
          <p className="text-xs font-medium text-slate-700">
            <span className="text-slate-400 mr-1">→</span>
            {card.action}
          </p>
        </div>
      )}
    </div>
  );
}

// ── Ana panel ─────────────────────────────────────────────────────────────────

interface OwnerInsightsPanelProps {
  targetClinicId?: string; // super_admin impersonation için
}

export function OwnerInsightsPanel({ targetClinicId }: OwnerInsightsPanelProps) {
  const [data, setData] = useState<ClinicInsightsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchInsights = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {};
      if (targetClinicId) params['target_clinic_id'] = targetClinicId;
      const res = await analyticsApi.aiInsights(params);
      setData(res.data as ClinicInsightsResponse);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'İçgörüler yüklenemedi';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [targetClinicId]);

  useEffect(() => {
    fetchInsights();
  }, [fetchInsights]);

  const criticalCount = data?.insights.filter(c => c.severity === 'critical').length ?? 0;
  const warningCount  = data?.insights.filter(c => c.severity === 'warning').length ?? 0;

  return (
    <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      {/* Panel header */}
      <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4 bg-gradient-to-r from-indigo-50 to-blue-50">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600 shadow">
            <Sparkles className="h-5 w-5 text-white" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-800">AI Klinik İçgörüleri</h2>
            <p className="text-xs text-slate-500">Son 30 gün verisi analizi</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Severity counters */}
          {!loading && data && (
            <div className="flex items-center gap-1.5 mr-2">
              {criticalCount > 0 && (
                <span className="flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700">
                  <AlertCircle className="h-3 w-3" />{criticalCount}
                </span>
              )}
              {warningCount > 0 && (
                <span className="flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-700">
                  <AlertTriangle className="h-3 w-3" />{warningCount}
                </span>
              )}
            </div>
          )}

          {data?.ai_powered && (
            <span className="flex items-center gap-1 rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-semibold text-indigo-700">
              <Bot className="h-3 w-3" />
              {data.model_used || 'AI'}
            </span>
          )}

          <button
            onClick={fetchInsights}
            disabled={loading}
            className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-600 disabled:opacity-50 transition"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            Yenile
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="p-5">
        {loading ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3].map(i => (
              <div key={i} className="rounded-xl border border-slate-100 bg-slate-50 p-4 animate-pulse">
                <div className="h-4 bg-slate-200 rounded w-3/4 mb-3" />
                <div className="h-3 bg-slate-200 rounded w-1/2 mb-2" />
                <div className="h-3 bg-slate-200 rounded w-full mb-1" />
                <div className="h-3 bg-slate-200 rounded w-5/6" />
              </div>
            ))}
          </div>
        ) : error ? (
          <div className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            {error}
          </div>
        ) : !data || data.insights.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 text-center text-slate-500">
            <Lightbulb className="h-10 w-10 text-slate-300 mb-3" />
            <p className="text-sm font-medium">Henüz içgörü yok</p>
            <p className="text-xs mt-1">Veri biriktikçe öneriler burada görünecek.</p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {/* Critical cards first */}
              {[...data.insights]
                .sort((a, b) => {
                  const order = { critical: 0, warning: 1, info: 2 };
                  return (order[a.severity] ?? 3) - (order[b.severity] ?? 3);
                })
                .map((card, idx) => (
                  <InsightCardUI key={idx} card={card} />
                ))}
            </div>

            {/* Metrics summary footer */}
            <div className="mt-4 border-t border-slate-100 pt-4 grid grid-cols-3 gap-3 sm:grid-cols-6 text-center">
              {[
                { label: 'Randevu (30g)', value: data.metrics_summary.total_appointments_30d },
                { label: 'İptal Oranı',  value: `%${data.metrics_summary.cancel_rate_pct}` },
                { label: 'Gelmeme',      value: `%${data.metrics_summary.noshow_rate_pct}` },
                { label: 'Bekleme L.',  value: data.metrics_summary.active_waitlist },
                { label: 'Düşük Stok',  value: data.metrics_summary.low_stock_items },
                { label: 'Acil Şikayet', value: data.metrics_summary.urgent_feedback },
              ].map(({ label, value }) => (
                <div key={label} className="flex flex-col">
                  <span className="text-xs text-slate-400">{label}</span>
                  <span className="text-sm font-bold text-slate-700">{value}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
