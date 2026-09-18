'use client';

import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { X } from 'lucide-react';
import { appointmentApi, paymentsApi } from '@/lib/api-client';
import { Button } from '@/components/ui/Button';

interface PatientHit {
  id: string;
  full_name: string;
  phone: string | null;
  insurance_type?: string | null;
  national_id?: string | null;
}

interface CreatePaymentModalProps {
  onClose: () => void;
  onCreated: () => void;
  prefill?: {
    patient_id: string;
    patient_name: string;
    patient_phone?: string | null;
    appointment_id?: string;
    treatment_type?: string | null;
  };
}

const inputCls =
  'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-200 outline-none';

export function CreatePaymentModal({ onClose, onCreated, prefill }: CreatePaymentModalProps) {
  const [query, setQuery] = useState(prefill?.patient_name ?? '');
  const [hits, setHits] = useState<PatientHit[]>([]);
  const [selected, setSelected] = useState<PatientHit | null>(
    prefill
      ? { id: prefill.patient_id, full_name: prefill.patient_name, phone: prefill.patient_phone ?? null }
      : null,
  );
  const [form, setForm] = useState({
    patient_name: prefill?.patient_name ?? '',
    patient_phone: prefill?.patient_phone ?? '',
    national_id: '',
    amount: '',
    treatment_type: prefill?.treatment_type ?? '',
    payment_method: '',
    insurance_type: 'none',
    insurance_amount: '',
    installment_count: '1',
    due_date: '',
    notes: '',
  });
  const [loading, setLoading] = useState(false);

  function set(field: string, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  useEffect(() => {
    if (selected || query.trim().length < 2) {
      setHits([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await appointmentApi.patients({ q: query.trim(), limit: 8 });
        setHits(res.data.patients ?? []);
      } catch {
        setHits([]);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [query, selected]);

  function pickPatient(p: PatientHit) {
    setSelected(p);
    setQuery(p.full_name);
    setHits([]);
    setForm((prev) => ({
      ...prev,
      patient_name: p.full_name,
      patient_phone: p.phone ?? '',
      national_id: p.national_id ?? '',
      insurance_type: p.insurance_type && p.insurance_type !== 'none' ? p.insurance_type : prev.insurance_type,
    }));
  }

  function clearPatient() {
    setSelected(null);
    setQuery('');
    setHits([]);
    setForm((prev) => ({ ...prev, patient_name: '', patient_phone: '', national_id: '' }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const name = selected?.full_name || form.patient_name.trim() || query.trim();
    if (!name || !form.amount) {
      toast.error('Hasta adı ve tutar zorunludur');
      return;
    }
    const amount = parseFloat(form.amount);
    if (!amount || amount <= 0) {
      toast.error('Geçerli bir tutar girin');
      return;
    }
    const nationalId = form.national_id.replace(/\D/g, '');
    if (nationalId && nationalId.length !== 11) {
      toast.error('TC kimlik 11 haneli olmalı');
      return;
    }
    const insuranceAmount = form.insurance_type === 'mixed' ? parseFloat(form.insurance_amount || '0') : undefined;
    if (form.insurance_type === 'mixed' && (insuranceAmount == null || insuranceAmount < 0 || insuranceAmount > amount)) {
      toast.error('SGK/sigorta tutarı toplamı aşamaz');
      return;
    }

    setLoading(true);
    try {
      await paymentsApi.create({
        patient_id: selected?.id,
        patient_name: selected ? undefined : name,
        patient_phone: selected ? undefined : form.patient_phone || undefined,
        national_id: nationalId || undefined,
        appointment_id: prefill?.appointment_id,
        amount,
        treatment_type: form.treatment_type || undefined,
        payment_method: form.payment_method || undefined,
        insurance_type: form.insurance_type,
        insurance_amount: insuranceAmount,
        installment_count: parseInt(form.installment_count, 10) || 1,
        due_date: form.due_date || undefined,
        notes: form.notes || undefined,
      });
      toast.success('Ödeme kaydı oluşturuldu');
      onCreated();
      onClose();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      const detail = err?.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Oluşturulamadı');
    } finally {
      setLoading(false);
    }
  }

  const showInsuranceCover = form.insurance_type === 'sgk' || form.insurance_type === 'private' || form.insurance_type === 'mixed';

  return (
    <div className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center bg-black/50 px-0 sm:px-4">
      <div className="w-full sm:max-w-xl rounded-t-2xl sm:rounded-2xl bg-white">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
          <h2 className="text-base font-semibold text-slate-800">Yeni Ödeme Kaydı</h2>
          <button onClick={onClose} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100">
            <X className="h-4 w-4" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4 overflow-y-auto max-h-[80vh]">
          <div className="relative sm:col-span-2">
            <label className="text-xs font-medium text-slate-600 block mb-1">Hasta *</label>
            {selected ? (
              <div className="flex items-center justify-between rounded-lg border border-brand-200 bg-brand-50 px-3 py-2">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-slate-800 truncate">{selected.full_name}</p>
                  <p className="text-xs text-slate-500">
                    {selected.phone ?? 'Telefon yok'}
                    {selected.insurance_type && selected.insurance_type !== 'none'
                      ? ` · ${selected.insurance_type === 'sgk' ? 'SGK' : selected.insurance_type === 'private' ? 'Özel sigorta' : 'Karma'}`
                      : ''}
                  </p>
                </div>
                <button type="button" onClick={clearPatient} className="text-xs text-brand-700 hover:underline">
                  Değiştir
                </button>
              </div>
            ) : (
              <>
                <input
                  required
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    set('patient_name', e.target.value);
                  }}
                  placeholder="İsim ile ara veya yeni hasta yaz"
                  className={inputCls}
                />
                {hits.length > 0 && (
                  <ul className="absolute z-10 mt-1 w-full rounded-lg border border-slate-200 bg-white shadow-lg overflow-hidden">
                    {hits.map((p) => (
                      <li key={p.id}>
                        <button
                          type="button"
                          onClick={() => pickPatient(p)}
                          className="w-full text-left px-3 py-2 text-sm hover:bg-slate-50"
                        >
                          <span className="font-medium text-slate-800">{p.full_name}</span>
                          {p.phone && <span className="text-slate-500 ml-2">{p.phone}</span>}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {!selected && (
              <div>
                <label className="text-xs font-medium text-slate-600 block mb-1">Telefon</label>
                <input
                  value={form.patient_phone}
                  onChange={(e) => set('patient_phone', e.target.value)}
                  placeholder="05xx..."
                  className={inputCls}
                />
              </div>
            )}
            <div>
              <label className="text-xs font-medium text-slate-600 block mb-1">TC Kimlik</label>
              <input
                value={form.national_id}
                onChange={(e) => set('national_id', e.target.value.replace(/\D/g, '').slice(0, 11))}
                placeholder="11 haneli"
                inputMode="numeric"
                className={inputCls}
              />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-600 block mb-1">Toplam Tutar (TL) *</label>
              <input
                required
                type="number"
                min="0.01"
                step="0.01"
                value={form.amount}
                onChange={(e) => set('amount', e.target.value)}
                placeholder="0.00"
                className={inputCls}
              />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-600 block mb-1">Taksit Sayısı</label>
              <input
                type="number"
                min="1"
                max="60"
                value={form.installment_count}
                onChange={(e) => set('installment_count', e.target.value)}
                className={inputCls}
              />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-600 block mb-1">Tedavi Türü</label>
              <input
                value={form.treatment_type}
                onChange={(e) => set('treatment_type', e.target.value)}
                placeholder="İmplant, Kanal, vb."
                className={inputCls}
              />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-600 block mb-1">Ödeme Yöntemi</label>
              <select
                value={form.payment_method}
                onChange={(e) => set('payment_method', e.target.value)}
                className={`${inputCls} bg-white`}
              >
                <option value="">Seçiniz</option>
                <option value="cash">Nakit</option>
                <option value="credit_card">Kredi Kartı</option>
                <option value="bank_transfer">Havale/EFT</option>
                <option value="insurance">Sigorta</option>
                <option value="mixed">Karma</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-slate-600 block mb-1">Ödeyen / Sigorta</label>
              <select
                value={form.insurance_type}
                onChange={(e) => set('insurance_type', e.target.value)}
                className={`${inputCls} bg-white`}
              >
                <option value="none">Hasta (ücretli)</option>
                <option value="sgk">SGK</option>
                <option value="private">Özel sigorta</option>
                <option value="mixed">Karma (SGK + hasta)</option>
              </select>
            </div>
            {showInsuranceCover && form.insurance_type === 'mixed' && (
              <div>
                <label className="text-xs font-medium text-slate-600 block mb-1">Sigorta payı (TL)</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={form.insurance_amount}
                  onChange={(e) => set('insurance_amount', e.target.value)}
                  placeholder="SGK / sigorta tutarı"
                  className={inputCls}
                />
              </div>
            )}
            <div>
              <label className="text-xs font-medium text-slate-600 block mb-1">Vade Tarihi</label>
              <input
                type="date"
                value={form.due_date}
                onChange={(e) => set('due_date', e.target.value)}
                className={inputCls}
              />
            </div>
            <div className="sm:col-span-2">
              <label className="text-xs font-medium text-slate-600 block mb-1">Açıklama / Not</label>
              <textarea
                value={form.notes}
                onChange={(e) => set('notes', e.target.value)}
                rows={2}
                placeholder="İsteğe bağlı not..."
                className={`${inputCls} resize-none`}
              />
            </div>
          </div>
          <div className="flex gap-2 pt-2">
            <Button type="submit" className="flex-1" disabled={loading}>
              {loading ? 'Kaydediliyor...' : 'Kaydet'}
            </Button>
            <Button type="button" variant="secondary" onClick={onClose}>İptal</Button>
          </div>
        </form>
      </div>
    </div>
  );
}
