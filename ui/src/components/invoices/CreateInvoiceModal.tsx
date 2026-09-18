'use client';

import { useState } from 'react';
import { toast } from 'sonner';
import { X } from 'lucide-react';
import { invoicesApi } from '@/lib/api-client';
import { Button } from '@/components/ui/Button';
import type { EligiblePayment } from '@/hooks/useInvoices';

interface CreateInvoiceModalProps {
  eligible: EligiblePayment[];
  onClose: () => void;
  onCreated: () => void;
}

const inputCls =
  'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-200 outline-none bg-white';

function formatCurrency(n: number) {
  return new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' }).format(n);
}

export function CreateInvoiceModal({ eligible, onClose, onCreated }: CreateInvoiceModalProps) {
  const [paymentId, setPaymentId] = useState(eligible[0]?.id ?? '');
  const [vatRate, setVatRate] = useState('10');
  const [invoiceType, setInvoiceType] = useState('');
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);

  const selected = eligible.find((p) => p.id === paymentId);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!paymentId) {
      toast.error('Fatura kesilecek ödemeyi seçin');
      return;
    }
    setLoading(true);
    try {
      await invoicesApi.fromPayment(paymentId, {
        vat_rate: parseFloat(vatRate) || 10,
        invoice_type: invoiceType || undefined,
        notes: notes || undefined,
      });
      toast.success('Fatura taslağı oluşturuldu');
      onCreated();
      onClose();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Oluşturulamadı');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/50 px-0 sm:px-4">
      <div className="w-full sm:max-w-lg rounded-t-2xl sm:rounded-2xl bg-white">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
          <h2 className="text-base font-semibold text-slate-800">Ödemeden Fatura</h2>
          <button onClick={onClose} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100">
            <X className="h-4 w-4" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <p className="text-xs text-slate-500">
            GİB gönderimi henüz bağlı değil. Fatura klinik kaydı olarak kesilir; e-Arşiv (bireysel TC), e-Fatura (VKN) veya e-SMM (şahıs hekim).
          </p>
          {eligible.length === 0 ? (
            <p className="text-sm text-slate-500">Fatura kesilecek açık ödeme yok.</p>
          ) : (
            <>
              <div>
                <label className="text-xs font-medium text-slate-600 block mb-1">Ödeme</label>
                <select value={paymentId} onChange={(e) => setPaymentId(e.target.value)} className={inputCls}>
                  {eligible.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.patient_name ?? 'Hasta'} — {formatCurrency(Number(p.amount))}
                      {p.treatment_type ? ` (${p.treatment_type})` : ''}
                    </option>
                  ))}
                </select>
              </div>
              {selected && (
                <div className="rounded-lg bg-slate-50 border border-slate-200 px-3 py-2 text-xs text-slate-600">
                  Toplam (KDV dahil): <strong>{formatCurrency(Number(selected.amount))}</strong>
                </div>
              )}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-slate-600 block mb-1">KDV %</label>
                  <select value={vatRate} onChange={(e) => setVatRate(e.target.value)} className={inputCls}>
                    <option value="0">0</option>
                    <option value="10">10</option>
                    <option value="20">20</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-600 block mb-1">Belge tipi</label>
                  <select value={invoiceType} onChange={(e) => setInvoiceType(e.target.value)} className={inputCls}>
                    <option value="">Otomatik (TC → e-Arşiv)</option>
                    <option value="e_arsiv">e-Arşiv</option>
                    <option value="e_fatura">e-Fatura</option>
                    <option value="e_smm">e-SMM</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="text-xs font-medium text-slate-600 block mb-1">Not</label>
                <input value={notes} onChange={(e) => setNotes(e.target.value)} className={inputCls} placeholder="İsteğe bağlı" />
              </div>
            </>
          )}
          <div className="flex gap-2 pt-1">
            <Button type="submit" className="flex-1" disabled={loading || eligible.length === 0}>
              {loading ? 'Oluşturuluyor...' : 'Taslak oluştur'}
            </Button>
            <Button type="button" variant="secondary" onClick={onClose}>İptal</Button>
          </div>
        </form>
      </div>
    </div>
  );
}
