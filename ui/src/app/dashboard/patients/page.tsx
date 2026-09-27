'use client';

import { useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { toast } from 'sonner';
import { Plus, RefreshCw, Upload, Users, AlertTriangle, Search } from 'lucide-react';
import { integrationApi } from '@/lib/api-client';
import { usePatients, type ClinicPatient } from '@/hooks/usePatients';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Skeleton } from '@/components/ui/Skeleton';
import { PatientFormModal } from '@/components/patients/PatientFormModal';

const INSURANCE_LABEL: Record<string, string> = {
  none: 'Yok',
  sgk: 'SGK',
  private: 'Özel',
  mixed: 'Karma',
};

export default function PatientsPage() {
  const [query, setQuery] = useState('');
  const [editing, setEditing] = useState<ClinicPatient | null | 'new'>(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const { patients, loading, error, refresh } = usePatients(query);

  const missingTc = useMemo(
    () => patients.filter((p) => !p.national_id).length,
    [patients],
  );

  async function onExcel(file: File | undefined) {
    if (!file) return;
    setUploading(true);
    try {
      const res = await integrationApi.importPatientsExcel(file);
      const data = res.data as { inserted: number; skipped_duplicates: number; skipped_invalid: number; errors?: string[] };
      toast.success(`Eklenen ${data.inserted} · tekrar ${data.skipped_duplicates} · hatalı ${data.skipped_invalid}`);
      if (data.errors?.length) toast.message(data.errors.slice(0, 3).join('\n'));
      await refresh();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Excel yüklenemedi');
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  }

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Hasta</p>
            <div className="rounded-lg p-2 bg-brand-50"><Users className="h-4 w-4 text-brand-600" /></div>
          </div>
          <p className="text-2xl font-bold text-slate-800">{loading ? '—' : patients.length}</p>
          <p className="text-xs text-slate-400 mt-1">Listelenen kayıt (en fazla 500)</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">TC eksik</p>
            <div className="rounded-lg p-2 bg-orange-50"><AlertTriangle className="h-4 w-4 text-orange-600" /></div>
          </div>
          <p className="text-2xl font-bold text-orange-600">{loading ? '—' : missingTc}</p>
          <p className="text-xs text-slate-400 mt-1">e-reçete / GİB için gerekli</p>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center gap-3 justify-between">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ad, telefon veya TC ara"
            className="w-full rounded-lg border border-slate-200 bg-white py-2 pl-9 pr-3 text-sm"
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            ref={fileRef}
            type="file"
            accept=".xlsx,.xls,.csv"
            className="hidden"
            onChange={(e) => void onExcel(e.target.files?.[0])}
          />
          <Button variant="secondary" size="sm" onClick={refresh}>
            <RefreshCw className="h-3.5 w-3.5" />
            Yenile
          </Button>
          <Button variant="outline" size="sm" disabled={uploading} onClick={() => fileRef.current?.click()}>
            <Upload className="h-3.5 w-3.5" />
            {uploading ? 'Yükleniyor…' : 'Excel içe aktar'}
          </Button>
          <Button size="sm" onClick={() => setEditing('new')}>
            <Plus className="h-3.5 w-3.5" />
            Hasta ekle
          </Button>
        </div>
      </div>

      <p className="text-xs text-slate-500">
        Excel sütunları: ad_soyad veya full_name (zorunlu), telefon, tc, dogum_tarihi, sigorta, email, notlar.
        Personel (hekim/asistan) Yetkiler sayfasından eklenir.
      </p>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>
      )}

      {loading ? (
        <div className="space-y-2">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-16 rounded-xl" />)}</div>
      ) : patients.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
          Hasta yok. Excel yükleyin veya yeni hasta ekleyin.
        </div>
      ) : (
        <div className="space-y-2">
          {patients.map((p) => (
            <Link
              key={p.id}
              href={`/dashboard/patients/${p.id}`}
              className="block w-full text-left rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm hover:border-brand-300"
            >
              <div className="flex flex-wrap items-center gap-2 justify-between">
                <div className="min-w-0">
                  <p className="font-semibold text-slate-800 truncate">{p.full_name}</p>
                  <p className="text-xs text-slate-500 truncate">
                    {p.phone ?? 'Telefon yok'}
                    {p.national_id ? ` · ${p.national_id}` : ' · TC yok'}
                    {p.email ? ` · ${p.email}` : ''}
                  </p>
                </div>
                <Badge variant={p.insurance_type === 'sgk' ? 'blue' : p.national_id ? 'green' : 'orange'}>
                  {INSURANCE_LABEL[p.insurance_type ?? 'none'] ?? 'Yok'}
                </Badge>
              </div>
            </Link>
          ))}
        </div>
      )}

      {editing && (
        <PatientFormModal
          patient={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => void refresh()}
        />
      )}
    </div>
  );
}
