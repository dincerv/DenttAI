'use client';
import { useCallback, useEffect, useState } from 'react';
import { waitlistApi } from '@/lib/api-client';
import type { WaitlistEntry } from '@/types';

export function useWaitlist() {
  const [entries, setEntries] = useState<WaitlistEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const res = await waitlistApi.list();
      // Backend sadece aktif kayıtları döndürür; ek filtre gerekmez
      setEntries(res.data);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e?.response?.data?.detail ?? 'Yedek liste yüklenemedi');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  const remove = useCallback(async (id: string) => {
    await waitlistApi.remove(id);
    setEntries((prev) => prev.filter((e) => e.id !== id));
  }, []);

  return { entries, loading, error, refresh: fetch, remove };
}
