'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { toast } from 'sonner';
import { ArrowLeft, Pencil } from 'lucide-react';
import { appointmentApi, dentalApi } from '@/lib/api-client';
import { useDentalChart } from '@/hooks/useDentalChart';
import type { ClinicPatient } from '@/hooks/usePatients';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Skeleton } from '@/components/ui/Skeleton';
import { PatientFormModal } from '@/components/patients/PatientFormModal';
import { Odontogram, TOOTH_STATUSES, TOOTH_STATUS_LABEL } from '@/components/patients/Odontogram';
import { TreatmentPlan } from '@/components/patients/TreatmentPlan';
import { PatientNotesPanel } from '@/components/dashboard/PatientNotesPanel';

const INSURANCE: Record<string, string> = {
  none: 'Yok', sgk: 'SGK', private: 'Özel', mixed: 'Karma',
};

export default function PatientChartPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [patient, setPatient] = useState<ClinicPatient | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);
  const { teeth, treatments, loading, error, refresh } = useDentalChart(id);

  async function loadPatient() {
    try {
      const res = await appointmentApi.getPatient(id);
      setPatient(res.data as ClinicPatient);
      setLoadError(null);
    } catch {
      setLoadError('Hasta bulunamadı');
    }
  }

  useEffect(() => {
    void loadPatient();
  }, [id]);

  async function setStatus(status: string) {
    if (!selected) {
      toast.message('Önce bir diş seçin');
      return;
    }
    try {
      await dentalApi.setTooth(id, selected, { status });
      await refresh();
    } catch {
      toast.error('Diş durumu kaydedilemedi');
    }
  }

  if (loadError) {
    return (
      <div className="space-y-3">
        <Link href="/dashboard/patients" className="text-sm text-brand-600">← Hastalar</Link>
        <p className="text-sm text-red-600">{loadError}</p>
      </div>
    );
  }

  if (!patient) {
    return <div className="space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-16 rounded-xl" />)}</div>;
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link href="/dashboard/patients" className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800">
            <ArrowLeft className="h-3.5 w-3.5" /> Hastalar
          </Link>
          <h2 className="text-xl font-semibold text-slate-800 mt-1">{patient.full_name}</h2>
          <p className="text-xs text-slate-500">
            {patient.phone ?? 'Telefon yok'}
            {patient.national_id ? ` · ${patient.national_id}` : ' · TC yok'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={patient.insurance_type === 'sgk' ? 'blue' : 'slate'}>
            {INSURANCE[patient.insurance_type ?? 'none'] ?? 'Yok'}
          </Badge>
          <Button size="sm" variant="secondary" onClick={() => setEditing(true)}>
            <Pencil className="h-3.5 w-3.5" /> Kart
          </Button>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Diş şeması (FDI)</p>
        {loading ? (
          <Skeleton className="h-28 rounded-xl" />
        ) : error ? (
          <p className="text-sm text-red-600">{error}</p>
        ) : (
          <Odontogram teeth={teeth} selected={selected} onSelect={setSelected} />
        )}
        <div className="flex flex-wrap gap-1.5 pt-1">
          {TOOTH_STATUSES.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => void setStatus(s)}
              className="rounded-full border border-slate-200 px-2.5 py-1 text-[11px] text-slate-600 hover:border-brand-400"
            >
              {TOOTH_STATUS_LABEL[s]}
            </button>
          ))}
        </div>
        <p className="text-[11px] text-slate-400">Dişe tıklayın, durumu işaretleyin, aşağıdan tedavi ekleyin.</p>
      </div>

      <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-3">Tedavi planı</p>
        <TreatmentPlan patientId={id} tooth={selected} data={treatments} onChanged={() => void refresh()} />
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-3">Notlar</p>
        <PatientNotesPanel patientId={id} patientName={patient.full_name} />
      </div>

      {editing && (
        <PatientFormModal
          patient={patient}
          onClose={() => setEditing(false)}
          onSaved={() => { setEditing(false); void loadPatient(); }}
        />
      )}
    </div>
  );
}
