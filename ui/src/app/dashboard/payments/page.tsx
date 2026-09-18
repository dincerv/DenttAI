'use client';
import { useState } from 'react';
import { toast } from 'sonner';
import {
  Plus, RefreshCw, TrendingDown, Wallet, AlertTriangle,
  CheckCircle2, Clock, ChevronDown, ChevronUp, CreditCard, X, FileText,
} from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { tr } from 'date-fns/locale';
import { usePayments, type Payment } from '@/hooks/usePayments';
import { invoicesApi, paymentsApi } from '@/lib/api-client';
import { useRouter } from 'next/navigation';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { CreatePaymentModal } from '@/components/payments/CreatePaymentModal';
import { cn } from '@/lib/utils';

const STATUS_CONFIG = {
  pending:   { label: 'Bekliyor',    variant: 'orange' as const, icon: Clock },
  partial:   { label: 'Kısmi',       variant: 'blue'   as const, icon: CreditCard },
  paid:      { label: 'Ödendi',      variant: 'green'  as const, icon: CheckCircle2 },
  cancelled: { label: 'İptal',       variant: 'slate'  as const, icon: X },
  refunded:  { label: 'İade',        variant: 'yellow' as const, icon: RefreshCw },
} satisfies Record<string, { label: string; variant: 'orange'|'blue'|'green'|'slate'|'yellow'|'red'; icon: React.ComponentType<{className?: string}> }>;

const METHOD_LABELS: Record<string, string> = {
  cash:          'Nakit',
  credit_card:   'Kredi Kartı',
  bank_transfer: 'Havale/EFT',
  insurance:     'Sigorta',
  mixed:         'Karma',
};

const PAYER_LABELS: Record<string, string> = {
  patient: 'Hasta',
  sgk:     'SGK',
  private: 'Özel sigorta',
  mixed:   'Karma',
};

const FILTER_OPTIONS = [
  { value: '',         label: 'Tümü' },
  { value: 'pending',  label: 'Bekliyor' },
  { value: 'partial',  label: 'Kısmi' },
  { value: 'paid',     label: 'Ödendi' },
];

function formatCurrency(n: number) {
  return new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' }).format(n);
}

function formatDate(d: string | null) {
  if (!d) return '—';
  return format(parseISO(d), 'd MMM yyyy', { locale: tr });
}

function SummaryCards({ summary, loading }: {
  summary: {
    total_remaining: number;
    total_paid: number;
    overdue_count: number;
    overdue_amount: number;
    sgk_remaining?: number;
    private_remaining?: number;
  } | null;
  loading: boolean;
}) {
  const cards = [
    { label: 'Tahsil Edilemeyen', value: summary?.total_remaining ?? 0, icon: TrendingDown, color: 'text-red-600', bg: 'bg-red-50' },
    { label: 'Tahsil Edilen',     value: summary?.total_paid ?? 0,      icon: Wallet,      color: 'text-green-600', bg: 'bg-green-50' },
    { label: 'Vadesi Geçmiş',     value: summary?.overdue_amount ?? 0,  icon: AlertTriangle, color: 'text-orange-600', bg: 'bg-orange-50' },
  ];

  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[0,1,2].map(i => <Skeleton key={i} className="h-24 rounded-xl" />)}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      {cards.map(({ label, value, icon: Icon, color, bg }) => (
        <div key={label} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
            <div className={cn('rounded-lg p-2', bg)}>
              <Icon className={cn('h-4 w-4', color)} />
            </div>
          </div>
          <p className={cn('text-2xl font-bold', color)}>{formatCurrency(value)}</p>
          {label === 'Vadesi Geçmiş' && summary && summary.overdue_count > 0 && (
            <p className="text-xs text-slate-400 mt-1">{summary.overdue_count} adet ödeme</p>
          )}
          {label === 'Tahsil Edilemeyen' && summary && ((summary.sgk_remaining ?? 0) > 0 || (summary.private_remaining ?? 0) > 0) && (
            <p className="text-xs text-slate-400 mt-1">
              {(summary.sgk_remaining ?? 0) > 0 ? `SGK ${formatCurrency(summary.sgk_remaining ?? 0)}` : ''}
              {(summary.sgk_remaining ?? 0) > 0 && (summary.private_remaining ?? 0) > 0 ? ' · ' : ''}
              {(summary.private_remaining ?? 0) > 0 ? `Özel ${formatCurrency(summary.private_remaining ?? 0)}` : ''}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

function PaymentRow({ payment, onTransactionAdded }: {
  payment: Payment;
  onTransactionAdded: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [showTxForm, setShowTxForm] = useState(false);
  const [txAmount, setTxAmount] = useState('');
  const [txMethod, setTxMethod] = useState('cash');
  const [txNotes, setTxNotes] = useState('');
  const [txLoading, setTxLoading] = useState(false);
  const [invLoading, setInvLoading] = useState(false);
  const router = useRouter();

  const cfg = STATUS_CONFIG[payment.status];
  const pct = payment.amount > 0 ? Math.min(100, (payment.paid_amount / payment.amount) * 100) : 0;

  async function handleAddTransaction() {
    const amount = parseFloat(txAmount);
    if (!amount || amount <= 0) { toast.error('Geçerli bir tutar girin'); return; }
    setTxLoading(true);
    try {
      await paymentsApi.addTransaction(payment.id, { amount, payment_method: txMethod, notes: txNotes || undefined });
      toast.success(`${formatCurrency(amount)} tahsil edildi`);
      setShowTxForm(false);
      setTxAmount(''); setTxNotes('');
      onTransactionAdded();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      toast.error(err?.response?.data?.detail ?? 'İşlem başarısız');
    } finally {
      setTxLoading(false);
    }
  }

  async function handleCreateInvoice() {
    setInvLoading(true);
    try {
      await invoicesApi.fromPayment(payment.id, {});
      toast.success('Fatura taslağı oluşturuldu');
      router.push('/dashboard/invoices');
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      toast.error(err?.response?.data?.detail ?? 'Fatura oluşturulamadı');
    } finally {
      setInvLoading(false);
    }
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      <div
        className="flex flex-wrap items-center gap-3 px-4 py-3 cursor-pointer hover:bg-slate-50 transition-colors"
        onClick={() => setExpanded(v => !v)}
      >
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-slate-800 truncate">
            {payment.patient_name ?? 'Hasta'}
          </p>
          <p className="text-xs text-slate-500 truncate">
            {payment.treatment_type ?? payment.description ?? '—'}
            {payment.payer_type && payment.payer_type !== 'patient' ? ` · ${PAYER_LABELS[payment.payer_type]}` : ''}
          </p>
        </div>

        <div className="hidden sm:flex items-center gap-2 w-32">
          <div className="flex-1 h-1.5 rounded-full bg-slate-100">
            <div
              className={cn('h-full rounded-full transition-all', pct >= 100 ? 'bg-green-500' : 'bg-brand-500')}
              style={{ width: `${pct}%` }}
            />
          </div>
          <span className="text-xs text-slate-500 flex-shrink-0">{Math.round(pct)}%</span>
        </div>

        <div className="text-right flex-shrink-0">
          <p className="font-bold text-slate-800">{formatCurrency(payment.amount)}</p>
          {payment.remaining_amount > 0 && (
            <p className="text-xs text-red-500">Kalan: {formatCurrency(payment.remaining_amount)}</p>
          )}
        </div>

        <div className="flex flex-col items-end gap-1 flex-shrink-0">
          <Badge variant={cfg.variant}>{cfg.label}</Badge>
          {payment.due_date && (
            <span className="text-xs text-slate-400">{formatDate(payment.due_date)}</span>
          )}
        </div>

        {expanded ? <ChevronUp className="h-4 w-4 text-slate-400 flex-shrink-0" /> : <ChevronDown className="h-4 w-4 text-slate-400 flex-shrink-0" />}
      </div>

      {expanded && (
        <div className="border-t border-slate-100 px-4 py-4 space-y-4 bg-slate-50/50">
          {payment.payer_type && payment.payer_type !== 'patient' && (
            <p className="text-xs text-slate-500">
              Ödeyen: {PAYER_LABELS[payment.payer_type]}
              {Number(payment.insurance_amount) > 0 ? ` · Sigorta payı ${formatCurrency(Number(payment.insurance_amount))}` : ''}
              {Number(payment.patient_amount) > 0 ? ` · Hasta payı ${formatCurrency(Number(payment.patient_amount))}` : ''}
            </p>
          )}
          {payment.transactions.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase mb-2">İşlem Geçmişi</p>
              <div className="space-y-1.5">
                {payment.transactions.map(tx => (
                  <div key={tx.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-white border border-slate-200 px-3 py-2">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-3.5 w-3.5 text-green-500 flex-shrink-0" />
                      <span className="text-sm font-medium text-green-700">{formatCurrency(tx.amount)}</span>
                      <span className="text-xs text-slate-500">{METHOD_LABELS[tx.payment_method] ?? tx.payment_method}</span>
                      {tx.notes && <span className="text-xs text-slate-400">· {tx.notes}</span>}
                    </div>
                    <span className="text-xs text-slate-400">{formatDate(tx.created_at)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {payment.status !== 'cancelled' && (
            <Button size="sm" variant="outline" disabled={invLoading} onClick={(e) => { e.stopPropagation(); handleCreateInvoice(); }}>
              <FileText className="h-3.5 w-3.5" />
              {invLoading ? 'Oluşturuluyor...' : 'Fatura kes'}
            </Button>
          )}

          {!['paid','cancelled','refunded'].includes(payment.status) && (
            <div>
              {!showTxForm ? (
                <Button size="sm" variant="primary" onClick={(e) => { e.stopPropagation(); setShowTxForm(true); }}>
                  <Plus className="h-3.5 w-3.5" />
                  Tahsilat Ekle
                </Button>
              ) : (
                <div className="rounded-lg border border-brand-200 bg-brand-50 p-4 space-y-3">
                  <p className="text-sm font-semibold text-brand-800">Tahsilat Kaydı</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs font-medium text-slate-600 block mb-1">Tutar (TL)</label>
                      <input
                        type="number" min="0.01" step="0.01"
                        value={txAmount}
                        onChange={e => setTxAmount(e.target.value)}
                        placeholder={`Maks. ${formatCurrency(payment.remaining_amount)}`}
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-200 outline-none"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-medium text-slate-600 block mb-1">Ödeme Yöntemi</label>
                      <select
                        value={txMethod}
                        onChange={e => setTxMethod(e.target.value)}
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-200 outline-none bg-white"
                      >
                        <option value="cash">Nakit</option>
                        <option value="credit_card">Kredi Kartı</option>
                        <option value="bank_transfer">Havale/EFT</option>
                        <option value="insurance">Sigorta</option>
                      </select>
                    </div>
                  </div>
                  <div>
                    <label className="text-xs font-medium text-slate-600 block mb-1">Not (opsiyonel)</label>
                    <input
                      type="text" value={txNotes}
                      onChange={e => setTxNotes(e.target.value)}
                      placeholder="Makbuz no, açıklama..."
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-200 outline-none"
                    />
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" variant="primary" onClick={handleAddTransaction} disabled={txLoading}>
                      {txLoading ? 'Kaydediliyor...' : 'Kaydet'}
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => setShowTxForm(false)}>
                      İptal
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function PaymentsPage() {
  const [statusFilter, setStatusFilter] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);

  const { payments, summary, loading, error, refresh } = usePayments({ statusFilter: statusFilter || undefined });

  return (
    <div className="space-y-5">
      <SummaryCards summary={summary} loading={loading} />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1.5">
          {FILTER_OPTIONS.map(opt => (
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
          <Button size="sm" onClick={() => setShowCreateModal(true)}>
            <Plus className="h-3.5 w-3.5" />
            Ödeme Ekle
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          ⚠ {error}
        </div>
      )}

      {loading ? (
        <div className="space-y-3">
          {[0,1,2,3].map(i => <Skeleton key={i} className="h-16 rounded-xl" />)}
        </div>
      ) : payments.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white py-16 text-center">
          <Wallet className="h-10 w-10 text-slate-300 mx-auto mb-3" />
          <p className="font-medium text-slate-500">Ödeme kaydı bulunamadı</p>
          <p className="text-sm text-slate-400 mt-1">
            {statusFilter ? 'Bu filtreyle eşleşen ödeme yok' : 'Yeni ödeme eklemek için butonu kullanın'}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {payments.map(payment => (
            <PaymentRow key={payment.id} payment={payment} onTransactionAdded={refresh} />
          ))}
        </div>
      )}

      {showCreateModal && (
        <CreatePaymentModal
          onClose={() => setShowCreateModal(false)}
          onCreated={refresh}
        />
      )}
    </div>
  );
}
