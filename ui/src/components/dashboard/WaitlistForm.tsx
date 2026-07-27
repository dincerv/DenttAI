/**
 * WaitlistForm Component
 *
 * Yedek listeye hasta ekle: Patient seçim + Tercih Edilen Hekimler multi-select
 *
 * Features:
 * - Patient search/select with autocomplete
 * - Preferred doctors multi-select
 * - Specialty filtering
 * - Form validation
 * - Success/error handling
 */

'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { getAccessToken } from '@/lib/auth';
import { Search, X, Plus, Loader2, AlertCircle, CheckCircle2 } from 'lucide-react';

interface Patient {
  id: string;
  full_name: string;
  phone_number: string;
  email: string;
}

interface Doctor {
  id: string;
  full_name: string;
  specialty: string;
}

interface WaitlistEntry {
  patient_id: string;
  preferred_doctor_ids: string[];
  specialty: string;
  notes?: string;
}

interface Toast {
  id: string;
  type: 'success' | 'error' | 'info';
  message: string;
}

export default function WaitlistForm() {
  const { user } = useAuth();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [specialties, setSpecialties] = useState<string[]>([]);
  const [toasts, setToasts] = useState<Toast[]>([]);

  // Form state
  const [searchInput, setSearchInput] = useState('');
  const [selectedPatient, setSelectedPatient] = useState<Patient | null>(null);
  const [selectedDoctors, setSelectedDoctors] = useState<string[]>([]);
  const [selectedSpecialty, setSelectedSpecialty] = useState('');
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Filtered patients for dropdown
  const filteredPatients = useMemo(() => {
    if (!searchInput) return [];
    return patients.filter(
      (p) =>
        p.full_name.toLowerCase().includes(searchInput.toLowerCase()) ||
        p.phone_number.includes(searchInput)
    );
  }, [searchInput, patients]);

  // Doctors filtered by specialty
  const filteredDoctors = useMemo(() => {
    if (!selectedSpecialty) return doctors;
    return doctors.filter((d) => d.specialty === selectedSpecialty);
  }, [doctors, selectedSpecialty]);

  useEffect(() => {
    fetchData();
  }, [user?.id]);

  async function fetchData() {
    try {
      setLoading(true);
      const token = getAccessToken();

      if (!token) {
        setLoading(false);
        return;
      }

      // Fetch patients
      const patientsRes = await fetch('/api/patients', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (patientsRes.ok) {
        const data = await patientsRes.json();
        setPatients(Array.isArray(data) ? data : data.data || []);
      }

      // Fetch doctors
      const doctorsRes = await fetch('/api/doctors', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (doctorsRes.ok) {
        const data = await doctorsRes.json();
        const doctorList = Array.isArray(data) ? data : data.data || [];
        setDoctors(doctorList);

        // Extract unique specialties
        const specs = Array.from(new Set(doctorList.map((d: Doctor) => d.specialty)));
        setSpecialties(specs as string[]);
      }
    } catch (error) {
      console.error('Failed to fetch data:', error);
      addToast('error', 'Veriler yüklenemedi');
    } finally {
      setLoading(false);
    }
  }

  const addToast = (type: Toast['type'], message: string) => {
    const id = Math.random().toString(36).substr(2, 9);
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3000);
  };

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    if (!selectedPatient) {
      addToast('error', 'Lütfen bir hasta seçin');
      return;
    }

    if (!selectedSpecialty) {
      addToast('error', 'Lütfen bir uzmanlık alanı seçin');
      return;
    }

    try {
      setSubmitting(true);
      const token = getAccessToken();
      if (!token) return;

      const payload: WaitlistEntry = {
        patient_id: selectedPatient.id,
        preferred_doctor_ids: selectedDoctors,
        specialty: selectedSpecialty,
        notes: notes || undefined,
      };

      const response = await fetch('/api/waitlist', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        addToast('success', `${selectedPatient.full_name} yedek listeye eklendi`);
        // Reset form
        setSelectedPatient(null);
        setSelectedDoctors([]);
        setSelectedSpecialty('');
        setNotes('');
        setSearchInput('');
      } else {
        const error = await response.json();
        addToast('error', error.detail || 'Eklenirken hata oluştu');
      }
    } catch (error) {
      console.error('Failed to add to waitlist:', error);
      addToast('error', 'Bir hata oluştu');
    } finally {
      setSubmitting(false);
    }
  }

  const toggleDoctor = (doctorId: string) => {
    setSelectedDoctors((prev) =>
      prev.includes(doctorId) ? prev.filter((id) => id !== doctorId) : [...prev, doctorId]
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Toasts */}
      <div className="fixed top-4 right-4 space-y-2 z-50">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`flex items-center gap-3 px-4 py-3 rounded-lg shadow-lg animate-in fade-in slide-in-from-right-4 ${
              toast.type === 'success'
                ? 'bg-green-50 text-green-800 border border-green-200'
                : 'bg-red-50 text-red-800 border border-red-200'
            }`}
          >
            {toast.type === 'success' && <CheckCircle2 className="w-5 h-5" />}
            {toast.type === 'error' && <AlertCircle className="w-5 h-5" />}
            {toast.message}
          </div>
        ))}
      </div>

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Yedek Listeye Hasta Ekle</h1>
        <p className="text-gray-600 mt-2">Hastayı tercih ettiği hekimler ile birlikte ekle</p>
      </div>

      {/* Form Card */}
      <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
        <div className="space-y-8">
          {/* Patient Search */}
          <div>
            <label className="block text-sm font-semibold text-gray-900 mb-3">
              Hasta Seç
            </label>
            <div className="relative">
              <div className="relative">
                <Search className="absolute left-3 top-3 w-5 h-5 text-gray-400" />
                <input
                  type="text"
                  placeholder="Hasta adı veya telefon numarası ara..."
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                />
              </div>

              {/* Dropdown */}
              {searchInput && filteredPatients.length > 0 && (
                <div className="absolute top-full left-0 right-0 mt-2 bg-white border border-gray-300 rounded-lg shadow-lg z-10 max-h-64 overflow-y-auto">
                  {filteredPatients.map((patient) => (
                    <button
                      key={patient.id}
                      type="button"
                      onClick={() => {
                        setSelectedPatient(patient);
                        setSearchInput('');
                      }}
                      className="w-full text-left px-4 py-3 hover:bg-blue-50 border-b border-gray-100 last:border-b-0 transition-colors"
                    >
                      <div className="font-medium text-gray-900">{patient.full_name}</div>
                      <div className="text-sm text-gray-600">{patient.phone_number}</div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Selected Patient Chip */}
            {selectedPatient && (
              <div className="mt-3 inline-flex items-center gap-2 px-3 py-2 bg-blue-100 text-blue-900 rounded-full text-sm font-medium">
                ✓ {selectedPatient.full_name}
                <button
                  type="button"
                  onClick={() => setSelectedPatient(null)}
                  className="ml-1 hover:text-blue-700"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>

          {/* Specialty Select */}
          <div>
            <label className="block text-sm font-semibold text-gray-900 mb-3">
              Uzmanlık Alanı
            </label>
            <select
              value={selectedSpecialty}
              onChange={(e) => {
                setSelectedSpecialty(e.target.value);
                setSelectedDoctors([]); // Reset doctors when specialty changes
              }}
              className="block w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
            >
              <option value="">-- Uzmanlık Alanı Seç --</option>
              {specialties.map((spec) => (
                <option key={spec} value={spec}>
                  {spec}
                </option>
              ))}
            </select>
            {!selectedSpecialty && (
              <p className="text-xs text-gray-600 mt-2">
                Uzmanlık alanı seçerek uygun hekimleri görebilirsiniz
              </p>
            )}
          </div>

          {/* Preferred Doctors Multi-Select */}
          {selectedSpecialty && (
            <div>
              <label className="block text-sm font-semibold text-gray-900 mb-3">
                Tercih Edilen Hekimler
                {selectedDoctors.length > 0 && (
                  <span className="ml-2 text-xs font-normal text-blue-600">
                    ({selectedDoctors.length} seçildi)
                  </span>
                )}
              </label>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {filteredDoctors.map((doctor) => (
                  <label
                    key={doctor.id}
                    className="flex items-center p-3 border-2 border-gray-200 rounded-lg cursor-pointer hover:border-blue-300 hover:bg-blue-50 transition-all"
                  >
                    <input
                      type="checkbox"
                      checked={selectedDoctors.includes(doctor.id)}
                      onChange={() => toggleDoctor(doctor.id)}
                      className="w-4 h-4 text-blue-600 rounded focus:ring-2 focus:ring-blue-500"
                    />
                    <div className="ml-3">
                      <div className="font-medium text-gray-900">{doctor.full_name}</div>
                      <div className="text-xs text-gray-600">{doctor.specialty}</div>
                    </div>
                  </label>
                ))}
              </div>

              {filteredDoctors.length === 0 && (
                <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-sm text-yellow-900">
                  Bu uzmanlık alanında hekim bulunamadı
                </div>
              )}

              <p className="text-xs text-gray-600 mt-2">
                Tercihe göre, sistem önce seçilen hekimlere uygun randevuları teklif edecektir
              </p>
            </div>
          )}

          {/* Notes */}
          <div>
            <label className="block text-sm font-semibold text-gray-900 mb-3">
              Notlar (Opsiyonel)
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="İlave bilgi veya notlar..."
              rows={3}
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none resize-none"
            />
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4 border-t border-gray-200">
            <button
              type="submit"
              disabled={submitting || !selectedPatient || !selectedSpecialty}
              className="inline-flex items-center gap-2 px-6 py-2.5 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
              <Plus className="w-4 h-4" />
              Yedek Listeye Ekle
            </button>
            <button
              type="button"
              onClick={() => {
                setSelectedPatient(null);
                setSelectedDoctors([]);
                setSelectedSpecialty('');
                setNotes('');
                setSearchInput('');
              }}
              className="px-6 py-2.5 border border-gray-300 text-gray-700 font-medium rounded-lg hover:bg-gray-50 transition-colors"
            >
              Temizle
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
