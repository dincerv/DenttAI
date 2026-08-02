'use client';
import { useCallback, useEffect, useState } from 'react';
import { analyticsApi } from '@/lib/api-client';
import type { AppointmentStatsResponse, TreatmentCountsResponse } from '@/types';

export type GroupBy = 'day' | 'week' | 'month' | 'year';

function periodDates(groupBy: GroupBy): { start_date: string; end_date: string } {
  const today = new Date();
  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  const end = fmt(today);
  let start: string;
  if (groupBy === 'day') {
    start = end;
  } else if (groupBy === 'week') {
    const d = new Date(today);
    d.setDate(today.getDate() - today.getDay() + (today.getDay() === 0 ? -6 : 1));
    start = fmt(d);
  } else if (groupBy === 'month') {
    start = fmt(new Date(today.getFullYear(), today.getMonth(), 1));
  } else {
    start = fmt(new Date(today.getFullYear(), 0, 1));
  }
  return { start_date: start, end_date: end };
}

export function useDoctorDashboard(groupBy: GroupBy = 'month') {
  const [stats, setStats]         = useState<AppointmentStatsResponse | null>(null);
  const [treatData, setTreatData] = useState<TreatmentCountsResponse | null>(null);
  const [loading, setLoading]     = useState(true);
  const [notLinked, setNotLinked] = useState(false);

  const load = useCallback(async (gb: GroupBy) => {
    setLoading(true);
    setNotLinked(false);
    const dates = periodDates(gb);

    const [statsRes, treatRes] = await Promise.allSettled([
      analyticsApi.appointmentStats(dates),
      analyticsApi.treatmentCounts({ group_by: gb, ...dates }),
    ]);

    const isUnlinked = [statsRes, treatRes].some(
      (r) => r.status === 'rejected' &&
        (r.reason as { response?: { status?: number } })?.response?.status === 403,
    );
    if (isUnlinked) {
      setNotLinked(true);
      setStats(null);
      setTreatData(null);
    } else {
      if (statsRes.status === 'fulfilled') setStats(statsRes.value.data);
      if (treatRes.status === 'fulfilled') setTreatData(treatRes.value.data);
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(groupBy); }, [groupBy, load]);

  return { stats, treatData, loading, notLinked };
}
