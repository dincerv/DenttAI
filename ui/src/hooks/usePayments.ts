import { useCallback, useEffect, useState } from 'react';
import { paymentsApi } from '@/lib/api-client';

export interface PaymentTransaction {
  id: string;
  payment_id: string;
  amount: number;
  payment_method: string;
  notes: string | null;
  created_at: string;
  created_by: string | null;
}

export interface Payment {
  id: string;
  clinic_id: string;
  patient_id: string;
  patient_name: string | null;
  appointment_id: string | null;
  amount: number;
  paid_amount: number;
  remaining_amount: number;
  status: 'pending' | 'partial' | 'paid' | 'cancelled' | 'refunded';
  description: string | null;
  treatment_type: string | null;
  payment_method: string | null;
  payer_type: 'patient' | 'sgk' | 'private' | 'mixed';
  insurance_amount: number;
  patient_amount: number;
  installment_count: number;
  due_date: string | null;
  paid_at: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  transactions: PaymentTransaction[];
}

export interface PaymentSummary {
  total_receivable: number;
  total_paid: number;
  total_remaining: number;
  overdue_count: number;
  overdue_amount: number;
  pending_count: number;
  partial_count: number;
  paid_count: number;
  sgk_remaining: number;
  private_remaining: number;
}

interface UsePaymentsOptions {
  statusFilter?: string;
  patientId?: string;
  overdueOnly?: boolean;
}

export function usePayments(options: UsePaymentsOptions = {}) {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [summary, setSummary] = useState<PaymentSummary | null>(null);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | boolean | number> = {};
      if (options.statusFilter) params.status = options.statusFilter;
      if (options.patientId) params.patient_id = options.patientId;
      if (options.overdueOnly) params.overdue_only = true;

      const [listRes, summaryRes] = await Promise.all([
        paymentsApi.list(params),
        paymentsApi.summary(),
      ]);
      setPayments(listRes.data.items ?? []);
      setTotal(listRes.data.total ?? 0);
      setSummary(summaryRes.data);
    } catch {
      setError('Ödemeler yüklenemedi');
    } finally {
      setLoading(false);
    }
  }, [options.statusFilter, options.patientId, options.overdueOnly]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  return { payments, summary, total, loading, error, refresh: fetchAll };
}
