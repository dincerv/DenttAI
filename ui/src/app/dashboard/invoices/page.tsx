'use client';

import { useState } from 'react';
import { toast } from 'sonner';
import {
  Plus, RefreshCw, FileText, CheckCircle2, X, Clock, AlertTriangle,
} from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { tr } from 'date-fns/locale';
import { useInvoices, type Invoice } from '@/hooks/useInvoices';
import { invoicesApi } from '@/lib/api-client';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { CreateInvoiceModal } from '@/components/invoices/CreateInvoiceModal';
import { cn } from '@/lib/utils';

const STATUS_CFG = {
  draft:     { label: 'Taslak', variant: 'orange' as const },
  issued:    { label: 'Kesildi', variant: 'green' as const },
  cancelled: { label: 'İptal', variant: 'slate' as const },
};

const TYPE_CFG: Record<string, { label: string; variant: 'blue' | 'yellow' | 'slate' }> = {
  e_arsiv:  { label: 'e-Arşiv', variant: 'blue' },
  e_fatura: { label: 'e-Fatura', variant: 'yellow' },
  e_smm:    { label: 'e-SMM', variant: 'slate' },
};

const FILTERS = [
  { value: '', label: 'Tümü' },
  { value: 'draft', label: 'Taslak' },
  { value: 'issued', label: 'Kesildi' },
  { value: 'cancelled', label: 'İptal' },
];

function money(n: number) {
  return new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' }).format(n);
}

function fmtDate(d: string | null) {
  if (!d) return '—';
  return format(parseISO(d), 'd MMM yyyy', { locale: tr });
}

function InvoiceRow({ invoice, onChanged }: { invoice: Invoice; onChanged: () => void }) {
  const [busy, setBusy] = useState(false);
  const st = STATUS_CFG[invoice.status];
  const tp = TYPE_CFG[invoice.invoice_type] ?? { label: invoice.invoice_type, variant: 'slate' as const };

  async function run(action: 'issue' | 'cancel') {
    setBusy(true);
    try {
      if (action === 'issue') {
        const res = await invoicesApi.issue(invoice.id);
        toast.success(`Fatura kesildi: ${res.data.invoice_no}`);
      } else {
        await invoicesApi.cancel(invoice.id);
        toast.success('Fatura iptal edildi');
      }
      onChanged();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'İşlem başarısız');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm px-4 py-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-slate-800 truncate">{invoice.buyer_name}</p>
          <p className="text-xs text-slate-500 truncate">
            {invoice.invoice_no ?? 'Numara henüz yok'}
            {invoice.description ? ` · ${invoice.description}` : ''}
            {invoice.buyer_tax_id ? ` · ${invoice.buyer_tax_id}` : ''}
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          <Badge variant={tp.variant}>{tp.label}</Badge>
          <Badge variant={st.variant}>{st.label}</Badge>
        </div>
        <div className="text-right flex-shrink-0">
          <p className="font-bold text-slate-800">{money(Number(invoice.total))}</p>
          <p className="text-xs text-slate-400">
            KDV %{Number(invoice.vat_rate)} · {money(Number(invoice.vat_amount))}
          </p>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-slate-400">
          {invoice.status === 'issued' ? `Kesim: ${fmtDate(invoice.issued_at)}` : `Oluşturma: ${fmtDate(invoice.created_at)}`}
          {' · '}GİB: gönderilmedi
        </p>
        <div className="flex gap-2">
          {invoice.status === 'draft' && (
            <Button size="sm" disabled={busy} onClick={() => run('issue')}>
              <CheckCircle2 className="h-3.5 w-3.5" />
              Faturayı kes
            </Button>
          )}
          {invoice.status !== 'cancelled' && (
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

export default function InvoicesPage() {
  const [statusFilter, setStatusFilter] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const { invoices, summary, eligible, loading, error, refresh } = useInvoices(statusFilter || undefined);

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
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Kesilen toplam</p>
              <div className="rounded-lg p-2 bg-green-50"><FileText className="h-4 w-4 text-green-600" /></div>
            </div>
            <p className="text-2xl font-bold text-green-600">{money(Number(summary?.issued_total ?? 0))}</p>
            <p className="text-xs text-slate-400 mt-1">{summary?.issued_count ?? 0} fatura</p>
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
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Belge tipi</p>
              <div className="rounded-lg p-2 bg-blue-50"><AlertTriangle className="h-4 w-4 text-blue-600" /></div>
            </div>
            <p className="text-2xl font-bold text-slate-800">
              {summary?.e_arsiv_count ?? 0}
              <span className="text-base font-medium text-slate-400"> / {summary?.e_fatura_count ?? 0}</span>
              <span className="text-base font-medium text-slate-400"> / {summary?.e_smm_count ?? 0}</span>
            </p>
            <p className="text-xs text-slate-400 mt-1">e-Arşiv / e-Fatura / e-SMM</p>
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
            Fatura oluştur
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">⚠ {error}</div>
      )}

      {loading ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-20 rounded-xl" />)}
        </div>
      ) : invoices.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white py-16 text-center">
          <FileText className="h-10 w-10 text-slate-300 mx-auto mb-3" />
          <p className="font-medium text-slate-500">Fatura kaydı yok</p>
          <p className="text-sm text-slate-400 mt-1">Bir ödemeden taslak oluşturup kesin.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {invoices.map((inv) => (
            <InvoiceRow key={inv.id} invoice={inv} onChanged={refresh} />
          ))}
        </div>
      )}

      {showCreate && (
        <CreateInvoiceModal
          eligible={eligible}
          onClose={() => setShowCreate(false)}
          onCreated={refresh}
        />
      )}
    </div>
  );
}
