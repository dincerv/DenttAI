'use client';
import { useCallback, useEffect, useState } from 'react';
import { appointmentApi } from '@/lib/api-client';
import type { Appointment, AppointmentCreateBody } from '@/types';

export function useAppointments() {
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  const fetch = useCallback(async (params?: Record<string, string>) => {
    setLoading(true);
    try {
      const res = await appointmentApi.list(params);
      // API may return { items: [...], total: N } or a plain array
      const raw = res.data;
      setAppointments(Array.isArray(raw) ? raw : (raw?.items ?? []));
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e?.response?.data?.detail ?? 'Randevular yüklenemedi');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  const cancel = useCallback(async (id: string) => {
    await appointmentApi.cancel(id);
    setAppointments((prev) =>
      prev.map((a) => a.id === id ? { ...a, status: 'cancelled' } : a),
    );
  }, []);

  const create = useCallback(async (data: AppointmentCreateBody) => {
    const res = await appointmentApi.create(data);
    setAppointments((prev) => [res.data, ...prev]);
    return res.data as Appointment;
  }, []);

  return { appointments, loading, error, refresh: fetch, cancel, create };
}
