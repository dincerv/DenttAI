import { useCallback, useEffect, useState } from 'react';
import { appointmentApi } from '@/lib/api-client';

export interface ClinicPatient {
  id: string;
  full_name: string;
  phone: string | null;
  email: string | null;
  insurance_type: string | null;
  insurance_provider: string | null;
  national_id: string | null;
  birth_date: string | null;
  notes: string | null;
}

export function usePatients(query: string) {
  const [patients, setPatients] = useState<ClinicPatient[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await appointmentApi.patients({
        q: query.trim() || undefined,
        limit: 500,
      });
      const data = res.data as { patients?: ClinicPatient[] };
      setPatients(data.patients ?? []);
    } catch {
      setError('Hastalar yüklenemedi');
      setPatients([]);
    } finally {
      setLoading(false);
    }
  }, [query]);

  useEffect(() => {
    const t = setTimeout(() => { void refresh(); }, 200);
    return () => clearTimeout(t);
  }, [refresh]);

  return { patients, loading, error, refresh };
}
