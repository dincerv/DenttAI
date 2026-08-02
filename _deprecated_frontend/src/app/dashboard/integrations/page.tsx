'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  Cable,
  Plus,
  RefreshCw,
  Trash2,
  Wifi,
  WifiOff,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  Settings2,
  KeyRound,
  Link2,
  Phone,
  Stethoscope,
  MessageSquare,
} from 'lucide-react';
import { toast } from 'sonner';
import { apiClient, integrationApi } from '@/lib/api-client';
import type { DoctorMappingsResponse, IntegrationConfig, SyncResult } from '@/types';

const PROVIDER_LABELS: Record<string, string> = {
  dentsoft: 'DentSoft',
  drdentes: 'Dr.Dentes',
};

const PROVIDER_COLORS: Record<string, string> = {
  dentsoft: 'bg-blue-100 text-blue-700',
  drdentes: 'bg-emerald-100 text-emerald-700',
};

const STATUS_CONFIG: Record<string, { icon: typeof CheckCircle2; color: string; label: string }> = {
  success: { icon: CheckCircle2, color: 'text-green-600', label: 'Başarılı' },
  error:   { icon: XCircle,      color: 'text-red-600',   label: 'Hata' },
  never:   { icon: Clock,        color: 'text-slate-400', label: 'Henüz senkronize edilmedi' },
};

// ── DentSoft config form fields ───────────────────────────
const DENTSOFT_FIELDS = [
  { key: 'base_url', label: 'Web Adresi', placeholder: 'https://dentsoft.example.com' },
  { key: 'session_cookie', label: 'Oturum Çerezi', placeholder: 'Tarayıcıdan kopyaladığınız çerez değeri...', multiline: true },
];

// ── Dr.Dentes config form fields ──────────────────────────
const DRDENTES_FIELDS = [
  { key: 'base_url', label: 'Web Adresi', placeholder: 'https://drdentes.com' },
  { key: 'tenant_id', label: 'Firma Kodu', placeholder: 'ör: 210130' },
  { key: 'session_cookie', label: 'Oturum Çerezi', placeholder: 'Tarayıcıdan kopyaladığınız çerez değeri...', multiline: true },
];

const PROVIDER_FIELDS: Record<string, typeof DENTSOFT_FIELDS> = {
  dentsoft: DENTSOFT_FIELDS,
  drdentes: DRDENTES_FIELDS,
};

export default function IntegrationsPage() {
  const [configs, setConfigs] = useState<IntegrationConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [testing, setTesting] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [lastSync, setLastSync] = useState<SyncResult | null>(null);

  // Add form state
  const [newProvider, setNewProvider] = useState('dentsoft');
  const [newDisplayName, setNewDisplayName] = useState('');
  const [newConfig, setNewConfig] = useState<Record<string, string>>({});
  const [newInterval, setNewInterval] = useState(30);
  const [saving, setSaving] = useState(false);
  const [clinicSenderLoading, setClinicSenderLoading] = useState(false);
  const [clinicSenderSaving, setClinicSenderSaving] = useState(false);
  const [whatsappBusinessAccountId, setWhatsappBusinessAccountId] = useState('');
  const [whatsappPhoneNumberId, setWhatsappPhoneNumberId] = useState('');
  const activeConfig = configs.find((cfg) => cfg.is_active) ?? null;

  const fetchConfigs = useCallback(async () => {
    try {
      const { data } = await integrationApi.listConfigs();
      setConfigs(data);

      setClinicSenderLoading(true);
      const clinicSettings = (await apiClient.get('/clinic-settings')).data as {
        whatsapp_business_account_id?: string | null;
        whatsapp_phone_number_id?: string | null;
      };
      setWhatsappBusinessAccountId(clinicSettings.whatsapp_business_account_id ?? '');
      setWhatsappPhoneNumberId(clinicSettings.whatsapp_phone_number_id ?? '');
    } catch {
      toast.error('Entegrasyon ayarları yüklenemedi');
    } finally {
      setClinicSenderLoading(false);
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchConfigs(); }, [fetchConfigs]);

  // ── Manuel sync ────────────────────────────────────────
  const handleSync = async () => {
    if (!activeConfig) {
      toast.error('Önce aktif bir entegrasyon seçin');
      return;
    }
    if (!activeConfig.has_session_cookie) {
      setEditId(activeConfig.id);
      toast.error('Tek tık veri çekmek için önce oturum çerezini ekleyin');
      return;
    }
    setSyncing(true);
    try {
      const { data } = await integrationApi.triggerSync();
      setLastSync(data);
      await fetchConfigs();
      if (data.errors?.length > 0) {
        toast.warning(`Sync tamamlandı ama ${data.errors.length} hata var`);
      } else {
        toast.success(
          `Sync başarılı! Hastalar: ${data.patients_inserted}/${data.patients_pulled}, Randevular: ${data.appointments_inserted}/${data.appointments_pulled}`,
        );
      }
    } catch {
      toast.error('Senkronizasyon başarısız');
    } finally {
      setSyncing(false);
    }
  };

  // ── Test connection ────────────────────────────────────
  const handleTest = async () => {
    if (!activeConfig) {
      toast.error('Önce aktif bir entegrasyon seçin');
      return;
    }
    if (!activeConfig.has_session_cookie) {
      setEditId(activeConfig.id);
      toast.error('Bağlantı testi için önce oturum çerezini ekleyin');
      return;
    }
    setTesting(true);
    try {
      const { data } = await integrationApi.testConnection();
      if (data.success) {
        toast.success(`${PROVIDER_LABELS[data.provider] ?? data.provider}: Bağlantı başarılı`);
      } else {
        toast.error(`${PROVIDER_LABELS[data.provider] ?? data.provider}: ${data.message}`);
      }
    } catch {
      toast.error('Bağlantı testi başarısız');
    } finally {
      setTesting(false);
    }
  };

  // ── Create ────────────────────────────────────────────
  const handleCreate = async () => {
    if (!newDisplayName.trim()) {
      toast.error('Görüntü adı gerekli');
      return;
    }
    setSaving(true);
    try {
      await integrationApi.createConfig({
        provider: newProvider,
        display_name: newDisplayName.trim(),
        config: newConfig,
        sync_interval_minutes: newInterval,
      });
      toast.success('Entegrasyon eklendi');
      setShowAdd(false);
      setNewDisplayName('');
      setNewConfig({});
      setNewInterval(30);
      await fetchConfigs();
    } catch (err: any) {
      const msg = err?.response?.data?.detail;
      toast.error(msg ?? 'Entegrasyon eklenemedi');
    } finally {
      setSaving(false);
    }
  };

  // ── Toggle active ─────────────────────────────────────
  const handleToggle = async (cfg: IntegrationConfig) => {
    try {
      await integrationApi.updateConfig(cfg.id, { is_active: !cfg.is_active });
      toast.success(cfg.is_active ? 'Entegrasyon devre dışı bırakıldı' : 'Entegrasyon etkinleştirildi');
      await fetchConfigs();
    } catch {
      toast.error('Güncelleme başarısız');
    }
  };

  // ── Delete ────────────────────────────────────────────
  const handleDelete = async (id: string) => {
    if (!confirm('Bu entegrasyonu silmek istediğinize emin misiniz?')) return;
    try {
      await integrationApi.deleteConfig(id);
      toast.success('Entegrasyon silindi');
      await fetchConfigs();
    } catch {
      toast.error('Silme başarısız');
    }
  };

  // ── Update config fields ──────────────────────────────
  const handleUpdateConfig = async (cfg: IntegrationConfig, updatedConfig: Record<string, string>) => {
    try {
      await integrationApi.updateConfig(cfg.id, { config: updatedConfig });
      toast.success('Bağlantı bilgileri güncellendi');
      setEditId(null);
      await fetchConfigs();
    } catch {
      toast.error('Güncelleme başarısız');
    }
  };

  const handleSaveClinicSender = async () => {
    setClinicSenderSaving(true);
    try {
      await apiClient.put('/clinic-settings', {
        whatsapp_business_account_id: whatsappBusinessAccountId.trim() || null,
        whatsapp_phone_number_id: whatsappPhoneNumberId.trim() || null,
      });
      toast.success('Klinik WhatsApp gönderici ayarları kaydedildi');
    } catch {
      toast.error('Klinik WhatsApp gönderici ayarları kaydedilemedi');
    } finally {
      setClinicSenderSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-brand-600" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Entegrasyonlar</h1>
          <p className="text-sm text-slate-500">
            Oturum hazırsa verileri tek tıkla çekin, süresi dolarsa yalnızca çerezi güncelleyin
          </p>
        </div>
        <div className="flex gap-2">
          {configs.some((c) => c.is_active) && (
            <>
              <button
                onClick={handleTest}
                disabled={testing}
                className="flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wifi className="h-4 w-4" />}
                Bağlantıyı Kontrol Et
              </button>
              <button
                onClick={handleSync}
                disabled={syncing || !activeConfig?.has_session_cookie}
                className="flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
              >
                {syncing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                Verileri Çek
              </button>
            </>
          )}
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
          >
            <Plus className="h-4 w-4" />
            Entegrasyon Ekle
          </button>
        </div>
      </div>

      {/* Last Sync Result */}
      {lastSync && (
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <h3 className="mb-2 text-sm font-semibold text-slate-700">Son Senkronizasyon Sonucu</h3>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <span className="text-slate-500">Hastalar:</span>{' '}
              <span className="font-medium">{lastSync.patients_inserted}/{lastSync.patients_pulled} eklendi</span>
            </div>
            <div>
              <span className="text-slate-500">Randevular:</span>{' '}
              <span className="font-medium">{lastSync.appointments_inserted}/{lastSync.appointments_pulled} eklendi</span>
            </div>
            <div>
              <span className="text-slate-500">Doktorlar:</span>{' '}
              <span className="font-medium">{lastSync.doctors_pulled} çekildi</span>
            </div>
          </div>
          {lastSync.errors.length > 0 && (
            <div className="mt-2 rounded bg-red-50 p-2 text-xs text-red-600">
              {lastSync.errors.map((e, i) => <p key={i}>{e}</p>)}
            </div>
          )}
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <div className="mb-4 flex items-start gap-3">
          <div className="rounded-lg bg-blue-100 p-2 text-blue-700">
            <MessageSquare className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-slate-900">Klinik WhatsApp Gönderici</h3>
            <p className="text-sm text-slate-500">
              Bu kliniğe özel gönderici ID tanımlayın. Boş bırakılırsa sistem global env sender'ına düşer.
            </p>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
              Business Account ID
            </label>
            <input
              value={whatsappBusinessAccountId}
              onChange={(e) => setWhatsappBusinessAccountId(e.target.value)}
              placeholder="Örn. 123456789012345"
              className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-brand-500"
              disabled={clinicSenderLoading || clinicSenderSaving}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
              Phone Number ID
            </label>
            <input
              value={whatsappPhoneNumberId}
              onChange={(e) => setWhatsappPhoneNumberId(e.target.value)}
              placeholder="Örn. 987654321098765"
              className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-brand-500"
              disabled={clinicSenderLoading || clinicSenderSaving}
            />
          </div>
        </div>

        <div className="mt-4 border-t border-slate-200 pt-4">
          <button
            onClick={handleSaveClinicSender}
            disabled={clinicSenderLoading || clinicSenderSaving}
            className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {clinicSenderSaving && <Loader2 className="h-4 w-4 animate-spin" />}
            Gönderici Ayarlarını Kaydet
          </button>
        </div>
      </div>

      {/* Add Form */}
      {showAdd && (
        <div className="rounded-lg border border-brand-200 bg-brand-50 p-6">
          <h3 className="mb-4 text-lg font-semibold text-slate-900">Yeni Entegrasyon</h3>
          <div className="grid gap-4">
            {/* Provider select */}
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Yazılım</label>
              <select
                value={newProvider}
                onChange={(e) => { setNewProvider(e.target.value); setNewConfig({}); }}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="dentsoft">DentSoft</option>
                <option value="drdentes">Dr.Dentes</option>
              </select>
            </div>

            {/* Display name */}
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Görüntü Adı</label>
              <input
                value={newDisplayName}
                onChange={(e) => setNewDisplayName(e.target.value)}
                placeholder="ör: Ana Klinik DentSoft"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>

            {/* Provider-specific fields */}
            {(PROVIDER_FIELDS[newProvider] ?? []).map((f) => (
              <div key={f.key}>
                <label className="mb-1 block text-sm font-medium text-slate-700">{f.label}</label>
                {f.multiline ? (
                  <>
                    <textarea
                      value={newConfig[f.key] ?? ''}
                      onChange={(e) => setNewConfig((prev) => ({ ...prev, [f.key]: e.target.value }))}
                      placeholder={f.placeholder}
                      rows={3}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-mono"
                    />
                    <p className="mt-1 text-xs text-slate-500">
                      Tarayıcınızda {newProvider === 'drdentes' ? 'Dr.Dentes' : 'DentSoft'}&apos;e giriş yapın → F12 veya Cookie-Editor benzeri eklenti ile tüm çerez değerlerini kopyalayın
                    </p>
                  </>
                ) : (
                  <input
                    type="text"
                    value={newConfig[f.key] ?? ''}
                    onChange={(e) => setNewConfig((prev) => ({ ...prev, [f.key]: e.target.value }))}
                    placeholder={f.placeholder}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  />
                )}
              </div>
            ))}

            {/* Sync interval */}
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Otomatik Sync Aralığı (dk)</label>
              <input
                type="number"
                min={5}
                max={1440}
                value={newInterval}
                onChange={(e) => setNewInterval(Number(e.target.value))}
                className="w-32 rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>

            <div className="flex gap-2 pt-2">
              <button
                onClick={handleCreate}
                disabled={saving}
                className="flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
              >
                {saving && <Loader2 className="h-4 w-4 animate-spin" />}
                Kaydet
              </button>
              <button
                onClick={() => setShowAdd(false)}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                İptal
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Empty state */}
      {configs.length === 0 && !showAdd && (
        <div className="rounded-lg border-2 border-dashed border-slate-300 p-12 text-center">
          <Cable className="mx-auto h-12 w-12 text-slate-400" />
          <h3 className="mt-4 text-lg font-medium text-slate-900">Henüz entegrasyon yok</h3>
          <p className="mt-1 text-sm text-slate-500">
            DentSoft veya Dr.Dentes bağlantı bilgilerinizi ekleyerek senkronizasyonu başlatın.
          </p>
          <button
            onClick={() => setShowAdd(true)}
            className="mt-4 inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
          >
            <Plus className="h-4 w-4" />
            İlk Entegrasyonu Ekle
          </button>
        </div>
      )}

      {/* Config cards */}
      <div className="space-y-4">
        {configs.map((cfg) => {
          const statusCfg = STATUS_CONFIG[cfg.last_sync_status ?? 'never'] ?? STATUS_CONFIG.never;
          const StatusIcon = statusCfg.icon;
          const isEditing = editId === cfg.id;

          return (
            <div key={cfg.id} className="rounded-lg border border-slate-200 bg-white p-5">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${PROVIDER_COLORS[cfg.provider] ?? 'bg-slate-100 text-slate-700'}`}>
                    {PROVIDER_LABELS[cfg.provider] ?? cfg.provider}
                  </span>
                  <h3 className="text-base font-semibold text-slate-900">{cfg.display_name}</h3>
                  {cfg.is_active ? (
                    <span className="flex items-center gap-1 text-xs text-green-600">
                      <Wifi className="h-3 w-3" /> Aktif
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-xs text-slate-400">
                      <WifiOff className="h-3 w-3" /> Devre dışı
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleToggle(cfg)}
                    className={`rounded-lg px-3 py-1.5 text-xs font-medium ${
                      cfg.is_active
                        ? 'border border-slate-300 text-slate-600 hover:bg-slate-50'
                        : 'bg-green-600 text-white hover:bg-green-700'
                    }`}
                  >
                    {cfg.is_active ? 'Devre Dışı Bırak' : 'Etkinleştir'}
                  </button>
                  <button
                    onClick={() => setEditId(isEditing ? null : cfg.id)}
                    className="rounded-lg border border-slate-300 p-1.5 text-slate-500 hover:bg-slate-50"
                  >
                    <Settings2 className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(cfg.id)}
                    className="rounded-lg border border-red-200 p-1.5 text-red-500 hover:bg-red-50"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>

              {/* Status row */}
              <div className="mt-3 flex items-center gap-4 text-sm text-slate-500">
                <span className={`flex items-center gap-1 ${statusCfg.color}`}>
                  <StatusIcon className="h-4 w-4" />
                  {statusCfg.label}
                </span>
                <span className={`flex items-center gap-1 ${cfg.has_session_cookie ? 'text-emerald-600' : 'text-amber-600'}`}>
                  <KeyRound className="h-3.5 w-3.5" />
                  {cfg.has_session_cookie ? 'Oturum hazır' : 'Oturum gerekli'}
                </span>
                {cfg.last_sync_at && (
                  <span>Son sync: {new Date(cfg.last_sync_at).toLocaleString('tr-TR')}</span>
                )}
                <span className="flex items-center gap-1">
                  <Clock className="h-3.5 w-3.5" />
                  Her {cfg.sync_interval_minutes} dakikada bir
                </span>
              </div>

              {cfg.last_sync_message && (
                <p className="mt-2 text-xs text-slate-500">{cfg.last_sync_message}</p>
              )}

              {cfg.is_active && (
                <div className="mt-3 flex gap-2">
                  <button
                    onClick={handleSync}
                    disabled={syncing || !cfg.has_session_cookie}
                    className="flex items-center gap-2 rounded-lg bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
                  >
                    {syncing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                    Verileri Çek
                  </button>
                  {!cfg.has_session_cookie && (
                    <button
                      onClick={() => setEditId(isEditing ? null : cfg.id)}
                      className="flex items-center gap-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-1.5 text-sm font-medium text-amber-800 hover:bg-amber-100"
                    >
                      <KeyRound className="h-3.5 w-3.5" />
                      Oturumu Güncelle
                    </button>
                  )}
                </div>
              )}

              {/* Edit config fields */}
              {isEditing && (
                <EditConfigForm cfg={cfg} onSave={handleUpdateConfig} onCancel={() => setEditId(null)} />
              )}
            </div>
          );
        })}
      </div>

      {/* Auto-sync info */}
      {configs.some((c) => c.is_active) && (
        <div className="rounded-lg bg-blue-50 p-4 text-sm text-blue-700">
          <p className="font-medium">Otomatik Senkronizasyon Aktif</p>
          <p className="mt-1 text-blue-600">
            Aktif entegrasyonlarınız her 30 dakikada bir otomatik olarak senkronize edilir.
            &quot;Verileri Çek&quot; butonuyla istediğiniz zaman manuel olarak da çalıştırabilirsiniz.
          </p>
        </div>
      )}
    </div>
  );
}

// ── Edit Config Subcomponent ──────────────────────────────

function EditConfigForm({
  cfg,
  onSave,
  onCancel,
}: {
  cfg: IntegrationConfig;
  onSave: (cfg: IntegrationConfig, config: Record<string, string>) => Promise<void>;
  onCancel: () => void;
}) {
  const fields = PROVIDER_FIELDS[cfg.provider] ?? [];
  const [values, setValues] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    fields.forEach((f) => { init[f.key] = ''; });
    return init;
  });
  const [saving, setSaving] = useState(false);
  const [cookieSaving, setCookieSaving] = useState(false);
  const [doctorMappings, setDoctorMappings] = useState<DoctorMappingsResponse | null>(null);
  const [mappingsLoading, setMappingsLoading] = useState(false);
  const [mappingSaving, setMappingSaving] = useState(false);

  useEffect(() => {
    if (cfg.provider !== 'drdentes') return;
    let active = true;
    const loadMappings = async () => {
      setMappingsLoading(true);
      try {
        const { data } = await integrationApi.getDoctorMappings(cfg.id);
        if (active) setDoctorMappings(data);
      } catch {
        if (active) toast.error('Hekim eşleme bilgileri yüklenemedi');
      } finally {
        if (active) setMappingsLoading(false);
      }
    };
    loadMappings();
    return () => { active = false; };
  }, [cfg.id, cfg.provider]);

  const handleSubmit = async () => {
    const filtered: Record<string, string> = {};
    for (const [k, v] of Object.entries(values)) {
      if (v.trim()) filtered[k] = v.trim();
    }
    if (Object.keys(filtered).length === 0) {
      toast.error('En az bir alan doldurulmalı');
      return;
    }
    setSaving(true);
    await onSave(cfg, filtered);
    setSaving(false);
  };

  const handleCookieUpdate = async () => {
    const cookie = values['session_cookie']?.trim();
    if (!cookie || cookie.length < 10) {
      toast.error('Geçerli bir çerez değeri girin (en az 10 karakter)');
      return;
    }
    setCookieSaving(true);
    try {
      await integrationApi.updateSessionCookie(cfg.id, cookie);
      toast.success('Oturum çerezi güncellendi');
      setValues((prev) => ({ ...prev, session_cookie: '' }));
    } catch {
      toast.error('Çerez güncellenemedi');
    } finally {
      setCookieSaving(false);
    }
  };

  const handleDoctorMappingChange = (externalName: string, doctorId: string) => {
    setDoctorMappings((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        external_doctors: prev.external_doctors.map((item) => (
          item.external_name === externalName
            ? { ...item, mapped_doctor_id: doctorId || null }
            : item
        )),
      };
    });
  };

  const handleDoctorMappingsSave = async () => {
    if (!doctorMappings) return;
    setMappingSaving(true);
    try {
      const payload = Object.fromEntries(
        doctorMappings.external_doctors.map((item) => [item.external_name, item.mapped_doctor_id ?? null]),
      );
      const { data } = await integrationApi.updateDoctorMappings(cfg.id, payload);
      setDoctorMappings(data);
      toast.success('Hekim eşlemeleri kaydedildi');
    } catch {
      toast.error('Hekim eşlemeleri kaydedilemedi');
    } finally {
      setMappingSaving(false);
    }
  };

  return (
    <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
      <h4 className="mb-3 text-sm font-semibold text-slate-700">Bağlantı Bilgileri</h4>

      {/* Cookie update section — prominent */}
      <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3">
        <div className="mb-2 flex items-center gap-2">
          <KeyRound className="h-4 w-4 text-amber-600" />
          <span className="text-sm font-semibold text-amber-800">Oturum Çerezi Güncelle</span>
        </div>
        <p className="mb-2 text-xs text-amber-700">
          {cfg.provider === 'drdentes' ? 'Dr.Dentes' : 'DentSoft'}&apos;e tarayıcınızda giriş yapın → F12 veya Cookie-Editor benzeri eklenti ile tüm çerezleri alıp aşağıya yapıştırın.
        </p>
        <textarea
          value={values['session_cookie'] ?? ''}
          onChange={(e) => setValues((prev) => ({ ...prev, session_cookie: e.target.value }))}
          placeholder="çerez1=değer1; çerez2=değer2; ..."
          rows={3}
          className="w-full rounded-lg border border-amber-300 bg-white px-3 py-2 text-sm font-mono"
        />
        <button
          onClick={handleCookieUpdate}
          disabled={cookieSaving}
          className="mt-2 flex items-center gap-2 rounded-lg bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-50"
        >
          {cookieSaving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          <KeyRound className="h-3.5 w-3.5" />
          Çerezi Güncelle
        </button>
      </div>

      {cfg.provider === 'drdentes' && (
        <div className="mb-4 rounded-lg border border-sky-200 bg-sky-50 p-3">
          <div className="mb-2 flex items-center gap-2">
            <Link2 className="h-4 w-4 text-sky-700" />
            <span className="text-sm font-semibold text-sky-900">Hekim Eşleme</span>
          </div>
          <p className="mb-3 text-xs text-sky-700">
            Dr.Dentes hekimlerini DentAI içindeki kendi hekim kayıtlarınıza bağlayın. Eşleme yapılırsa sonraki sync&apos;lerde aynı dış hekim doğrudan seçtiğiniz yerel hekime yazılır.
          </p>
          {mappingsLoading ? (
            <div className="flex items-center gap-2 text-sm text-sky-800">
              <Loader2 className="h-4 w-4 animate-spin" />
              Hekim eşlemeleri yükleniyor...
            </div>
          ) : doctorMappings ? (
            <div className="space-y-3">
              {doctorMappings.external_doctors.map((item) => (
                <div key={item.external_name} className="grid gap-2 rounded-lg border border-sky-100 bg-white p-3 md:grid-cols-[1fr_1fr] md:items-center">
                  <div>
                    <p className="text-sm font-medium text-slate-900">{item.external_name}</p>
                    <p className="text-xs text-slate-500">Dr.Dentes hekimi</p>
                  </div>
                  <select
                    value={item.mapped_doctor_id ?? ''}
                    onChange={(e) => handleDoctorMappingChange(item.external_name, e.target.value)}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                  >
                    <option value="">Otomatik / dış hekim olarak bırak</option>
                    {doctorMappings.local_doctors.map((doctor) => (
                      <option key={doctor.id} value={doctor.id}>{doctor.full_name}</option>
                    ))}
                  </select>
                </div>
              ))}
              <button
                onClick={handleDoctorMappingsSave}
                disabled={mappingSaving}
                className="flex items-center gap-2 rounded-lg bg-sky-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-800 disabled:opacity-50"
              >
                {mappingSaving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                <Link2 className="h-3.5 w-3.5" />
                Eşlemeleri Kaydet
              </button>
            </div>
          ) : null}
        </div>
      )}

      {/* Other config fields */}
      <div className="grid gap-3">
        {fields.filter((f) => f.key !== 'session_cookie').map((f) => (
          <div key={f.key} className="flex items-center gap-3">
            <label className="w-32 text-sm text-slate-600">{f.label}</label>
            <input
              type="text"
              value={values[f.key] ?? ''}
              onChange={(e) => setValues((prev) => ({ ...prev, [f.key]: e.target.value }))}
              placeholder={f.placeholder}
              className="flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
            />
          </div>
        ))}
      </div>
      <div className="mt-3 flex gap-2">
        <button
          onClick={handleSubmit}
          disabled={saving}
          className="flex items-center gap-2 rounded-lg bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          Güncelle
        </button>
        <button
          onClick={onCancel}
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100"
        >
          İptal
        </button>
      </div>
    </div>
  );
}
