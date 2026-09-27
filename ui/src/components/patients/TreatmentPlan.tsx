'use client';

import { useState } from 'react';
import { toast } from 'sonner';
import { dentalApi } from '@/lib/api-client';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import type { TreatmentList } from '@/hooks/useDentalChart';

export const PROCEDURES: { value: string; label: string }[] = [
  { value: 'dolgu', label: 'Dolgu' },
  { value: 'kanal', label: 'Kanal' },
  { value: 'cekim', label: 'Çekim' },
  { value: 'kron', label: 'Kron' },
  { value: 'kopru', label: 'Köprü' },
  { value: 'implant', label: 'İmplant' },
  { value: 'veneer', label: 'Veneer' },
  { value: 'protez', label: 'Protez' },
  { value: 'temizlik', label: 'Temizlik' },
  { value: 'ortodonti', label: 'Ortodonti' },
  { value: 'muayene', label: 'Muayene' },
  { value: 'diger', label: 'Diğer' },
];

const PROC_LABEL = Object.fromEntries(PROCEDURES.map((p) => [p.value, p.label]));

function money(n: number) {
  return new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' }).format(n);
}

export function TreatmentPlan({
  patientId,
  tooth,
  data,
  onChanged,
}: {
  patientId: string;
  tooth: number | null;
  data: TreatmentList | null;
  onChanged: () => void;
}) {
  const [procedure, setProcedure] = useState('dolgu');
  const [price, setPrice] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await dentalApi.addTreatment(patientId, {
        tooth_fdi: tooth,
        procedure,
        price: price ? Number(price) : 0,
        notes: notes.trim() || undefined,
      });
      toast.success('Tedavi plana eklendi');
      setPrice('');
      setNotes('');
      onChanged();
    } catch {
      toast.error('Eklenemedi');
    } finally {
      setSaving(false);
    }
  }

  async function complete(id: string) {
    setBusyId(id);
    try {
      await dentalApi.completeTreatment(id, true);
      toast.success('Tamamlandı · borç oluşturuldu');
      onChanged();
    } catch {
      toast.error('Tamamlanamadı');
    } finally {
      setBusyId(null);
    }
  }

  async function cancel(id: string) {
    setBusyId(id);
    try {
      await dentalApi.cancelTreatment(id);
      toast.success('İptal edildi');
      onChanged();
    } catch {
      toast.error('İptal edilemedi');
    } finally {
      setBusyId(null);
    }
  }

  const items = data?.items ?? [];

  return (
    <div className="space-y-4">
      <form onSubmit={add} className="rounded-xl border border-slate-200 bg-white p-3 space-y-2">
        <p className="text-xs font-semibold text-slate-600">
          Plan ekle {tooth ? `· diş ${tooth}` : '· diş seçilmedi (tüm ağız)'}
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          <select
            value={procedure}
            onChange={(e) => setProcedure(e.target.value)}
            className="rounded-lg border border-slate-200 px-2 py-2 text-sm"
          >
            {PROCEDURES.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
          <input
            type="number"
            min={0}
            step="0.01"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            placeholder="Ücret ₺"
            className="rounded-lg border border-slate-200 px-2 py-2 text-sm"
          />
          <input
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Not"
            className="rounded-lg border border-slate-200 px-2 py-2 text-sm"
          />
        </div>
        <Button type="submit" size="sm" disabled={saving}>{saving ? 'Ekleniyor…' : 'Plana ekle'}</Button>
      </form>

      <div className="flex gap-3 text-xs text-slate-500">
        <span>Planlı {money(Number(data?.planned_total ?? 0))}</span>
        <span>Tamamlanan {money(Number(data?.completed_total ?? 0))}</span>
      </div>

      {items.length === 0 ? (
        <p className="text-sm text-slate-400">Henüz tedavi planı yok. Dişe tıklayıp ekleyin.</p>
      ) : (
        <ul className="space-y-2">
          {items.map((t) => (
            <li key={t.id} className="rounded-xl border border-slate-200 bg-white px-3 py-2 flex flex-wrap items-center justify-between gap-2">
              <div className="min-w-0">
                <p className="text-sm font-medium text-slate-800">
                  {PROC_LABEL[t.procedure] ?? t.procedure}
                  {t.tooth_fdi ? ` · ${t.tooth_fdi}` : ''}
                  <span className="ml-2 text-slate-500 font-normal">{money(Number(t.price))}</span>
                </p>
                {t.notes && <p className="text-xs text-slate-400 truncate">{t.notes}</p>}
              </div>
              <div className="flex items-center gap-2">
                <Badge variant={t.status === 'completed' ? 'green' : t.status === 'cancelled' ? 'slate' : 'orange'}>
                  {t.status === 'completed' ? 'Yapıldı' : t.status === 'cancelled' ? 'İptal' : 'Planlı'}
                </Badge>
                {t.status === 'planned' && (
                  <>
                    <Button size="sm" disabled={busyId === t.id} onClick={() => void complete(t.id)}>Yapıldı</Button>
                    <Button size="sm" variant="ghost" disabled={busyId === t.id} onClick={() => void cancel(t.id)}>İptal</Button>
                  </>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
