/**
 * WaitlistForm — yedek listeye hasta ekle (apiClient)
 */
'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { AlertCircle, CheckCircle2, Loader2, Plus, Search, X } from 'lucide-react';
import { appointmentApi, waitlistApi } from '@/lib/api-client';

const DEFAULT_SPECIALTIES = [
  'Ortodonti',
  'Pedodonti',
  'İmplant',
  'Cerrahi',
  'Endodonti',
  'Periodontoloji',
  'Protez',
  'Genel Diş Hekimliği',
];

interface Patient {
  id: string;
  full_name: string;
  phone?: string | null;
}

interface Doctor {
  id: string;
  full_name: string;
  specialty?: string | null;
}

interface WaitlistFormProps {
  onCreated?: () => void;
}

export default function WaitlistForm({ onCreated }: WaitlistFormProps) {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [specialties, setSpecialties] = useState<string[]>([]);
  const [searchInput, setSearchInput] = useState('');
  const [selectedPatient, setSelectedPatient] = useState<Patient | null>(null);
  const [selectedDoctorId, setSelectedDoctorId] = useState('');
  const [selectedSpecialty, setSelectedSpecialty] = useState('');
  const [notes, setNotes] = useState('');
  const [priority, setPriority] = useState(10);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const filteredPatients = useMemo(() => {
    const q = searchInput.trim().toLowerCase();
    if (!q) return [];
    return patients
      .filter(
        (p) =>
          p.full_name.toLowerCase().includes(q) ||
          (p.phone ?? '').includes(q),
      )
      .slice(0, 12);
  }, [searchInput, patients]);

  const filteredDoctors = useMemo(() => {
    if (!selectedSpecialty) return doctors;
    return doctors.filter((d) => (d.specialty ?? '') === selectedSpecialty);
  }, [doctors, selectedSpecialty]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        const [patientsRes, doctorsRes] = await Promise.all([
          appointmentApi.patients({ limit: 200 }),
          appointmentApi.doctors(),
        ]);
        if (cancelled) return;
        const patientList = Array.isArray(patientsRes.data)
          ? patientsRes.data
          : (patientsRes.data as { patients?: Patient[] })?.patients ?? [];
        const doctorList = Array.isArray(doctorsRes.data)
          ? doctorsRes.data
          : (doctorsRes.data as { doctors?: Doctor[] })?.doctors ?? [];
        setPatients(patientList as Patient[]);
        setDoctors(doctorList as Doctor[]);
        const specs = Array.from(
          new Set([
            ...DEFAULT_SPECIALTIES,
            ...(doctorList as Doctor[])
              .map((d) => d.specialty)
              .filter((s): s is string => Boolean(s && s.trim())),
          ]),
        );
        setSpecialties(specs);
      } catch {
        if (!cancelled) setError('Hasta/hekim listesi yüklenemedi');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (!selectedPatient) {
      setError('Lütfen bir hasta seçin');
      return;
    }
    if (!selectedSpecialty.trim()) {
      setError('Lütfen bir branş seçin');
      return;
    }

    try {
      setSubmitting(true);
      await waitlistApi.add({
        patient_id: selectedPatient.id,
        specialty: selectedSpecialty.trim(),
        doctor_id: selectedDoctorId || null,
        priority,
        notes: notes.trim() || null,
      });
      setSuccess(`${selectedPatient.full_name} yedek listeye eklendi`);
      setSelectedPatient(null);
      setSelectedDoctorId('');
      setSelectedSpecialty('');
      setNotes('');
      setPriority(10);
      setSearchInput('');
      onCreated?.();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      const detail = e?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Eklenirken hata oluştu');
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-10">
        <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm space-y-5">
      <div>
        <h2 className="text-base font-semibold text-slate-800">Yedek listeye ekle</h2>
        <p className="text-sm text-slate-500">Hasta + branş (+ isteğe bağlı hekim)</p>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}
      {success && (
        <div className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          {success}
        </div>
      )}

      <div>
        <label className="mb-1.5 block text-sm font-medium text-slate-700">Hasta</label>
        <div className="relative">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input
            type="text"
            placeholder="Ad veya telefon ara…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-blue-500"
          />
          {searchInput && filteredPatients.length > 0 && (
            <div className="absolute z-10 mt-1 max-h-56 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-lg">
              {filteredPatients.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => {
                    setSelectedPatient(p);
                    setSearchInput('');
                  }}
                  className="block w-full border-b border-slate-100 px-3 py-2 text-left text-sm hover:bg-blue-50 last:border-0"
                >
                  <div className="font-medium text-slate-800">{p.full_name}</div>
                  <div className="text-xs text-slate-500">{p.phone || '—'}</div>
                </button>
              ))}
            </div>
          )}
        </div>
        {selectedPatient && (
          <div className="mt-2 inline-flex items-center gap-2 rounded-full bg-blue-100 px-3 py-1 text-sm text-blue-900">
            {selectedPatient.full_name}
            <button type="button" onClick={() => setSelectedPatient(null)} aria-label="Temizle">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-700">Branş</label>
          {specialties.length > 0 ? (
            <select
              value={selectedSpecialty}
              onChange={(e) => {
                setSelectedSpecialty(e.target.value);
                setSelectedDoctorId('');
              }}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Seçin…</option>
              {specialties.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          ) : (
            <input
              value={selectedSpecialty}
              onChange={(e) => setSelectedSpecialty(e.target.value)}
              placeholder="Örn. Ortodonti"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500"
            />
          )}
        </div>
        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-700">Hekim (opsiyonel)</label>
          <select
            value={selectedDoctorId}
            onChange={(e) => setSelectedDoctorId(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Fark etmez</option>
            {filteredDoctors.map((d) => (
              <option key={d.id} value={d.id}>
                {d.full_name}{d.specialty ? ` — ${d.specialty}` : ''}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-700">Öncelik (1=yüksek)</label>
          <input
            type="number"
            min={1}
            max={100}
            value={priority}
            onChange={(e) => setPriority(Number(e.target.value) || 10)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-700">Not</label>
          <input
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="İsteğe bağlı"
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      <button
        type="submit"
        disabled={submitting}
        className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
      >
        {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
        Listeye ekle
      </button>
    </form>
  );
}
