'use client';

import { useState } from 'react';
import { appointmentApi } from '@/lib/api-client';
import { Button } from '@/components/ui/Button';
import type { ClinicPatient } from '@/hooks/usePatients';

const INSURANCE = [
  { value: 'none', label: 'Yok' },
  { value: 'sgk', label: 'SGK' },
  { value: 'private', label: 'Özel' },
  { value: 'mixed', label: 'Karma' },
];

const SEX = [
  { value: '', label: '—' },
  { value: 'female', label: 'Kadın' },
  { value: 'male', label: 'Erkek' },
  { value: 'other', label: 'Diğer' },
  { value: 'unknown', label: 'Bilinmiyor' },
];

export function PatientFormModal({
  patient,
  onClose,
  onSaved,
}: {
  patient: ClinicPatient | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEdit = Boolean(patient);
  const [fullName, setFullName] = useState(patient?.full_name ?? '');
  const [phone, setPhone] = useState(patient?.phone ?? '');
  const [email, setEmail] = useState(patient?.email ?? '');
  const [nationalId, setNationalId] = useState(patient?.national_id ?? '');
  const [birthDate, setBirthDate] = useState(patient?.birth_date ?? '');
  const [sex, setSex] = useState(patient?.sex ?? '');
  const [insuranceType, setInsuranceType] = useState(patient?.insurance_type ?? 'none');
  const [insuranceProvider, setInsuranceProvider] = useState(patient?.insurance_provider ?? '');
  const [address, setAddress] = useState(patient?.address ?? '');
  const [city, setCity] = useState(patient?.city ?? '');
  const [district, setDistrict] = useState(patient?.district ?? '');
  const [country, setCountry] = useState(patient?.country ?? '');
  const [fileNumber, setFileNumber] = useState(patient?.file_number ?? '');
  const [archiveNumber, setArchiveNumber] = useState(patient?.archive_number ?? '');
  const [occupation, setOccupation] = useState(patient?.occupation ?? '');
  const [nationality, setNationality] = useState(patient?.nationality ?? '');
  const [bloodType, setBloodType] = useState(patient?.blood_type ?? '');
  const [notes, setNotes] = useState(patient?.notes ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError('');
    const body = {
      full_name: fullName.trim(),
      phone: phone.trim(),
      email: email.trim() || undefined,
      national_id: nationalId.trim() || undefined,
      birth_date: birthDate || undefined,
      sex: sex || undefined,
      insurance_type: insuranceType,
      insurance_provider: insuranceProvider.trim() || undefined,
      address: address.trim() || undefined,
      city: city.trim() || undefined,
      district: district.trim() || undefined,
      country: country.trim() || undefined,
      file_number: fileNumber.trim() || undefined,
      archive_number: archiveNumber.trim() || undefined,
      occupation: occupation.trim() || undefined,
      nationality: nationality.trim() || undefined,
      blood_type: bloodType.trim() || undefined,
      notes: notes.trim() || undefined,
    };
    try {
      if (isEdit && patient) {
        await appointmentApi.updatePatient(patient.id, body);
      } else {
        await appointmentApi.createPatient(body);
      }
      onSaved();
      onClose();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Kaydedilemedi');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40 p-0 sm:p-4">
      <form
        onSubmit={submit}
        className="w-full max-w-lg rounded-t-2xl sm:rounded-2xl bg-white p-5 shadow-xl space-y-3 max-h-[90vh] overflow-y-auto"
      >
        <h2 className="text-lg font-semibold text-slate-800">{isEdit ? 'Hasta kartı' : 'Yeni hasta'}</h2>
        <label className="block text-xs font-medium text-slate-600">
          Ad soyad
          <input required value={fullName} onChange={(e) => setFullName(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
        </label>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <label className="block text-xs font-medium text-slate-600">
            Telefon
            <input required={!isEdit} value={phone} onChange={(e) => setPhone(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" placeholder="05xx" />
          </label>
          <label className="block text-xs font-medium text-slate-600">
            TC
            <input value={nationalId} onChange={(e) => setNationalId(e.target.value)} maxLength={11} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
          </label>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <label className="block text-xs font-medium text-slate-600">
            Doğum tarihi
            <input type="date" value={birthDate} onChange={(e) => setBirthDate(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
          </label>
          <label className="block text-xs font-medium text-slate-600">
            Cinsiyet
            <select value={sex} onChange={(e) => setSex(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm">
              {SEX.map((o) => <option key={o.value || 'empty'} value={o.value}>{o.label}</option>)}
            </select>
          </label>
          <label className="block text-xs font-medium text-slate-600">
            Sigorta
            <select value={insuranceType} onChange={(e) => setInsuranceType(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm">
              {INSURANCE.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </label>
        </div>
        <label className="block text-xs font-medium text-slate-600">
          E-posta
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
        </label>
        <label className="block text-xs font-medium text-slate-600">
          Sigorta kurumu
          <input value={insuranceProvider} onChange={(e) => setInsuranceProvider(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
        </label>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <label className="block text-xs font-medium text-slate-600">
            Dosya no
            <input value={fileNumber} onChange={(e) => setFileNumber(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
          </label>
          <label className="block text-xs font-medium text-slate-600">
            Arşiv no
            <input value={archiveNumber} onChange={(e) => setArchiveNumber(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
          </label>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <label className="block text-xs font-medium text-slate-600">
            Meslek
            <input value={occupation} onChange={(e) => setOccupation(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
          </label>
          <label className="block text-xs font-medium text-slate-600">
            Uyruk
            <input value={nationality} onChange={(e) => setNationality(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
          </label>
          <label className="block text-xs font-medium text-slate-600">
            Kan grubu
            <input value={bloodType} onChange={(e) => setBloodType(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" placeholder="A+" />
          </label>
        </div>
        <label className="block text-xs font-medium text-slate-600">
          Adres
          <input value={address} onChange={(e) => setAddress(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
        </label>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <label className="block text-xs font-medium text-slate-600">
            İl
            <input value={city} onChange={(e) => setCity(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
          </label>
          <label className="block text-xs font-medium text-slate-600">
            İlçe
            <input value={district} onChange={(e) => setDistrict(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
          </label>
          <label className="block text-xs font-medium text-slate-600">
            Ülke
            <input value={country} onChange={(e) => setCountry(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
          </label>
        </div>
        <label className="block text-xs font-medium text-slate-600">
          Not
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
        </label>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>Vazgeç</Button>
          <Button type="submit" disabled={saving}>{saving ? 'Kaydediliyor…' : 'Kaydet'}</Button>
        </div>
      </form>
    </div>
  );
}
