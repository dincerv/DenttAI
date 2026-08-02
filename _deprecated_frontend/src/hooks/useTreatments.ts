'use client';
import { useCallback, useEffect, useState } from 'react';
import { analyticsApi } from '@/lib/api-client';
import type { TreatmentCountsResponse, TreatmentsByDoctorResponse } from '@/types';

export type GroupBy = 'day' | 'week' | 'month' | 'year';

/** groupBy değerine göre start_date / end_date hesapla (YYYY-MM-DD) */
function periodDates(groupBy: GroupBy): { start_date: string; end_date: string } {
  const today = new Date();
  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  const end = fmt(today);

  let start: string;
  if (groupBy === 'day') {
    start = end; // sadece bugün
  } else if (groupBy === 'week') {
    const d = new Date(today);
    d.setDate(today.getDate() - today.getDay() + (today.getDay() === 0 ? -6 : 1)); // Pazartesi
    start = fmt(d);
  } else if (groupBy === 'month') {
    start = fmt(new Date(today.getFullYear(), today.getMonth(), 1));
  } else {
    start = fmt(new Date(today.getFullYear(), 0, 1)); // 1 Ocak
  }
  return { start_date: start, end_date: end };
}

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
