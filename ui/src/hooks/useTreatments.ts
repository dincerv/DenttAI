'use client';
import { useCallback, useEffect, useState } from 'react';
import { analyticsApi } from '@/lib/api-client';
import { periodDates, type GroupBy } from '@/lib/period';
import type { TreatmentCountsResponse, TreatmentsByDoctorResponse } from '@/types';

export type { GroupBy };

export function useTreatments(groupBy: GroupBy = 'month') {
  const [data, setData]       = useState<TreatmentCountsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  const fetch = useCallback(async (gb: GroupBy) => {
    setLoading(true);
    setError(null);
    try {
      const res = await analyticsApi.treatmentCounts({ group_by: gb, ...periodDates(gb) });
      setData(res.data);
    } catch {
      setError('Tedavi verileri yüklenemedi');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch(groupBy); }, [groupBy, fetch]);

  return { data, loading, error, refetch: fetch };
}

export function useTreatmentsByDoctor(groupBy: GroupBy = 'month') {
  const [data, setData]       = useState<TreatmentsByDoctorResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  const fetch = useCallback(async (gb: GroupBy) => {
    setLoading(true);
    setError(null);
    try {
      const res = await analyticsApi.treatmentsByDoctor(periodDates(gb));
      setData(res.data);
    } catch {
      setError('Hekim tedavi verileri yüklenemedi');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch(groupBy); }, [groupBy, fetch]);

  return { data, loading, error };
}
