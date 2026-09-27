import { useCallback, useEffect, useState } from 'react';
import { dentalApi } from '@/lib/api-client';

export interface ToothState {
  tooth_fdi: number;
  status: string;
  notes: string | null;
}

export interface DentalTreatment {
  id: string;
  tooth_fdi: number | null;
  procedure: string;
  status: string;
  price: number;
  notes: string | null;
  payment_id: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface TreatmentList {
  items: DentalTreatment[];
  total: number;
  planned_total: number;
  completed_total: number;
}

export function useDentalChart(patientId: string) {
  const [teeth, setTeeth] = useState<ToothState[]>([]);
  const [treatments, setTreatments] = useState<TreatmentList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!patientId) return;
    setLoading(true);
    setError(null);
    try {
      const [chartRes, txRes] = await Promise.all([
        dentalApi.chart(patientId),
        dentalApi.treatments(patientId),
      ]);
      setTeeth((chartRes.data as { teeth: ToothState[] }).teeth ?? []);
      setTreatments(txRes.data as TreatmentList);
    } catch {
      setError('Diş şeması yüklenemedi');
    } finally {
      setLoading(false);
    }
  }, [patientId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { teeth, treatments, loading, error, refresh };
}
