'use client';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { format, addDays, startOfWeek, isSameDay, parseISO } from 'date-fns';
import { tr } from 'date-fns/locale';
import {
  ChevronLeft, ChevronRight,
  RefreshCw, ListPlus, User, Filter, X, Phone, Stethoscope, Plus, Pencil, MessageCircle,
} from 'lucide-react';
import { toast } from 'sonner';
import { appointmentApi, integrationApi, waitlistApi } from '@/lib/api-client';
import { PatientNotesPanel } from '@/components/dashboard/PatientNotesPanel';
import { useAuth } from '@/hooks/useAuth';
import type { Appointment, AppointmentCreateBody } from '@/types';

/* ── Types ────────────────────────────────────────────── */
interface Doctor {
  id: string;
  full_name: string;
  specialty: string | null;
}

/* ── Constants ────────────────────────────────────────── */
const HOUR_START = 9;
const HOUR_END   = 20;
const SLOT_HEIGHT = 60;                              // px per 30-min slot
const HOURS = Array.from({ length: HOUR_END - HOUR_START }, (_, i) => HOUR_START + i);

const DOCTOR_COLORS = [
  { bg: 'bg-yellow-100', border: 'border-yellow-300', text: 'text-yellow-900', hex: '#fef08a' },
  { bg: 'bg-pink-100',   border: 'border-pink-300',   text: 'text-pink-900',   hex: '#fbcfe8' },
  { bg: 'bg-blue-100',   border: 'border-blue-300',   text: 'text-blue-900',   hex: '#dbeafe' },
  { bg: 'bg-purple-100', border: 'border-purple-300', text: 'text-purple-900', hex: '#f3e8ff' },
  { bg: 'bg-green-100',  border: 'border-green-300',  text: 'text-green-900',  hex: '#dcfce7' },
  { bg: 'bg-orange-100', border: 'border-orange-300', text: 'text-orange-900', hex: '#ffedd5' },
  { bg: 'bg-cyan-100',   border: 'border-cyan-300',   text: 'text-cyan-900',   hex: '#cffafe' },
  { bg: 'bg-rose-100',   border: 'border-rose-300',   text: 'text-rose-900',   hex: '#ffe4e6' },
];

const STATUS_COLORS: Record<string, string> = {
  scheduled: 'bg-blue-500',  confirmed: 'bg-green-500', completed: 'bg-slate-400',
  cancelled: 'bg-red-500',   no_show:   'bg-orange-500',
};
const STATUS_LABELS: Record<string, string> = {
  scheduled: 'Planlandı', confirmed: 'Onaylı', completed: 'Tamamlandı',
  cancelled: 'İptal',     no_show:   'Gelmedi',
};

const SPECIALTY_OPTIONS = [
  'Ortodonti',
  'Pedodonti',
  'İmplant',
  'Cerrahi',
  'Endodonti',
  'Periodontoloji',
  'Protez',
  'Genel Diş Hekimliği',
];

function normalizeToTrLocal10(raw: string): string {
  const digits = raw.replace(/\D/g, '');
  if (digits.startsWith('90')) return digits.slice(2, 12);
  if (digits.startsWith('0')) return digits.slice(1, 11);
  return digits.slice(0, 10);
}

function formatTrPhoneInput(raw: string): string {
  const d = normalizeToTrLocal10(raw);
  const p1 = d.slice(0, 3);
  const p2 = d.slice(3, 6);
  const p3 = d.slice(6, 8);
  const p4 = d.slice(8, 10);
  return [p1, p2, p3, p4].filter(Boolean).join(' ');
}

function toTrE164(raw: string): string | null {
  const local = normalizeToTrLocal10(raw);
  if (local.length !== 10) return null;
  return `+90${local}`;
}

function getApiErrorMessage(err: unknown, fallback: string): string {
  const responseData = (err as { response?: { data?: { detail?: unknown } } })?.response?.data;
  const detail = responseData?.detail;

  if (typeof detail === 'string' && detail.trim()) return detail;

  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: unknown };
    if (typeof first?.msg === 'string' && first.msg.trim()) return first.msg;
  }

  if (detail && typeof detail === 'object') {
    const msg = (detail as { message?: unknown }).message;
    if (typeof msg === 'string' && msg.trim()) return msg;
  }

  if (err instanceof Error && err.message.trim()) return err.message;
  return fallback;
}

function PatientTypeToggle({
  value,
  onChange,
  disabled = false,
}: {
  value: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <div className="inline-flex rounded-lg border border-slate-200 bg-white p-1">
      <button
        type="button"
        disabled={disabled}
        onClick={() => onChange(false)}
        className={`rounded-md px-3 py-1.5 text-xs font-semibold transition-colors disabled:opacity-50 ${
          value ? 'text-slate-500 hover:bg-slate-50' : 'bg-red-600 text-white'
        }`}
      >
        Eski Hasta
      </button>
      <button
        type="button"
        disabled={disabled}
        onClick={() => onChange(true)}
        className={`rounded-md px-3 py-1.5 text-xs font-semibold transition-colors disabled:opacity-50 ${
          value ? 'bg-emerald-600 text-white' : 'text-slate-500 hover:bg-slate-50'
        }`}
      >
        Yeni Hasta
      </button>
    </div>
  );
}

/* ── Treatment Followup Toggle ────────────────────────── */
function TreatmentFollowupToggle({
  value,
  onChange,
  disabled = false,
}: {
  value: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <div className="inline-flex rounded-lg border border-slate-200 bg-white p-1">
      <button
        type="button"
        disabled={disabled}
        onClick={() => onChange(false)}
        className={`rounded-md px-3 py-1.5 text-xs font-semibold transition-colors disabled:opacity-50 ${
          value ? 'text-slate-500 hover:bg-slate-50' : 'bg-red-600 text-white'
        }`}
      >
        Kapalı
      </button>
      <button
        type="button"
        disabled={disabled}
        onClick={() => onChange(true)}
        className={`rounded-md px-3 py-1.5 text-xs font-semibold transition-colors disabled:opacity-50 ${
          value ? 'bg-emerald-600 text-white' : 'text-slate-500 hover:bg-slate-50'
        }`}
      >
        Açık
      </button>
    </div>
  );
}

/* ── Doctor filter dropdown ───────────────────────────── */
function DoctorFilter({
  doctors, selected, onChange,
}: { doctors: Doctor[]; selected: Set<string>; onChange: (s: Set<string>) => void }) {
  const [open, setOpen] = useState(false);

  const toggle = (id: string) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id); else next.add(id);
    onChange(next);
  };

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 shadow-sm"
      >
        <Filter className="h-4 w-4 text-slate-400" />
        Diş Hekimleri
        {selected.size < doctors.length && (
          <span className="rounded-full bg-blue-600 px-1.5 py-0.5 text-[10px] font-bold text-white">
            {selected.size}
          </span>
        )}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} />
          <div className="absolute left-0 top-full z-40 mt-1 w-64 rounded-xl border border-slate-200 bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-100 px-3 py-2">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Doktor Seç</span>
              <div className="flex gap-1">
                <button onClick={() => onChange(new Set(doctors.map(d => d.id)))} className="rounded px-2 py-0.5 text-[10px] font-medium text-blue-600 hover:bg-blue-50">Tümü</button>
                <button onClick={() => onChange(new Set())} className="rounded px-2 py-0.5 text-[10px] font-medium text-slate-500 hover:bg-slate-50">Temizle</button>
              </div>
            </div>
            <div className="max-h-64 overflow-y-auto p-2 space-y-0.5">
              {doctors.map((doc, i) => {
                const c = DOCTOR_COLORS[i % DOCTOR_COLORS.length];
                return (
                  <label key={doc.id} className={`flex items-center gap-2.5 rounded-lg px-2.5 py-2 cursor-pointer transition-colors ${selected.has(doc.id) ? 'bg-slate-50' : 'hover:bg-slate-50'}`}>
                    <input type="checkbox" checked={selected.has(doc.id)} onChange={() => toggle(doc.id)} className="h-3.5 w-3.5 rounded border-slate-300 text-blue-600" />
                    <div className="h-3 w-3 rounded-full shrink-0" style={{ backgroundColor: c.hex }} />
                    <span className="text-sm text-slate-700 truncate">{doc.full_name}</span>
                  </label>
                );
              })}
              {doctors.length === 0 && <p className="py-4 text-center text-xs text-slate-400">Doktor bulunamadı</p>}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

/* ── Appointment detail modal ─────────────────────────── */
function AppointmentDetail({
  appt, doctors, canEdit, onClose, onAddToWaitlist, addingToWaitlist, onUpdated,
}: {
  appt: Appointment;
  doctors: Doctor[];
  canEdit: boolean;
  onClose: () => void;
  onAddToWaitlist: (a: Appointment) => void;
  addingToWaitlist: boolean;
  onUpdated: () => void;
}) {
  const dt = parseISO(appt.scheduled_at);
  const [editMode, setEditMode] = useState(false);
  const [saving, setSaving] = useState(false);
  const [reachingOut, setReachingOut] = useState(false);

  const [doctorId, setDoctorId] = useState(appt.doctor_id);
  const [typeValue, setTypeValue] = useState(appt.type ?? '');
  const [dateValue, setDateValue] = useState(format(dt, 'yyyy-MM-dd'));
  const [isNewPatient, setIsNewPatient] = useState(Boolean(appt.is_new_patient));
  const [treatmentFollowupEnabled, setTreatmentFollowupEnabled] = useState(Boolean(appt.treatment_follow_up_enabled));
  const [startTime, setStartTime] = useState(format(dt, 'HH:mm'));
  const [endTime, setEndTime] = useState(() => {
    const d = parseISO(appt.scheduled_at);
    const duration = appt.duration_minutes || 30;
    const endD = new Date(d.getTime() + duration * 60000);
    return format(endD, 'HH:mm');
  });
  const [phoneInput, setPhoneInput] = useState(formatTrPhoneInput(appt.patient_phone ?? ''));

  async function handleSave() {
    const phoneE164 = toTrE164(phoneInput);
    if (!phoneE164) {
      toast.error('Telefon +90 formatinda olmali (örn: 511 111 11 11)');
      return;
    }
    if (!doctorId) {
      toast.error('Lutfen doktor secin');
      return;
    }

    const startScheduled = new Date(`${dateValue}T${startTime}:00`);
    const endScheduled = new Date(`${dateValue}T${endTime}:00`);
    
    if (Number.isNaN(startScheduled.getTime()) || Number.isNaN(endScheduled.getTime())) {
      toast.error('Gecerli tarih/saat girin');
      return;
    }
    
    if (endScheduled <= startScheduled) {
      toast.error('Bitiş saati başlangıç saatinden sonra olmalıdır');
      return;
    }
    
    const durationMinutes = (endScheduled.getTime() - startScheduled.getTime()) / 60000;

    if (durationMinutes < 15) {
      toast.error('Randevu süresi en az 15 dakika olmalıdır');
      return;
    }

    if (durationMinutes > 240) {
      toast.error('Randevu süresi en fazla 240 dakika olabilir');
      return;
    }

    const selectedDoctor = doctors.find((d) => d.id === doctorId);

    try {
      setSaving(true);
      await appointmentApi.update(appt.id, {
        doctor_id: doctorId,
        scheduled_at: startScheduled.toISOString(),
        duration_minutes: durationMinutes,
        is_new_patient: isNewPatient,
        treatment_follow_up_enabled: treatmentFollowupEnabled,
        type: typeValue.trim() || null,
        specialty: selectedDoctor?.specialty ?? appt.specialty,
      });

      await appointmentApi.updatePatient(appt.patient_id, {
        phone: phoneE164,
      });

      toast.success('Randevu bilgileri guncellendi');
      setEditMode(false);
      onUpdated();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Guncelleme basarisiz'));
    } finally {
      setSaving(false);
    }
  }

  async function handlePostOpReachout() {
    try {
      setReachingOut(true);
      await integrationApi.triggerPostOpReachout(appt.id);
      toast.success('Tedavi sonrasi ulasim mesaji kuyruga alindi');
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Tedavi sonrasi ulasim tetiklenemedi'));
    } finally {
      setReachingOut(false);
    }
  }

  async function handleDelete() {
    if (!confirm('Bu randevuyu silmek istediğinize emin misiniz?')) return;
    try {
      setSaving(true);
      await appointmentApi.delete(appt.id);
      toast.success('Randevu silindi');
      onUpdated();
      onClose();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Silme başarısız'));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-2xl rounded-2xl bg-white shadow-2xl overflow-hidden max-h-[90vh] flex flex-col">
        <div className="bg-gradient-to-r from-blue-600 to-blue-700 px-5 py-4 flex items-center justify-between">
          <h3 className="text-base font-semibold text-white">Randevu Detayı</h3>
          <button onClick={onClose} className="rounded-full p-1 text-white/70 hover:text-white hover:bg-white/10"><X className="h-4 w-4" /></button>
        </div>

        <div className="p-5 space-y-4 overflow-y-auto">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100"><User className="h-5 w-5 text-blue-600" /></div>
            <div>
              <p className="text-sm font-semibold text-slate-900">{appt.patient_name ?? 'Hasta'}</p>
              <p className="text-xs text-slate-500">{appt.doctor_name ?? 'Hekim atanmadı'}</p>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
              <div className="mb-2 flex items-center gap-2 text-emerald-700">
                <Phone className="h-4 w-4" />
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em]">Telefon</p>
              </div>
              {editMode ? (
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-emerald-800">+90</span>
                    <input
                      value={phoneInput}
                      onChange={(e) => setPhoneInput(formatTrPhoneInput(e.target.value))}
                      placeholder="511 111 11 11"
                      className="w-full rounded-lg border border-emerald-200 bg-white px-3 py-2 text-sm outline-none focus:border-emerald-400"
                    />
                  </div>
                  <p className="text-[11px] text-emerald-700">Sadece 10 haneli GSM numarasi girin.</p>
                </div>
              ) : (
                <p className="text-base font-semibold text-emerald-950">
                  {appt.patient_phone || 'Telefon bilgisi yok'}
                </p>
              )}
            </div>
            <div className="rounded-xl border border-blue-200 bg-blue-50 p-4">
              <div className="mb-2 flex items-center gap-2 text-blue-700">
                <Stethoscope className="h-4 w-4" />
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em]">İşlem Tipi</p>
              </div>
              {editMode ? (
                <input
                  value={typeValue}
                  onChange={(e) => setTypeValue(e.target.value)}
                  placeholder="Orn. Kontrol"
                  className="w-full rounded-lg border border-blue-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-400"
                />
              ) : (
                <p className="text-base font-semibold text-blue-950">
                  {appt.type || 'İşlem tipi girilmemiş'}
                </p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
              <div className="rounded-lg bg-slate-50 p-3">
                <p className="text-[10px] uppercase tracking-wide text-slate-400 mb-1">Hasta Tipi</p>
                {editMode ? (
                  <PatientTypeToggle value={isNewPatient} onChange={setIsNewPatient} disabled={saving} />
                ) : (
                  <span
                    className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${
                      appt.is_new_patient ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'
                    }`}
                  >
                    {appt.is_new_patient ? 'Yeni Hasta' : 'Eski Hasta'}
                  </span>
                )}
              </div>

              <div className="rounded-lg bg-slate-50 p-3">
                <p className="text-[10px] uppercase tracking-wide text-slate-400 mb-1">Tedavi Kontrolü</p>
                {editMode ? (
                  <TreatmentFollowupToggle value={treatmentFollowupEnabled} onChange={setTreatmentFollowupEnabled} disabled={saving} />
                ) : (
                  <span
                    className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${
                      appt.treatment_follow_up_enabled ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'
                    }`}
                  >
                    {appt.treatment_follow_up_enabled ? 'Açık' : 'Kapalı'}
                  </span>
                )}
              </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg bg-slate-50 p-3">
              <p className="text-[10px] uppercase tracking-wide text-slate-400 mb-1">Tarih</p>
              {editMode ? (
                <input
                  type="date"
                  value={dateValue}
                  onChange={(e) => setDateValue(e.target.value)}
                  className="w-full rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-sm"
                />
              ) : (
                <p className="text-sm font-medium text-slate-800">{format(dt, 'd MMMM yyyy', { locale: tr })}</p>
              )}
            </div>
            {editMode ? (
              <div>
                <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">Randevu Saati</label>
                <div className="grid gap-2 grid-cols-2">
                  <div>
                    <label className="text-xs text-slate-500 mb-1 block">Başlangıç</label>
                    <input
                      type="time"
                      value={startTime}
                      onChange={(e) => setStartTime(e.target.value)}
                      className="w-full rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-sm outline-none focus:border-blue-400"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 mb-1 block">Bitiş</label>
                    <input
                      type="time"
                      value={endTime}
                      onChange={(e) => setEndTime(e.target.value)}
                      className="w-full rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-sm outline-none focus:border-blue-400"
                    />
                  </div>
                </div>
              </div>
            ) : (
              <div className="rounded-lg bg-slate-50 p-3">
                <p className="text-[10px] uppercase tracking-wide text-slate-400 mb-1">Saat</p>
                <p className="text-sm font-medium text-slate-800">{format(dt, 'HH:mm')}</p>
              </div>
            )}
            <div className="rounded-lg bg-slate-50 p-3">
              <p className="text-[10px] uppercase tracking-wide text-slate-400 mb-1">Doktor</p>
              {editMode ? (
                <select
                  value={doctorId}
                  onChange={(e) => setDoctorId(e.target.value)}
                  className="w-full rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-sm"
                >
                  <option value="">Doktor secin</option>
                  {doctors.map((d) => (
                    <option key={d.id} value={d.id}>{d.full_name}</option>
                  ))}
                </select>
              ) : (
                <p className="text-sm font-medium text-slate-800">{appt.doctor_name ?? '—'}</p>
              )}
            </div>
            <div className="rounded-lg bg-slate-50 p-3">
              <p className="text-[10px] uppercase tracking-wide text-slate-400 mb-1">Durum</p>
              <div className="flex items-center gap-1.5">
                <span className={`h-2 w-2 rounded-full ${STATUS_COLORS[appt.status]}`} />
                <p className="text-sm font-medium text-slate-800">{STATUS_LABELS[appt.status]}</p>
              </div>
            </div>
          </div>

          {appt.notes && (
            <div className="rounded-lg bg-slate-50 p-3">
              <p className="text-[10px] uppercase tracking-wide text-slate-400 mb-1">Notlar</p>
              <p className="text-sm text-slate-700">{appt.notes}</p>
            </div>
          )}

          {/* Hasta Not Defteri — kalıcı, patient_notes tablosunda */}
          <PatientNotesPanel
            patientId={appt.patient_id}
            patientName={appt.patient_name ?? undefined}
            canAdd={true}
            defaultNoteType="treatment"
          />

          <div className="flex gap-2 pt-1">
            {canEdit && (
              <button
                onClick={editMode ? handleSave : () => setEditMode(true)}
                disabled={saving}
                className="inline-flex items-center justify-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-4 py-2.5 text-sm font-medium text-blue-700 hover:bg-blue-100 disabled:opacity-50"
              >
                <Pencil className="h-4 w-4" />
                {saving ? 'Kaydediliyor...' : editMode ? 'Kaydet' : 'Duzenle'}
              </button>
            )}

            {editMode && canEdit && (
              <button
                onClick={handleDelete}
                disabled={saving}
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-red-600 hover:bg-red-700 text-white px-4 py-2.5 text-sm font-medium disabled:opacity-50"
              >
                {saving ? 'Siliniyor...' : 'Sil'}
              </button>
            )}

            {appt.status === 'completed' && (
              <button
                onClick={handlePostOpReachout}
                disabled={reachingOut}
                className="inline-flex items-center justify-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-sm font-medium text-emerald-700 hover:bg-emerald-100 disabled:opacity-50"
              >
                <MessageCircle className="h-4 w-4" />
                {reachingOut ? 'Gonderiliyor...' : 'Tedavi Sonrasi Ulas'}
              </button>
            )}

            <button
              onClick={() => onAddToWaitlist(appt)}
              disabled={addingToWaitlist || appt.status === 'cancelled'}
              className="flex-1 flex items-center justify-center gap-2 rounded-lg bg-amber-500 px-4 py-2.5 text-sm font-medium text-white hover:bg-amber-600 disabled:opacity-50 transition-colors"
            >
              <ListPlus className="h-4 w-4" />
              {addingToWaitlist ? 'Ekleniyor…' : 'Yedek Listeye Ekle'}
            </button>
            <button onClick={onClose} className="rounded-lg border border-slate-200 px-4 py-2.5 text-sm font-medium text-slate-600 hover:bg-slate-50">Kapat</button>
          </div>
        </div>
      </div>
    </div>
  );
}

function CreateAppointmentModal({
  doctors,
  onClose,
  onCreated,
}: {
  doctors: Doctor[];
  onClose: () => void;
  onCreated: () => void;
}) {
  const [doctorId, setDoctorId] = useState('');
  const [specialty, setSpecialty] = useState('Genel Diş Hekimliği');
  const [dateValue, setDateValue] = useState(format(new Date(), 'yyyy-MM-dd'));
  const [isNewPatient, setIsNewPatient] = useState(false);
  const [treatmentFollowupEnabled, setTreatmentFollowupEnabled] = useState(false);
  const [startTime, setStartTime] = useState('09:00');
  const [endTime, setEndTime] = useState('09:30');
  const [type, setType] = useState('');
  const [notes, setNotes] = useState('');
  const [newPatientName, setNewPatientName] = useState('');
  const [newPatientPhone, setNewPatientPhone] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!doctorId) return;
    const selectedDoctor = doctors.find((d) => d.id === doctorId);
    if (selectedDoctor?.specialty && SPECIALTY_OPTIONS.includes(selectedDoctor.specialty)) {
      setSpecialty(selectedDoctor.specialty);
    }
  }, [doctorId, doctors]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const fullName = newPatientName.trim();
    const phone = toTrE164(newPatientPhone);

    if (!fullName) {
      toast.error('Hasta adi zorunlu');
      return;
    }
    if (!phone) {
      toast.error('Telefon +90 formatinda olmali (10 hane girin)');
      return;
    }
    if (!doctorId) {
      toast.error('Lutfen bir doktor secin');
      return;
    }
    if (!specialty) {
      toast.error('Lutfen bir brans secin');
      return;
    }

    const startScheduled = new Date(`${dateValue}T${startTime}:00`);
    const endScheduled = new Date(`${dateValue}T${endTime}:00`);
    
    if (Number.isNaN(startScheduled.getTime()) || Number.isNaN(endScheduled.getTime())) {
      toast.error('Gecerli tarih/saat girin');
      return;
    }
    
    if (endScheduled <= startScheduled) {
      toast.error('Bitiş saati başlangıç saatinden sonra olmalıdır');
      return;
    }

    const durationMinutes = (endScheduled.getTime() - startScheduled.getTime()) / 60000;
    if (durationMinutes < 15) {
      toast.error('Randevu süresi en az 15 dakika olmalıdır');
      return;
    }

    if (durationMinutes > 240) {
      toast.error('Randevu süresi en fazla 240 dakika olabilir');
      return;
    }

    try {
      setSaving(true);
      const patientRes = await appointmentApi.createPatient({ full_name: fullName, phone });
      const patient = patientRes.data as { id: string };

      const payload: AppointmentCreateBody = {
        patient_id: patient.id,
        doctor_id: doctorId,
        specialty,
        scheduled_at: startScheduled.toISOString(),
        type: type.trim() || undefined,
        notes: notes.trim() || undefined,
        duration_minutes: durationMinutes,
        is_new_patient: isNewPatient,
        treatment_follow_up_enabled: treatmentFollowupEnabled,
      };

      await appointmentApi.create(payload);
      toast.success('Randevu manuel olarak eklendi');
      onCreated();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Randevu olusturulamadi'));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-2xl rounded-2xl bg-white shadow-2xl overflow-hidden">
        <div className="flex items-center justify-between bg-gradient-to-r from-slate-900 to-slate-800 px-5 py-4">
          <h3 className="text-base font-semibold text-white">Manuel Randevu Ekle</h3>
          <button onClick={onClose} className="rounded-full p-1 text-white/70 hover:text-white hover:bg-white/10">
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={submit} className="space-y-4 p-5">
          <div>
            <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">Randevu Olustur</label>
            <div className="grid gap-3 md:grid-cols-2">
              <input
                value={newPatientName}
                onChange={(e) => setNewPatientName(e.target.value)}
                placeholder="Hasta adi"
                className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-blue-500"
              />
              <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2.5 focus-within:border-blue-500">
                <span className="text-sm font-semibold text-blue-700">+90</span>
                <input
                  type="tel"
                  inputMode="numeric"
                  value={newPatientPhone}
                  onChange={(e) => setNewPatientPhone(formatTrPhoneInput(e.target.value))}
                  placeholder="511 111 11 11"
                  className="w-full text-sm outline-none"
                />
                </div>
              </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">Hasta Tipi</label>
              <PatientTypeToggle value={isNewPatient} onChange={setIsNewPatient} disabled={saving} />
            </div>

            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">Tedavi Kontrolü</label>
              <TreatmentFollowupToggle value={treatmentFollowupEnabled} onChange={setTreatmentFollowupEnabled} disabled={saving} />
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">Doktor</label>
              <select
                value={doctorId}
                onChange={(e) => setDoctorId(e.target.value)}
                className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-blue-500"
              >
                <option value="">Doktor secin</option>
                {doctors.map((d) => (
                  <option key={d.id} value={d.id}>{d.full_name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">Brans</label>
              <select
                value={specialty}
                onChange={(e) => setSpecialty(e.target.value)}
                className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-blue-500"
              >
                {SPECIALTY_OPTIONS.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
            <div className="grid gap-3 md:grid-cols-[minmax(180px,220px)_1fr] md:col-span-2">
              <div>
                <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">Tarih</label>
                <input
                  type="date"
                  value={dateValue}
                  onChange={(e) => setDateValue(e.target.value)}
                  className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">Randevu Saati</label>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-xs text-slate-500 mb-1 block">Başlangıç</label>
                    <input
                      type="time"
                      step={60}
                      value={startTime}
                      onChange={(e) => setStartTime(e.target.value)}
                      className="w-full min-w-[120px] rounded-lg border border-slate-200 px-3 py-2.5 text-sm font-medium tabular-nums outline-none focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 mb-1 block">Bitiş</label>
                    <input
                      type="time"
                      step={60}
                      value={endTime}
                      onChange={(e) => setEndTime(e.target.value)}
                      className="w-full min-w-[120px] rounded-lg border border-slate-200 px-3 py-2.5 text-sm font-medium tabular-nums outline-none focus:border-blue-500"
                    />
                  </div>
                </div>
              </div>
            </div>
            <div className="md:col-span-2">
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">Islem Tipi</label>
              <input
                value={type}
                onChange={(e) => setType(e.target.value)}
                placeholder="Orn. Kontrol"
                className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-blue-500"
              />
            </div>
            <div className="md:col-span-2">
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">Not</label>
              <input
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Opsiyonel"
                className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={onClose} className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50">Iptal</button>
            <button type="submit" disabled={saving} className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60">
              <Plus className="h-4 w-4" />
              {saving ? 'Kaydediliyor...' : 'Randevu Ekle'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/* ── Overlap layout computation for week view ─────────── */
interface LayoutInfo { appt: Appointment; colIndex: number; colCount: number }

function computeOverlapLayout(appts: Appointment[]): LayoutInfo[] {
  if (appts.length === 0) return [];
  // Sort by time
  const sorted = [...appts].sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at));
  // Each appointment occupies a 30-min slot
  const getSlot = (a: Appointment) => {
    const d = parseISO(a.scheduled_at);
    return d.getHours() * 60 + d.getMinutes();
  };
  const DURATION = 30; // minutes

  // Group overlapping appointments
  const groups: Appointment[][] = [];
  let currentGroup: Appointment[] = [sorted[0]];
  let groupEnd = getSlot(sorted[0]) + DURATION;

  for (let i = 1; i < sorted.length; i++) {
    const start = getSlot(sorted[i]);
    if (start < groupEnd) {
      currentGroup.push(sorted[i]);
      groupEnd = Math.max(groupEnd, start + DURATION);
    } else {
      groups.push(currentGroup);
      currentGroup = [sorted[i]];
      groupEnd = start + DURATION;
    }
  }
  groups.push(currentGroup);

  // Assign column index within each group
  const result: LayoutInfo[] = [];
  for (const group of groups) {
    const count = group.length;
    group.forEach((appt, idx) => {
      result.push({ appt, colIndex: idx, colCount: count });
    });
  }
  return result;
}

/* ── Appointment block on the calendar ────────────────── */
function ApptBlock({
  appt, colorIdx, onClick, colIndex = 0, colCount = 1,
}: {
  appt: Appointment; colorIdx: number; onClick: () => void;
  colIndex?: number; colCount?: number;
}) {
  const dt = parseISO(appt.scheduled_at);
  const top = ((dt.getHours() * 60 + dt.getMinutes()) - HOUR_START * 60) / 30 * SLOT_HEIGHT;
  const color = DOCTOR_COLORS[colorIdx % DOCTOR_COLORS.length];
  const isCancelled = appt.status === 'cancelled';
  const widthPct = 100 / colCount;
  const leftPct = colIndex * widthPct;

  return (
    <button
      onClick={onClick}
      className={`absolute rounded-lg border ${color.border} ${color.bg} px-1.5 py-1 text-left transition-all hover:shadow-md hover:scale-[1.01] overflow-hidden ${isCancelled ? 'opacity-40 line-through' : ''}`}
      style={{
        top: `${top}px`,
        height: `${SLOT_HEIGHT - 2}px`,
        minHeight: '28px',
        left: `calc(${leftPct}% + 1px)`,
        width: `calc(${widthPct}% - 2px)`,
      }}
      title={`${appt.patient_name ?? 'Hasta'} – ${format(dt, 'HH:mm')}`}
    >
      <p className={`text-[10px] font-bold ${color.text} leading-tight truncate`}>
        {format(dt, 'HH:mm')} {appt.patient_name ?? 'Hasta'}
      </p>
      {SLOT_HEIGHT > 40 && appt.type && (
        <p className={`text-[9px] ${color.text} opacity-70 truncate`}>{appt.type}</p>
      )}
    </button>
  );
}

/* ── Main page ────────────────────────────────────────── */
export default function AppointmentsPage() {
  const { user } = useAuth();
  const [date, setDate]               = useState(() => new Date());
  const [viewMode, setViewMode]       = useState<'day' | 'week'>('day');
  const [doctors, setDoctors]         = useState<Doctor[]>([]);
  const [selectedDoctors, setSelectedDoctors] = useState<Set<string>>(new Set());
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading]         = useState(true);
  const [selectedAppt, setSelectedAppt] = useState<Appointment | null>(null);
  const [addingWaitlist, setAddingWaitlist] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);

  const canEditAppointments = useMemo(() => {
    if (!user) return false;
    if (user.role === 'owner' || user.role === 'super_admin') return true;
    return (user.allowed_pages ?? []).includes('appointments_write');
  }, [user]);

  /* load doctors once */
  useEffect(() => {
    appointmentApi.doctors().then((res) => {
      const docs: Doctor[] = res.data.doctors ?? [];
      setDoctors(docs);
      setSelectedDoctors(new Set(docs.map(d => d.id)));
    }).catch(() => {});
  }, []);

  /* load appointments for current date / week */
  const fetchAppointments = useCallback(async () => {
    setLoading(true);
    try {
      let dateFrom: string, dateTo: string;
      if (viewMode === 'day') {
        dateFrom = format(date, 'yyyy-MM-dd');
        dateTo   = format(addDays(date, 1), 'yyyy-MM-dd');
      } else {
        const ws = startOfWeek(date, { weekStartsOn: 1 });
        dateFrom = format(ws, 'yyyy-MM-dd');
        dateTo   = format(addDays(ws, 7), 'yyyy-MM-dd');
      }
      const res = await appointmentApi.list({ date_from: dateFrom, date_to: dateTo });
      const raw = res.data;
      setAppointments(Array.isArray(raw) ? raw : (raw?.items ?? []));
    } catch { toast.error('Randevular yüklenemedi'); }
    finally  { setLoading(false); }
  }, [date, viewMode]);

  useEffect(() => { fetchAppointments(); }, [fetchAppointments]);

  /* navigation helpers */
  const step = viewMode === 'day' ? 1 : 7;
  const prevDay  = () => setDate(d => addDays(d, -step));
  const nextDay  = () => setDate(d => addDays(d, step));
  const goToday  = () => setDate(new Date());

  /* filtered / grouped data */
  const filteredAppts = useMemo(() => appointments.filter(a => selectedDoctors.has(a.doctor_id)), [appointments, selectedDoctors]);
  const doctorColumns = useMemo(() => doctors.filter(d => selectedDoctors.has(d.id)), [doctors, selectedDoctors]);
  const doctorColorMap = useMemo(() => { const m = new Map<string, number>(); doctors.forEach((d, i) => m.set(d.id, i)); return m; }, [doctors]);

  /* waitlist action */
  async function handleAddToWaitlist(appt: Appointment) {
    setAddingWaitlist(true);
    try {
      // Specialty: appointment'ın kendi specialty'si, yoksa doktorun uzmanlığı, yoksa genel
      const doc = doctors.find(d => d.id === appt.doctor_id);
      const specialty = appt.specialty || doc?.specialty || 'Genel Diş Hekimliği';
      await waitlistApi.add({ patient_id: appt.patient_id, doctor_id: appt.doctor_id, specialty });
      toast.success(`${appt.patient_name ?? 'Hasta'} yedek listeye eklendi`);
      setSelectedAppt(null);
    } catch (err: unknown) {
      const msg = getApiErrorMessage(err, 'Yedek listeye eklenemedi');
      toast.error(msg === 'Bu hasta zaten bu branşta yedek listede' ? msg : 'Yedek listeye eklenemedi');
    } finally { setAddingWaitlist(false); }
  }

  const weekStart = startOfWeek(date, { weekStartsOn: 1 });
  const weekDays  = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));
  const gridHeight = HOURS.length * SLOT_HEIGHT * 2;

  /* ── Render ──────────────────────────────────────────── */
  return (
    <div className="flex h-full flex-col space-y-4">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <button onClick={prevDay} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><ChevronLeft className="h-4 w-4" /></button>
          <button onClick={goToday} className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50">Bugün</button>
          <button onClick={nextDay} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><ChevronRight className="h-4 w-4" /></button>
          <h2 className="ml-2 text-lg font-bold text-slate-800">
            {viewMode === 'day'
              ? format(date, 'd MMMM yyyy, EEEE', { locale: tr })
              : `${format(weekStart, 'd MMM', { locale: tr })} – ${format(addDays(weekStart, 6), 'd MMM yyyy', { locale: tr })}`}
          </h2>
        </div>

        <div className="flex items-center gap-2">
          <DoctorFilter doctors={doctors} selected={selectedDoctors} onChange={setSelectedDoctors} />
          {canEditAppointments && (
            <button
              onClick={() => setShowCreateModal(true)}
              className="inline-flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-100"
            >
              <Plus className="h-4 w-4" />
              Manuel Randevu
            </button>
          )}
          <div className="flex rounded-lg border border-slate-200 bg-white overflow-hidden">
            {(['day', 'week'] as const).map(m => (
              <button key={m} onClick={() => setViewMode(m)} className={`px-3 py-1.5 text-xs font-semibold transition-colors ${viewMode === m ? 'bg-blue-600 text-white' : 'text-slate-600 hover:bg-slate-50'}`}>
                {m === 'day' ? 'Gün' : 'Hafta'}
              </button>
            ))}
          </div>
          <button onClick={fetchAppointments} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100">
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Calendar */}
      <div className="flex-1 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        {viewMode === 'day' ? (
          /* ─── Day view: doctor columns ──────────── */
          <div className="flex h-full flex-col">
            {/* column headers */}
            <div className="flex border-b border-slate-200 bg-slate-50 sticky top-0 z-10">
              <div className="w-16 shrink-0 border-r border-slate-200" />
              {doctorColumns.length > 0 ? doctorColumns.map((doc) => {
                const c = DOCTOR_COLORS[(doctorColorMap.get(doc.id) ?? 0) % DOCTOR_COLORS.length];
                return (
                  <div key={doc.id} className="flex-1 min-w-[180px] border-r border-slate-100 px-3 py-2.5 text-center">
                    <div className="flex items-center justify-center gap-2">
                      <div className="h-3 w-3 rounded-full shrink-0" style={{ backgroundColor: c.hex }} />
                      <p className="text-sm font-semibold text-slate-700 truncate">{doc.full_name}</p>
                    </div>
                    {doc.specialty && <p className="text-[10px] text-slate-400 mt-0.5">{doc.specialty}</p>}
                  </div>
                );
              }) : (
                <div className="flex-1 px-3 py-2.5 text-center text-sm text-slate-400">Doktor seçin</div>
              )}
            </div>

            {/* time grid */}
            <div className="flex-1 overflow-auto">
              <div className="flex" style={{ minHeight: `${gridHeight}px` }}>
                {/* time gutter */}
                <div className="w-16 shrink-0 border-r border-slate-200 relative">
                  {HOURS.map(h => (
                    <div key={h} className="absolute left-0 right-0 flex items-start justify-end pr-2" style={{ top: `${(h - HOUR_START) * SLOT_HEIGHT * 2}px` }}>
                      <span className="text-[10px] font-medium text-slate-400 -mt-1.5">{String(h).padStart(2, '0')}:00</span>
                    </div>
                  ))}
                </div>

                {/* doctor columns */}
                {doctorColumns.map(doc => {
                  const docAppts = filteredAppts.filter(a => a.doctor_id === doc.id && isSameDay(parseISO(a.scheduled_at), date));
                  const idx = doctorColorMap.get(doc.id) ?? 0;
                  return (
                    <div key={doc.id} className="flex-1 min-w-[180px] border-r border-slate-50 relative">
                      {HOURS.map(h => (
                        <div key={h}>
                          <div className="absolute left-0 right-0 border-t border-slate-100" style={{ top: `${(h - HOUR_START) * SLOT_HEIGHT * 2}px` }} />
                          <div className="absolute left-0 right-0 border-t border-slate-50" style={{ top: `${(h - HOUR_START) * SLOT_HEIGHT * 2 + SLOT_HEIGHT}px` }} />
                        </div>
                      ))}
                      {docAppts.map(appt => (
                        <ApptBlock key={appt.id} appt={appt} colorIdx={idx} onClick={() => setSelectedAppt(appt)} />
                      ))}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        ) : (
          /* ─── Week view ────────────────────────── */
          <div className="flex h-full flex-col">
            <div className="flex border-b border-slate-200 bg-slate-50 sticky top-0 z-10">
              <div className="w-16 shrink-0 border-r border-slate-200" />
              {weekDays.map(day => {
                const isToday = isSameDay(day, new Date());
                return (
                  <div key={day.toISOString()} onClick={() => { setDate(day); setViewMode('day'); }} className={`flex-1 min-w-[120px] border-r border-slate-100 px-2 py-2.5 text-center cursor-pointer hover:bg-blue-50 ${isToday ? 'bg-blue-50' : ''}`}>
                    <p className="text-[10px] uppercase tracking-wide text-slate-400">{format(day, 'EEEE', { locale: tr })}</p>
                    <p className={`text-lg font-bold ${isToday ? 'text-blue-600' : 'text-slate-700'}`}>{format(day, 'd')}</p>
                  </div>
                );
              })}
            </div>

            <div className="flex-1 overflow-auto">
              <div className="flex" style={{ minHeight: `${gridHeight}px` }}>
                <div className="w-16 shrink-0 border-r border-slate-200 relative">
                  {HOURS.map(h => (
                    <div key={h} className="absolute left-0 right-0 flex items-start justify-end pr-2" style={{ top: `${(h - HOUR_START) * SLOT_HEIGHT * 2}px` }}>
                      <span className="text-[10px] font-medium text-slate-400 -mt-1.5">{String(h).padStart(2, '0')}:00</span>
                    </div>
                  ))}
                </div>
                {weekDays.map(day => {
                  const dayAppts = filteredAppts.filter(a => isSameDay(parseISO(a.scheduled_at), day));
                  const layoutItems = computeOverlapLayout(dayAppts);
                  return (
                    <div key={day.toISOString()} className="flex-1 min-w-[120px] border-r border-slate-50 relative">
                      {HOURS.map(h => (
                        <div key={h}>
                          <div className="absolute left-0 right-0 border-t border-slate-100" style={{ top: `${(h - HOUR_START) * SLOT_HEIGHT * 2}px` }} />
                          <div className="absolute left-0 right-0 border-t border-slate-50" style={{ top: `${(h - HOUR_START) * SLOT_HEIGHT * 2 + SLOT_HEIGHT}px` }} />
                        </div>
                      ))}
                      {layoutItems.map(({ appt, colIndex, colCount }) => (
                        <ApptBlock key={appt.id} appt={appt} colorIdx={doctorColorMap.get(appt.doctor_id) ?? 0} onClick={() => setSelectedAppt(appt)} colIndex={colIndex} colCount={colCount} />
                      ))}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500">
        <span className="font-medium text-slate-600">Durum:</span>
        {Object.entries(STATUS_LABELS).map(([k, v]) => (
          <div key={k} className="flex items-center gap-1.5"><span className={`h-2.5 w-2.5 rounded-full ${STATUS_COLORS[k]}`} />{v}</div>
        ))}
        <span className="ml-4 text-slate-400">{filteredAppts.length} randevu gösteriliyor</span>
      </div>

      {/* Detail modal */}
      {selectedAppt && (
        <AppointmentDetail
          appt={selectedAppt}
          doctors={doctors}
          canEdit={canEditAppointments}
          onClose={() => setSelectedAppt(null)}
          onAddToWaitlist={handleAddToWaitlist}
          addingToWaitlist={addingWaitlist}
          onUpdated={() => {
            setSelectedAppt(null);
            fetchAppointments();
          }}
        />
      )}

      {showCreateModal && (
        <CreateAppointmentModal
          doctors={doctors}
          onClose={() => setShowCreateModal(false)}
          onCreated={() => {
            setShowCreateModal(false);
            fetchAppointments();
          }}
        />
      )}
    </div>
  );
}
