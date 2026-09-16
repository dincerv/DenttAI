'use client';
import { useEffect, useState } from 'react';
import { analyticsApi } from '@/lib/api-client';
import type {
  AppointmentStatsResponse,
  DoctorPerformanceResponse,
  ExpiringCyclesResponse,
  NewPatientsOverviewResponse,
  RecoveredRevenueResponse,
  WasteReportResponse,
} from '@/types';

export function useDashboard() {
  const [revenue, setRevenue]   = useState<RecoveredRevenueResponse | null>(null);
  const [stats, setStats]       = useState<AppointmentStatsResponse | null>(null);
  const [doctorPerf, setDoctorPerf] = useState<DoctorPerformanceResponse | null>(null);
  const [expiring, setExpiring] = useState<ExpiringCyclesResponse | null>(null);
  const [newPatients, setNewPatients] = useState<NewPatientsOverviewResponse | null>(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    Promise.allSettled([
      analyticsApi.recoveredRevenue(),
      analyticsApi.appointmentStats(),
      analyticsApi.doctorPerformance(),
      analyticsApi.expiringCycles(),
      analyticsApi.newPatientsOverview(),
    ])
      .then(([revRes, statsRes, perfRes, expRes, newPatientsRes]) => {
        if (revRes.status === 'fulfilled')   setRevenue(revRes.value.data);
        if (statsRes.status === 'fulfilled') setStats(statsRes.value.data);
        if (perfRes.status === 'fulfilled')  setDoctorPerf(perfRes.value.data);
        if (expRes.status === 'fulfilled')   setExpiring(expRes.value.data);
        if (newPatientsRes.status === 'fulfilled') setNewPatients(newPatientsRes.value.data);
        const allFailed = [revRes, statsRes, perfRes, expRes, newPatientsRes].every(r => r.status === 'rejected');
        if (allFailed) setError('Analitik veriler yüklenemedi');
      })
      .finally(() => setLoading(false));
  }, []);

  return { revenue, stats, doctorPerf, expiring, newPatients, loading, error };
}

export function useWasteReport() {
  const [data, setData]     = useState<WasteReportResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState<string | null>(null);

  useEffect(() => {
    analyticsApi.wasteReport()
      .then((res) => setData(res.data))
      .catch((err) => setError(err?.response?.data?.detail ?? 'Veri yüklenemedi'))
      .finally(() => setLoading(false));
  }, []);

  return { data, loading, error };
}
