import { useCallback, useEffect, useState } from 'react';
import { invoicesApi } from '@/lib/api-client';

export interface InvoiceItem {
  id: string;
  description: string;
  quantity: number;
  unit_price: number;
  vat_rate: number;
  line_total: number;
}

export interface Invoice {
  id: string;
  clinic_id: string;
  patient_id: string;
  payment_id: string | null;
  invoice_no: string | null;
  invoice_type: 'e_fatura' | 'e_arsiv' | 'e_smm';
  status: 'draft' | 'issued' | 'cancelled';
  gib_status: 'not_sent' | 'queued' | 'sent' | 'rejected';
  buyer_name: string;
  buyer_tax_id: string | null;
  buyer_tax_office: string | null;
  buyer_address: string | null;
  subtotal: number;
  vat_rate: number;
  vat_amount: number;
  total: number;
  description: string | null;
  notes: string | null;
  issued_at: string | null;
  cancelled_at: string | null;
  created_at: string;
  items: InvoiceItem[];
}

export interface InvoiceSummary {
  draft_count: number;
  issued_count: number;
  cancelled_count: number;
  issued_total: number;
  e_arsiv_count: number;
  e_fatura_count: number;
  e_smm_count: number;
}

export interface EligiblePayment {
  id: string;
  patient_id: string;
  patient_name: string | null;
  amount: number;
  treatment_type: string | null;
  status: string;
}

export function useInvoices(statusFilter?: string) {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [summary, setSummary] = useState<InvoiceSummary | null>(null);
  const [eligible, setEligible] = useState<EligiblePayment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {};
      if (statusFilter) params.status = statusFilter;
      const [listRes, summaryRes, eligibleRes] = await Promise.all([
        invoicesApi.list(params),
        invoicesApi.summary(),
        invoicesApi.eligiblePayments(),
      ]);
      setInvoices(listRes.data.items ?? []);
      setSummary(summaryRes.data);
      setEligible(eligibleRes.data.items ?? []);
    } catch {
      setError('Faturalar yüklenemedi');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  return { invoices, summary, eligible, loading, error, refresh: fetchAll };
}
