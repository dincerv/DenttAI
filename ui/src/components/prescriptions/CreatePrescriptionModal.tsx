'use client';

import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Plus, Trash2, X } from 'lucide-react';
import { appointmentApi, prescriptionsApi } from '@/lib/api-client';
import { Button } from '@/components/ui/Button';

interface PatientHit {
  id: string;
  full_name: string;
  phone: string | null;
  national_id?: string | null;
}

interface DrugRow {
  drug_name: string;
  dosage: string;
  quantity: string;
  instructions: string;
}

interface CreatePrescriptionModalProps {
  onClose: () => void;
  onCreated: () => void;
  prefill?: {
    patient_id: string;
    patient_name: string;
    national_id?: string | null;
    appointment_id?: string;
  };
}

const inputCls =
  'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-200 outline-none bg-white';

export function CreatePrescriptionModal({ onClose, onCreated, prefill }: CreatePrescriptionModalProps) {
  const [query, setQuery] = useState(prefill?.patient_name ?? '');
  const [hits, setHits] = useState<PatientHit[]>([]);
  const [selected, setSelected] = useState<PatientHit | null>(
    prefill
      ? { id: prefill.patient_id, full_name: prefill.patient_name, national_id: prefill.national_id ?? null, phone: null }
      : null,
  );
  const [diagnosis, setDiagnosis] = useState('');
  const [notes, setNotes] = useState('');
  const [drugs, setDrugs] = useState<DrugRow[]>([
    { drug_name: '', dosage: '', quantity: '1', instructions: '' },
  ]);
  const [loading, setLoading] = useState(false);

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

  function setDrug(index: number, field: keyof DrugRow, value: string) {
    setDrugs((prev) => prev.map((row, i) => (i === index ? { ...row, [field]: value } : row)));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selected) {
      toast.error('Hasta seçin');
      return;
    }
    const items = drugs
      .map((d) => ({
        drug_name: d.drug_name.trim(),
        dosage: d.dosage.trim() || undefined,
        quantity: parseFloat(d.quantity) || 1,
        instructions: d.instructions.trim() || undefined,
      }))
      .filter((d) => d.drug_name);
    if (items.length === 0) {
      toast.error('En az bir ilaç girin');
      return;
    }
    setLoading(true);
    try {
      await prescriptionsApi.create({
        patient_id: selected.id,
        appointment_id: prefill?.appointment_id,
        diagnosis: diagnosis.trim() || undefined,
        notes: notes.trim() || undefined,
        items,
      });
      toast.success('Reçete taslağı oluşturuldu');
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
    <div className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center bg-black/50 px-0 sm:px-4">
      <div className="w-full sm:max-w-lg max-h-[90vh] overflow-y-auto rounded-t-2xl sm:rounded-2xl bg-white">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
          <h2 className="text-base font-semibold text-slate-800">Yeni e-Reçete</h2>
          <button onClick={onClose} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100">
            <X className="h-4 w-4" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <p className="text-xs text-slate-500">
            Medula gönderimi henüz bağlı değil. Reçete klinik kaydı olarak kesilir; TC’si olan hastalarda ileride e-reçete gönderimine hazır olur.
          </p>
          <div className="relative">
            <label className="text-xs font-medium text-slate-600 block mb-1">Hasta</label>
            <input
              value={query}
              onChange={(e) => { setSelected(null); setQuery(e.target.value); }}
              className={inputCls}
              placeholder="Ad veya telefon ara"
            />
            {hits.length > 0 && (
              <ul className="absolute z-10 mt-1 w-full rounded-lg border border-slate-200 bg-white shadow-lg max-h-40 overflow-y-auto">
                {hits.map((p) => (
                  <li key={p.id}>
                    <button
                      type="button"
                      className="w-full text-left px-3 py-2 text-sm hover:bg-slate-50"
                      onClick={() => { setSelected(p); setQuery(p.full_name); setHits([]); }}
                    >
                      {p.full_name}
                      {p.national_id ? <span className="text-slate-400"> · {p.national_id}</span> : <span className="text-orange-500"> · TC yok</span>}
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {selected?.national_id ? (
              <p className="text-xs text-green-600 mt-1">TC: {selected.national_id}</p>
            ) : selected ? (
              <p className="text-xs text-orange-600 mt-1">TC yok — Medula için sonra eklenmeli</p>
            ) : null}
          </div>
          <div>
            <label className="text-xs font-medium text-slate-600 block mb-1">Tanı</label>
            <input value={diagnosis} onChange={(e) => setDiagnosis(e.target.value)} className={inputCls} placeholder="Örn. Pulpitis" />
          </div>
          <div className="space-y-2">
            <p className="text-xs font-medium text-slate-600">İlaçlar</p>
            {drugs.map((row, i) => (
              <div key={i} className="rounded-lg border border-slate-200 p-3 space-y-2">
                <div className="flex gap-2">
                  <input
                    value={row.drug_name}
                    onChange={(e) => setDrug(i, 'drug_name', e.target.value)}
                    className={inputCls}
                    placeholder="İlaç adı"
                  />
                  {drugs.length > 1 && (
                    <button type="button" className="text-slate-400 hover:text-red-500" onClick={() => setDrugs((p) => p.filter((_, idx) => idx !== i))}>
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <input value={row.dosage} onChange={(e) => setDrug(i, 'dosage', e.target.value)} className={inputCls} placeholder="Doz (1x2)" />
                  <input value={row.quantity} onChange={(e) => setDrug(i, 'quantity', e.target.value)} className={inputCls} placeholder="Adet" type="number" min="1" />
                </div>
                <input value={row.instructions} onChange={(e) => setDrug(i, 'instructions', e.target.value)} className={inputCls} placeholder="Kullanım (yemekten sonra...)" />
              </div>
            ))}
            <Button type="button" size="sm" variant="outline" onClick={() => setDrugs((p) => [...p, { drug_name: '', dosage: '', quantity: '1', instructions: '' }])}>
              <Plus className="h-3.5 w-3.5" />
              İlaç ekle
            </Button>
          </div>
          <div>
            <label className="text-xs font-medium text-slate-600 block mb-1">Not</label>
            <input value={notes} onChange={(e) => setNotes(e.target.value)} className={inputCls} placeholder="İsteğe bağlı" />
          </div>
          <div className="flex gap-2 pt-1">
            <Button type="submit" className="flex-1" disabled={loading}>
              {loading ? 'Oluşturuluyor...' : 'Taslak oluştur'}
            </Button>
            <Button type="button" variant="secondary" onClick={onClose}>İptal</Button>
          </div>
        </form>
      </div>
    </div>
  );
}
