'use client';
import { useCallback, useEffect, useState } from 'react';
import { patientNotesApi } from '@/lib/api-client';
import type { PatientNote, PatientNotesSummary } from '@/types';

/** Hasta notlarını patient_id ve/veya filtrelerle çek */
export function usePatientNotes(params?: Record<string, string>) {
  const [notes, setNotes] = useState<PatientNote[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(() => {
    setLoading(true);
    patientNotesApi
      .list(params)
      .then((res) => setNotes(res.data))
      .catch(() => setNotes([]))
      .finally(() => setLoading(false));
  }, [JSON.stringify(params)]);

  useEffect(() => { refresh(); }, [refresh]);

  return { notes, loading, refresh };
}

/** Doktorun kendi tedavi loglarını çek */
export function useMyTreatmentLog(params?: Record<string, string>) {
  const [notes, setNotes] = useState<PatientNote[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(() => {
    setLoading(true);
    patientNotesApi
      .myLog(params)
      .then((res) => setNotes(res.data))
      .catch(() => setNotes([]))
      .finally(() => setLoading(false));
  }, [JSON.stringify(params)]);

  useEffect(() => { refresh(); }, [refresh]);

  return { notes, loading, refresh };
}

/** Admin: Tüm doktorların tedavi logları (group_by destekli) */
export function useAllDoctorsLog(params?: Record<string, string>) {
  const [summaries, setSummaries] = useState<PatientNotesSummary[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(() => {
    setLoading(true);
    patientNotesApi
      .allLog(params)
      .then((res) => setSummaries(res.data))
      .catch(() => setSummaries([]))
      .finally(() => setLoading(false));
  }, [JSON.stringify(params)]);

  useEffect(() => { refresh(); }, [refresh]);

  return { summaries, loading, refresh };
}
