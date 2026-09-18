import { useCallback, useEffect, useState } from 'react';
import { prescriptionsApi } from '@/lib/api-client';

export interface PrescriptionItem {
  id: string;
  drug_name: string;
  barcode: string | null;
  dosage: string | null;
  quantity: number;
  instructions: string | null;
}

export interface Prescription {
  id: string;
  clinic_id: string;
  patient_id: string;
  appointment_id: string | null;
  doctor_id: string | null;
  patient_name: string | null;
  patient_national_id: string | null;
  doctor_name: string | null;
  prescription_no: string | null;
  status: 'draft' | 'issued' | 'cancelled';
  medula_status: 'not_sent' | 'queued' | 'sent' | 'rejected';
  diagnosis: string | null;
  notes: string | null;
  issued_at: string | null;
  cancelled_at: string | null;
  created_at: string;
  items: PrescriptionItem[];
}

export interface PrescriptionSummary {
  draft_count: number;
  issued_count: number;
  cancelled_count: number;
  missing_national_id: number;
}

export function usePrescriptions(statusFilter?: string) {
  const [prescriptions, setPrescriptions] = useState<Prescription[]>([]);
  const [summary, setSummary] = useState<PrescriptionSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {};
      if (statusFilter) params.status = statusFilter;
      const [listRes, summaryRes] = await Promise.all([
        prescriptionsApi.list(params),
        prescriptionsApi.summary(),
      ]);
      setPrescriptions(listRes.data.items ?? []);
      setSummary(summaryRes.data);
    } catch {
      setError('Reçeteler yüklenemedi');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  return { prescriptions, summary, loading, error, refresh: fetchAll };
}
