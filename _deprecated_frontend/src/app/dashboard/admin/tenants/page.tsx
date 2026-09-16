'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { adminApi } from '@/lib/api-client';
import { setImpersonation } from '@/lib/auth';
import type {
  AIUsagePeriod,
  ClinicAIUsageSummary,
  ClinicSummary,
  ClinicsAIUsageResponse,
  PlatformStats,
} from '@/types';
import {
  Building2, Users, Plus, ChevronDown, ChevronRight,
  CheckCircle2, XCircle, Loader2, X, ToggleLeft, ToggleRight,
  TrendingUp, AlertCircle, LogIn, Trash2,
} from 'lucide-react';

const PERIOD_LABELS: Record<AIUsagePeriod, string> = {
  day: 'Günlük',
  week: 'Haftalık',
  month: 'Aylık',
  year: 'Yıllık',
};

function formatNumber(value: number): string {
  return new Intl.NumberFormat('tr-TR').format(value);
}

function formatUsd(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 4,
    maximumFractionDigits: 4,
  }).format(value);
}

function formatDateTime(value: string | null): string {
  if (!value) return '—';
  return new Date(value).toLocaleString('tr-TR');
}

const ROLE_LABELS: Record<string, string> = {
  owner: 'Klinik Sahibi',
  doctor: 'Hekim',
  assistant: 'Asistan',
  super_admin: 'Süper Admin',
};

const ROLE_COLORS: Record<string, string> = {
  owner:       'bg-purple-100 text-purple-700',
  doctor:      'bg-blue-100 text-blue-700',
  assistant:   'bg-green-100 text-green-700',
  super_admin: 'bg-red-100 text-red-700',
};

interface ClinicUser {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
}

// --- Platform İstatistik Kartları ---
function StatsCards({ stats, loading }: { stats: PlatformStats | null; loading: boolean }) {
  const cards = [
    {
      label: 'Toplam Klinik',
      value: stats?.total_clinics ?? '–',
      icon: Building2,
      color: 'bg-blue-50 text-blue-600',
      border: 'border-blue-100',
    },
    {
      label: 'Aktif Klinik',
      value: stats?.active_clinics ?? '–',
      icon: CheckCircle2,
      color: 'bg-emerald-50 text-emerald-600',
      border: 'border-emerald-100',
    },
    {
      label: 'Pasif Klinik',
      value: stats ? stats.total_clinics - stats.active_clinics : '–',
      icon: XCircle,
      color: 'bg-slate-50 text-slate-400',
      border: 'border-slate-100',
    },
    {
      label: 'Toplam Kullanıcı',
      value: stats?.total_users ?? '–',
      icon: Users,
      color: 'bg-violet-50 text-violet-600',
      border: 'border-violet-100',
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      {cards.map(({ label, value, icon: Icon, color, border }) => (
        <div key={label} className={`rounded-2xl border ${border} bg-white p-5 shadow-sm`}>
          <div className={`mb-3 flex h-10 w-10 items-center justify-center rounded-xl ${color}`}>
            <Icon className="h-5 w-5" />
          </div>
          {loading ? (
            <div className="h-7 w-16 animate-pulse rounded-lg bg-slate-100" />
          ) : (
            <p className="text-2xl font-bold text-slate-800">{value}</p>
          )}
          <p className="mt-1 text-xs text-slate-500">{label}</p>
        </div>
      ))}
    </div>
  );
}

function AIUsageTable({
  period,
  onPeriodChange,
  loading,
  error,
  data,
  onRetry,
}: {
  period: AIUsagePeriod;
  onPeriodChange: (value: AIUsagePeriod) => void;
  loading: boolean;
  error: string | null;
  data: ClinicsAIUsageResponse | null;
  onRetry: () => void;
}) {
  const items = data?.items ?? [];
  const totals = items.reduce(
    (acc, item) => ({
      request_count: acc.request_count + item.request_count,
      prompt_tokens: acc.prompt_tokens + item.prompt_tokens,
      completion_tokens: acc.completion_tokens + item.completion_tokens,
      total_tokens: acc.total_tokens + item.total_tokens,
      ai_cost_usd: acc.ai_cost_usd + item.ai_cost_usd,
      whatsapp_message_count: acc.whatsapp_message_count + item.whatsapp_message_count,
      whatsapp_cost_usd: acc.whatsapp_cost_usd + item.whatsapp_cost_usd,
      total_cost_usd: acc.total_cost_usd + item.total_cost_usd,
    }),
    {
      request_count: 0,
      prompt_tokens: 0,
      completion_tokens: 0,
      total_tokens: 0,
      ai_cost_usd: 0,
      whatsapp_message_count: 0,
      whatsapp_cost_usd: 0,
      total_cost_usd: 0,
    },
  );

  return (
    <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      <div className="flex flex-col gap-3 border-b border-slate-100 px-5 py-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-semibold text-slate-700">AI Token ve Maliyet Raporu</p>
          <p className="text-xs text-slate-500">Klinik bazli toplamlar</p>
        </div>
        <div className="flex items-center rounded-xl bg-slate-100 p-1">
          {(Object.keys(PERIOD_LABELS) as AIUsagePeriod[]).map((key) => (
            <button
              key={key}
              onClick={() => onPeriodChange(key)}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                period === key
                  ? 'bg-white text-blue-700 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              {PERIOD_LABELS[key]}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-12 text-slate-400">
          <Loader2 className="h-5 w-5 animate-spin" />
          <span className="text-sm">AI kullanim verileri yukleniyor...</span>
        </div>
      ) : error ? (
        <div className="flex flex-col items-center justify-center gap-3 py-12">
          <p className="text-sm text-red-600">{error}</p>
          <button
            onClick={onRetry}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50"
          >
            Tekrar Dene
          </button>
        </div>
      ) : items.length === 0 ? (
        <div className="py-10 text-center text-sm text-slate-400">
          Secilen donemde kayitli AI token kullanim verisi yok.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3 text-left">Klinik</th>
                <th className="px-4 py-3 text-right">Istek</th>
                <th className="px-4 py-3 text-right">Prompt Token</th>
                <th className="px-4 py-3 text-right">Output Token</th>
                <th className="px-4 py-3 text-right">Toplam Token</th>
                <th className="px-4 py-3 text-right">AI Maliyeti (USD)</th>
                <th className="px-4 py-3 text-right">WhatsApp Mesaj</th>
                <th className="px-4 py-3 text-right">WhatsApp Maliyeti (USD)</th>
                <th className="px-4 py-3 text-right">Toplam Maliyet (USD)</th>
                <th className="px-4 py-3 text-right">Son Kullanim</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {items.map((item: ClinicAIUsageSummary) => (
                <tr key={item.clinic_id} className="hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <p className="font-semibold text-slate-700">{item.clinic_name}</p>
                    <p className="text-xs text-slate-400">@{item.clinic_slug}</p>
                  </td>
                  <td className="px-4 py-3 text-right text-slate-600">{formatNumber(item.request_count)}</td>
                  <td className="px-4 py-3 text-right text-slate-600">{formatNumber(item.prompt_tokens)}</td>
                  <td className="px-4 py-3 text-right text-slate-600">{formatNumber(item.completion_tokens)}</td>
                  <td className="px-4 py-3 text-right font-semibold text-slate-800">{formatNumber(item.total_tokens)}</td>
                  <td className="px-4 py-3 text-right font-semibold text-blue-700">{formatUsd(item.ai_cost_usd)}</td>
                  <td className="px-4 py-3 text-right text-slate-600">{formatNumber(item.whatsapp_message_count)}</td>
                  <td className="px-4 py-3 text-right font-semibold text-violet-700">{formatUsd(item.whatsapp_cost_usd)}</td>
                  <td className="px-4 py-3 text-right font-semibold text-emerald-700">{formatUsd(item.total_cost_usd)}</td>
                  <td className="px-4 py-3 text-right text-xs text-slate-500">{formatDateTime(item.last_usage_at)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot className="border-t border-slate-200 bg-slate-50">
              <tr>
                <td className="px-4 py-3 font-semibold text-slate-700">Toplam</td>
                <td className="px-4 py-3 text-right font-semibold text-slate-700">{formatNumber(totals.request_count)}</td>
                <td className="px-4 py-3 text-right font-semibold text-slate-700">{formatNumber(totals.prompt_tokens)}</td>
                <td className="px-4 py-3 text-right font-semibold text-slate-700">{formatNumber(totals.completion_tokens)}</td>
                <td className="px-4 py-3 text-right font-bold text-slate-900">{formatNumber(totals.total_tokens)}</td>
                <td className="px-4 py-3 text-right font-bold text-blue-800">{formatUsd(totals.ai_cost_usd)}</td>
                <td className="px-4 py-3 text-right font-semibold text-slate-700">{formatNumber(totals.whatsapp_message_count)}</td>
                <td className="px-4 py-3 text-right font-bold text-violet-800">{formatUsd(totals.whatsapp_cost_usd)}</td>
                <td className="px-4 py-3 text-right font-bold text-emerald-800">{formatUsd(totals.total_cost_usd)}</td>
                <td className="px-4 py-3" />
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </div>
  );
}

// --- Yeni Klinik Modalı ---
function generateCode(): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  return Array.from({ length: 6 }, () => chars[Math.floor(Math.random() * chars.length)]).join('');
}

function CreateClinicModal({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [clinicName, setClinicName] = useState('');
  const [clinicCode, setClinicCode] = useState(() => generateCode());
  const [ownerEmail, setOwnerEmail] = useState('');
  const [ownerFullName, setOwnerFullName] = useState('');
  const [ownerPassword, setOwnerPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const emailDomain = ownerEmail.includes('@') ? ownerEmail.split('@')[1] : '';
  const hasOwner = ownerEmail.trim() || ownerPassword.trim() || ownerFullName.trim();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (hasOwner && !(ownerEmail && ownerPassword && ownerFullName)) {
      setError('Owner eklemek için ad soyad, e-posta ve şifrenin tamamını doldurun.');
      return;
    }
    if (ownerEmail && !ownerEmail.includes('@')) {
      setError('Geçerli bir e-posta adresi girin (ör: admin@demo.com).');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await adminApi.createClinic({
        clinic_name: clinicName.trim(),
        clinic_code: clinicCode.trim(),
        ...(hasOwner ? {
          owner_full_name: ownerFullName.trim(),
          owner_email: ownerEmail.trim().toLowerCase(),
          owner_password: ownerPassword,
        } : {}),
      });
      onSuccess();
      onClose();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ?? 'Klinik oluşturulamadı');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded-2xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
          <div>
            <h3 className="text-base font-bold text-slate-800">Yeni Klinik Ekle</h3>
            <p className="text-xs text-slate-500">Klinik kodu ve admin e-postası belirleyin</p>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 hover:bg-slate-100 transition-colors">
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={submit} className="px-6 py-5 space-y-5">
          {error && (
            <div className="flex items-start gap-2 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-600">
              <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
              {error}
            </div>
          )}

          <div>
            <p className="mb-3 text-xs font-bold uppercase tracking-wide text-slate-400">Klinik Bilgileri</p>
            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-600">Klinik Adı *</label>
                <input
                  required
                  value={clinicName}
                  onChange={e => setClinicName(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
                  placeholder="Uzman Ağız Sağlığı"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-600">
                  Klinik Kodu *
                  <span className="ml-1 font-normal text-slate-400">– 6 haneli, giriş için kullanılır</span>
                </label>
                <div className="flex items-center gap-2">
                  <input
                    required
                    value={clinicCode}
                    onChange={e => setClinicCode(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 6))}
                    maxLength={6}
                    pattern="^[A-Z0-9]{6}$"
                    className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm font-mono tracking-widest focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
                    placeholder="A1B2C3"
                  />
                  <button
                    type="button"
                    onClick={() => setClinicCode(generateCode())}
                    className="shrink-0 rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-colors flex items-center gap-1"
                  >
                    <TrendingUp className="h-3.5 w-3.5" /> Yenile
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <p className="mb-3 text-xs font-bold uppercase tracking-wide text-slate-400">
              Klinik Admini
              <span className="ml-1 font-normal normal-case text-slate-400">(opsiyonel)</span>
            </p>
            {emailDomain && (
              <div className="mb-3 rounded-lg bg-blue-50 border border-blue-200 px-3 py-2 text-xs text-blue-700">
                Bu klinikte tüm e-postalar <strong>@{emailDomain}</strong> ile bitmek zorunda olacak.
              </div>
            )}
            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-600">Ad Soyad</label>
                <input
                  value={ownerFullName}
                  onChange={e => setOwnerFullName(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm bg-white focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
                  placeholder="Dr. Ayşe Kaya"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-600">
                    E-posta
                    <span className="ml-1 font-normal text-slate-400">– @domain kliniğe atanır</span>
                  </label>
                  <input
                    type="email"
                    autoComplete="off"
                    value={ownerEmail}
                    onChange={e => setOwnerEmail(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm bg-white focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
                    placeholder="admin@demo.com"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-600">Şifre</label>
                  <input
                    type="password"
                    autoComplete="new-password"
                    minLength={6}
                    value={ownerPassword}
                    onChange={e => setOwnerPassword(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm bg-white focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
                    placeholder="Min. 6 karakter"
                  />
                </div>
              </div>
            </div>
          </div>

          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose}
              className="flex-1 rounded-lg border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-600 hover:bg-slate-50 transition-colors">
              İptal
            </button>
            <button type="submit" disabled={loading}
              className="flex-1 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60 transition-colors flex items-center justify-center gap-2">
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              Klinik Oluştur
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// --- Kullanıcı Ekleme Modalı ---
function AddUserModal({
  clinicId,
  clinicEmailDomain,
  clinicName,
  onClose,
  onSuccess,
}: {
  clinicId: string;
  clinicEmailDomain: string;
  clinicName: string;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [emailPrefix, setEmailPrefix] = useState('');
  const [form, setForm] = useState({
    full_name: '',
    password: '',
    role: 'assistant',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const email = `${emailPrefix}@${clinicEmailDomain}`;
      await adminApi.addUser(clinicId, { ...form, email });
      onSuccess();
      onClose();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ?? 'Kullanıcı eklenemedi');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-2xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
          <div>
            <h3 className="text-base font-bold text-slate-800">Kullanıcı Ekle</h3>
            <p className="text-xs text-slate-500">{clinicName}</p>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 hover:bg-slate-100 transition-colors">
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={submit} className="space-y-4 px-6 py-5">
          {error && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-600">
              {error}
            </div>
          )}
          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-600">Ad Soyad</label>
            <input
              required
              value={form.full_name}
              onChange={e => setForm(f => ({ ...f, full_name: e.target.value }))}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
              placeholder="Dr. Ahmet Yılmaz"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-600">E-posta</label>
            <div className="flex items-center overflow-hidden rounded-lg border border-slate-300 focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-200">
              <input
                required
                type="text"
                autoComplete="off"
                value={emailPrefix}
                onChange={e => setEmailPrefix(e.target.value.replace(/[@\s]/g, '').toLowerCase())}
                className="flex-1 px-3 py-2 text-sm focus:outline-none bg-white"
                placeholder="kullanici.adi"
              />
              <span className="bg-slate-50 border-l border-slate-300 px-3 py-2 text-sm text-slate-500 select-none whitespace-nowrap">
                @{clinicEmailDomain}
              </span>
            </div>
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-600">Şifre</label>
            <input
              required
              type="password"
              value={form.password}
              onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
              placeholder="Min. 6 karakter"
              minLength={6}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-600">Rol</label>
            <select
              value={form.role}
              onChange={e => setForm(f => ({ ...f, role: e.target.value }))}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            >
              <option value="owner">Owner (Klinik Sahibi)</option>
              <option value="doctor">Hekim</option>
              <option value="assistant">Asistan</option>
            </select>
          </div>
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 rounded-lg border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-600 hover:bg-slate-50 transition-colors"
            >
              İptal
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60 transition-colors flex items-center justify-center gap-2"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Ekle
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// --- Klinik Satırı ---
function ClinicRow({
  clinic,
  onRefresh,
}: {
  clinic: ClinicSummary;
  onRefresh: () => void;
}) {
  const router = useRouter();
  const [expanded, setExpanded] = useState(false);
  const [users, setUsers] = useState<ClinicUser[]>([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [entering, setEntering] = useState(false);

  const loadUsers = async () => {
    setUsersLoading(true);
    try {
      const res = await adminApi.listUsers(clinic.id);
      setUsers(res.data as ClinicUser[]);
    } catch {
      // sessiz
    } finally {
      setUsersLoading(false);
    }
  };

  const toggle = () => {
    if (!expanded) loadUsers();
    setExpanded(p => !p);
  };

  const toggleActive = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setToggling(true);
    try {
      await adminApi.updateClinic(clinic.id, { is_active: !clinic.is_active });
      onRefresh();
    } catch {
      // sessiz
    } finally {
      setToggling(false);
    }
  };

  const deleteClinic = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm(`"${clinic.name}" kliniğini ve tüm verilerini kalıcı olarak silmek istediğinize emin misiniz? Bu işlem geri alınamaz.`)) return;
    setDeleting(true);
    try {
      await adminApi.deleteClinic(clinic.id);
      onRefresh();
    } catch {
      alert('Klinik silinemedi.');
    } finally {
      setDeleting(false);
    }
  };

  const enterClinic = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setEntering(true);
    try {
      const res = await adminApi.impersonateClinic(clinic.id);
      const { access_token, clinic_name, clinic_slug } = res.data;
      setImpersonation(access_token, clinic_name, clinic_slug);
      router.push('/dashboard');
      window.location.href = '/dashboard';
    } catch {
      alert('Kliniğe giriş yapılamadı.');
    } finally {
      setEntering(false);
    }
  };

  return (
    <>
      {showAddModal && (
        <AddUserModal
          clinicId={clinic.id}
          clinicEmailDomain={clinic.email_domain || clinic.slug || ''}
          clinicName={clinic.name}
          onClose={() => setShowAddModal(false)}
          onSuccess={() => { loadUsers(); onRefresh(); }}
        />
      )}

      {/* Ana satır */}
      <div
        className="flex cursor-pointer items-center gap-4 px-5 py-4 hover:bg-slate-50 transition-colors"
        onClick={toggle}
      >
        <div className="flex items-center gap-3 flex-1 min-w-0">
          {expanded
            ? <ChevronDown className="h-4 w-4 text-slate-400 shrink-0" />
            : <ChevronRight className="h-4 w-4 text-slate-400 shrink-0" />
          }
          <div className={`flex h-9 w-9 items-center justify-center rounded-xl shrink-0 ${clinic.is_active ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 text-slate-400'}`}>
            <Building2 className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <p className={`font-semibold truncate ${clinic.is_active ? 'text-slate-800' : 'text-slate-400'}`}>
              {clinic.name}
            </p>
            <div className="flex items-center gap-2">
              <p className="text-xs text-slate-400">@{clinic.slug}</p>
              {clinic.code && (
                <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs font-mono text-slate-600">
                  {clinic.code}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <span className="flex items-center gap-1 text-xs text-slate-500">
            <Users className="h-3.5 w-3.5" /> {clinic.user_count}
          </span>

          {/* Aktif / Pasif Toggle */}
          <button
            onClick={toggleActive}
            disabled={toggling}
            title={clinic.is_active ? 'Kliniği pasife al' : 'Kliniği aktife al'}
            className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-semibold transition-colors ${
              clinic.is_active
                ? 'bg-emerald-50 text-emerald-600 hover:bg-red-50 hover:text-red-600'
                : 'bg-slate-100 text-slate-400 hover:bg-emerald-50 hover:text-emerald-600'
            }`}
          >
            {toggling ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : clinic.is_active ? (
              <ToggleRight className="h-3.5 w-3.5" />
            ) : (
              <ToggleLeft className="h-3.5 w-3.5" />
            )}
            {clinic.is_active ? 'Aktif' : 'Pasif'}
          </button>

          <button
            onClick={e => { e.stopPropagation(); setShowAddModal(true); }}
            className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 transition-colors flex items-center gap-1"
          >
            <Plus className="h-3.5 w-3.5" /> Kullanıcı Ekle
          </button>

          <button
            onClick={enterClinic}
            disabled={entering || !clinic.is_active}
            title={clinic.is_active ? 'Kliniğe gir' : 'Pasif klinik'}
            className="rounded-lg bg-violet-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-violet-700 disabled:opacity-40 transition-colors flex items-center gap-1"
          >
            {entering ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <LogIn className="h-3.5 w-3.5" />}
            Kliniğe Gir
          </button>

          <button
            onClick={deleteClinic}
            disabled={deleting}
            title="Kliniği sil"
            className="rounded-lg bg-red-50 px-3 py-1.5 text-xs font-semibold text-red-600 hover:bg-red-100 disabled:opacity-40 transition-colors flex items-center gap-1"
          >
            {deleting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
            Sil
          </button>
        </div>
      </div>

      {/* Genişletilmiş kullanıcı listesi */}
      {expanded && (
        <div className="border-t border-slate-100 bg-slate-50/50 px-5 pb-4 pt-3">
          {usersLoading ? (
            <div className="flex items-center gap-2 text-sm text-slate-400 py-3">
              <Loader2 className="h-4 w-4 animate-spin" /> Yükleniyor...
            </div>
          ) : users.length === 0 ? (
            <p className="text-sm text-slate-400 py-2">Bu klinikte henüz kullanıcı yok.</p>
          ) : (
            <div className="space-y-2">
              {users.map((u) => (
                <div
                  key={u.id}
                  className="flex items-center gap-3 rounded-lg bg-white px-4 py-2.5 shadow-sm border border-slate-100"
                >
                  <div className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-100 text-xs font-bold text-blue-700 shrink-0">
                    {u.full_name.charAt(0).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-700 truncate">{u.full_name}</p>
                    <p className="text-xs text-slate-400 truncate">{u.email}</p>
                  </div>
                  <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${ROLE_COLORS[u.role] ?? 'bg-slate-100 text-slate-600'}`}>
                    {ROLE_LABELS[u.role] ?? u.role}
                  </span>
                  {!u.is_active && (
                    <span className="text-xs text-slate-400">(Pasif)</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </>
  );
}

// --- Ana Sayfa ---
export default function AdminTenantsPage() {
  const [clinics, setClinics] = useState<ClinicSummary[]>([]);
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const [usagePeriod, setUsagePeriod] = useState<AIUsagePeriod>('month');
  const [usageData, setUsageData] = useState<ClinicsAIUsageResponse | null>(null);
  const [usageLoading, setUsageLoading] = useState(true);
  const [usageError, setUsageError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const fetchStats = async () => {
    setStatsLoading(true);
    try {
      const res = await adminApi.getStats();
      setStats(res.data as PlatformStats);
    } catch {
      // sessiz
    } finally {
      setStatsLoading(false);
    }
  };

  const fetchClinics = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminApi.listClinics();
      const data = res.data as { items: ClinicSummary[]; total: number };
      setClinics(data.items ?? []);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ?? 'Klinikler yüklenemedi');
    } finally {
      setLoading(false);
    }
  };

  const fetchUsage = async (period: AIUsagePeriod) => {
    setUsageLoading(true);
    setUsageError(null);
    try {
      const res = await adminApi.getAIUsage(period);
      setUsageData(res.data as ClinicsAIUsageResponse);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setUsageError(detail ?? 'AI kullanim raporu yuklenemedi');
    } finally {
      setUsageLoading(false);
    }
  };

  const refresh = () => {
    fetchClinics();
    fetchStats();
    fetchUsage(usagePeriod);
  };

  useEffect(() => {
    fetchClinics();
    fetchStats();
  }, []);
  useEffect(() => { fetchUsage(usagePeriod); }, [usagePeriod]);

  return (
    <div className="space-y-6">
      {showCreate && (
        <CreateClinicModal onClose={() => setShowCreate(false)} onSuccess={refresh} />
      )}

      {/* Başlık */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-blue-900">Klinik Yönetimi</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Platformdaki tüm klinikleri görüntüle, ekle ve yönet
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-bold text-white hover:bg-blue-700 transition-colors shadow-sm"
        >
          <Plus className="h-4 w-4" />
          Yeni Klinik Ekle
        </button>
      </div>

      {/* İstatistik Kartları */}
      <StatsCards stats={stats} loading={statsLoading} />

      <AIUsageTable
        period={usagePeriod}
        onPeriodChange={setUsagePeriod}
        loading={usageLoading}
        error={usageError}
        data={usageData}
        onRetry={() => fetchUsage(usagePeriod)}
      />

      {/* Klinik Listesi */}
      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-700">
            <TrendingUp className="h-4 w-4 text-blue-500" />
            Tüm Klinikler
          </div>
          <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-bold text-slate-600">
            {clinics.length}
          </span>
        </div>

        {loading ? (
          <div className="flex items-center justify-center gap-3 py-16 text-slate-400">
            <Loader2 className="h-6 w-6 animate-spin" />
            <span>Yükleniyor...</span>
          </div>
        ) : error ? (
          <div className="flex items-center justify-center py-16">
            <p className="text-sm text-red-600">{error}</p>
          </div>
        ) : clinics.length === 0 ? (
          <div className="py-16 text-center">
            <Building2 className="mx-auto mb-3 h-10 w-10 text-slate-200" />
            <p className="text-sm text-slate-400">Henüz hiç klinik yok.</p>
            <button
              onClick={() => setShowCreate(true)}
              className="mt-4 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 transition-colors"
            >
              <Plus className="h-4 w-4" /> İlk Kliniği Ekle
            </button>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {clinics.map(clinic => (
              <ClinicRow key={clinic.id} clinic={clinic} onRefresh={refresh} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
