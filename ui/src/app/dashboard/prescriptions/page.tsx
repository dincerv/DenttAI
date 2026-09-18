'use client';

import { useState } from 'react';
import { toast } from 'sonner';
import { Plus, RefreshCw, Pill, CheckCircle2, X, Clock, AlertTriangle } from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { tr } from 'date-fns/locale';
import { usePrescriptions, type Prescription } from '@/hooks/usePrescriptions';
import { prescriptionsApi } from '@/lib/api-client';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { CreatePrescriptionModal } from '@/components/prescriptions/CreatePrescriptionModal';
import { cn } from '@/lib/utils';

const STATUS_CFG = {
  draft:     { label: 'Taslak', variant: 'orange' as const },
  issued:    { label: 'Kesildi', variant: 'green' as const },
  cancelled: { label: 'İptal', variant: 'slate' as const },
};

const FILTERS = [
  { value: '', label: 'Tümü' },
  { value: 'draft', label: 'Taslak' },
  { value: 'issued', label: 'Kesildi' },
  { value: 'cancelled', label: 'İptal' },
];

function fmtDate(d: string | null) {
  if (!d) return '—';
  return format(parseISO(d), 'd MMM yyyy', { locale: tr });
}

function RxRow({ rx, onChanged }: { rx: Prescription; onChanged: () => void }) {
  const [busy, setBusy] = useState(false);
  const st = STATUS_CFG[rx.status];

  async function run(action: 'issue' | 'cancel') {
    setBusy(true);
    try {
      if (action === 'issue') {
        const res = await prescriptionsApi.issue(rx.id);
        toast.success(`Reçete kesildi: ${res.data.prescription_no}`);
      } else {
        await prescriptionsApi.cancel(rx.id);
        toast.success('Reçete iptal edildi');
      }
      onChanged();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'İşlem başarısız');
    } finally {
      setBusy(false);
    }
  }

  const when =
    rx.status === 'issued' ? `Kesim: ${fmtDate(rx.issued_at)}`
    : rx.status === 'cancelled' ? `İptal: ${fmtDate(rx.cancelled_at)}`
    : `Oluşturma: ${fmtDate(rx.created_at)}`;

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm px-4 py-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-slate-800 truncate">{rx.patient_name ?? 'Hasta'}</p>
          <p className="text-xs text-slate-500 truncate">
            {rx.prescription_no ?? 'Numara henüz yok'}
            {rx.diagnosis ? ` · ${rx.diagnosis}` : ''}
            {rx.patient_national_id ? ` · ${rx.patient_national_id}` : ' · TC yok'}
          </p>
        </div>
        <Badge variant={st.variant}>{st.label}</Badge>
      </div>
      <ul className="mt-2 text-sm text-slate-600 space-y-0.5">
        {rx.items.map((item) => (
          <li key={item.id}>
            {item.drug_name}
            {item.dosage ? ` · ${item.dosage}` : ''}
            {` × ${Number(item.quantity)}`}
          </li>
        ))}
      </ul>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-slate-400">{when} · Medula: gönderilmedi</p>
        <div className="flex gap-2">
          {rx.status === 'draft' && (
            <Button size="sm" disabled={busy} onClick={() => run('issue')}>
              <CheckCircle2 className="h-3.5 w-3.5" />
              Reçeteyi kes
            </Button>
          )}
          {rx.status !== 'cancelled' && (
            <Button size="sm" variant="danger" disabled={busy} onClick={() => run('cancel')}>
              <X className="h-3.5 w-3.5" />
              İptal
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

export default function PrescriptionsPage() {
  const [statusFilter, setStatusFilter] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const { prescriptions, summary, loading, error, refresh } = usePrescriptions(statusFilter || undefined);

  return (
    <div className="space-y-5">
      {loading && !summary ? (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Kesilen</p>
              <div className="rounded-lg p-2 bg-green-50"><Pill className="h-4 w-4 text-green-600" /></div>
            </div>
            <p className="text-2xl font-bold text-green-600">{summary?.issued_count ?? 0}</p>
            <p className="text-xs text-slate-400 mt-1">e-reçete kaydı</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Taslak</p>
              <div className="rounded-lg p-2 bg-orange-50"><Clock className="h-4 w-4 text-orange-600" /></div>
            </div>
            <p className="text-2xl font-bold text-orange-600">{summary?.draft_count ?? 0}</p>
            <p className="text-xs text-slate-400 mt-1">Kesilmeyi bekliyor</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">TC eksik</p>
              <div className="rounded-lg p-2 bg-blue-50"><AlertTriangle className="h-4 w-4 text-blue-600" /></div>
            </div>
            <p className="text-2xl font-bold text-slate-800">{summary?.missing_national_id ?? 0}</p>
            <p className="text-xs text-slate-400 mt-1">Medula için TC gerekli</p>
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1.5">
          {FILTERS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setStatusFilter(opt.value)}
              className={cn(
                'rounded-lg px-3 py-1.5 text-xs font-medium transition-colors',
                statusFilter === opt.value
                  ? 'bg-brand-600 text-white'
                  : 'bg-white border border-slate-200 text-slate-600 hover:border-brand-300',
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={refresh}>
            <RefreshCw className="h-3.5 w-3.5" />
            Yenile
          </Button>
          <Button size="sm" onClick={() => setShowCreate(true)}>
            <Plus className="h-3.5 w-3.5" />
            Reçete oluştur
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">⚠ {error}</div>
      )}

      {loading ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
        </div>
      ) : prescriptions.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white py-16 text-center">
          <Pill className="h-10 w-10 text-slate-300 mx-auto mb-3" />
          <p className="font-medium text-slate-500">Reçete kaydı yok</p>
          <p className="text-sm text-slate-400 mt-1">Hasta seçip ilaç ekleyerek taslak oluşturun.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {prescriptions.map((rx) => (
            <RxRow key={rx.id} rx={rx} onChanged={refresh} />
          ))}
        </div>
      )}

      {showCreate && (
        <CreatePrescriptionModal onClose={() => setShowCreate(false)} onCreated={refresh} />
      )}
    </div>
  );
}
