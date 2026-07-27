'use client';
import { useState, useMemo } from 'react';
import {
  FileText, Stethoscope, Bot, StickyNote, ChevronDown, ChevronUp,
  Calendar as CalendarIcon, User,
} from 'lucide-react';
import { format, parseISO, startOfDay, startOfWeek, startOfMonth, startOfYear } from 'date-fns';
import { tr } from 'date-fns/locale';
import { useMyTreatmentLog, useAllDoctorsLog } from '@/hooks/usePatientNotes';
import type { PatientNote, PatientNotesSummary, NoteType } from '@/types';

type GroupBy = 'day' | 'week' | 'month' | 'year';

const FILTER_OPTIONS: { label: string; value: GroupBy }[] = [
  { label: 'Günlük',   value: 'day' },
  { label: 'Haftalık', value: 'week' },
  { label: 'Aylık',    value: 'month' },
  { label: 'Yıllık',   value: 'year' },
];

function periodDates(groupBy: GroupBy): { date_from: string; date_to: string } {
  const today = new Date();
  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  const date_to = fmt(today);
  let date_from: string;
  if (groupBy === 'day') {
    date_from = fmt(startOfDay(today));
  } else if (groupBy === 'week') {
    date_from = fmt(startOfWeek(today, { weekStartsOn: 1 }));
  } else if (groupBy === 'month') {
    date_from = fmt(startOfMonth(today));
  } else {
    date_from = fmt(startOfYear(today));
  }
  return { date_from, date_to };
}

const NOTE_TYPE_BADGE: Record<NoteType, { label: string; icon: React.ReactNode; cls: string }> = {
  treatment:   { label: 'Tedavi',          icon: <Stethoscope className="h-3 w-3" />, cls: 'bg-blue-100 text-blue-700' },
  ai_feedback: { label: 'Yapay Zeka Notu', icon: <Bot className="h-3 w-3" />,        cls: 'bg-purple-100 text-purple-700' },
  general:     { label: 'Genel',           icon: <StickyNote className="h-3 w-3" />,   cls: 'bg-slate-100 text-slate-600' },
};

/* ── Period Filter ─────────────────────────────────── */
function PeriodFilter({ value, onChange }: { value: GroupBy; onChange: (v: GroupBy) => void }) {
  return (
    <div className="flex gap-1 rounded-xl bg-slate-100 p-1">
      {FILTER_OPTIONS.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
            value === opt.value
              ? 'bg-blue-600 text-white shadow-sm'
              : 'text-slate-500 hover:text-slate-700'
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

/* ── Note Row ──────────────────────────────────────── */
function NoteCard({ note, showDoctor = false }: { note: PatientNote; showDoctor?: boolean }) {
  const cfg = NOTE_TYPE_BADGE[note.note_type as NoteType] ?? NOTE_TYPE_BADGE.general;
  const sourceLabel = note.note_type === 'ai_feedback' ? 'DentAI Yapay Zeka' : note.doctor_name;
  const isAiNote = note.note_type === 'ai_feedback';
  return (
    <div className={`flex items-start gap-3 px-4 py-3 transition-colors ${isAiNote ? 'border-l-4 border-purple-400 bg-purple-50/40 hover:bg-purple-50/60' : 'hover:bg-slate-50'}`}>
      <div className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-full bg-blue-50 shrink-0">
        <User className="h-4 w-4 text-blue-500" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-semibold text-slate-800">
            {note.patient_name ?? 'Hasta'}
          </span>
          <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ${cfg.cls}`}>
            {cfg.icon} {cfg.label}
          </span>
          {isAiNote && (
            <span className="rounded-full bg-purple-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-purple-700">
              AI
            </span>
          )}
          {showDoctor && sourceLabel && (
            <span className="text-xs text-slate-400">• {sourceLabel}</span>
          )}
        </div>
        <p className="mt-1 text-sm text-slate-700 whitespace-pre-wrap">{note.content}</p>
        <p className="mt-1 text-xs text-slate-400">
          {format(parseISO(note.created_at), 'd MMM yyyy HH:mm', { locale: tr })}
        </p>
      </div>
    </div>
  );
}

/* ── Doctor's Own Treatment Log ─────────────────────── */
export function DoctorTreatmentLog() {
  const [groupBy, setGroupBy] = useState<GroupBy>('day');
  const dates = useMemo(() => periodDates(groupBy), [groupBy]);
  const { notes, loading } = useMyTreatmentLog(dates);

  // Group notes by date
  const grouped = useMemo(() => {
    const map = new Map<string, PatientNote[]>();
    for (const n of notes) {
      const dateKey = format(parseISO(n.created_at), 'd MMM yyyy', { locale: tr });
      if (!map.has(dateKey)) map.set(dateKey, []);
      map.get(dateKey)!.push(n);
    }
    return Array.from(map.entries());
  }, [notes]);

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 bg-slate-50 px-5 py-3">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-blue-600" />
          <span className="text-sm font-semibold text-slate-700">Tedavi Kayıtlarım</span>
          <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-semibold text-blue-700">
            {notes.length} kayıt
          </span>
        </div>
        <PeriodFilter value={groupBy} onChange={setGroupBy} />
      </div>

      {/* Content */}
      {loading ? (
        <div className="p-8 text-center text-sm text-slate-400 animate-pulse">Yükleniyor...</div>
      ) : notes.length === 0 ? (
        <div className="p-8 text-center">
          <FileText className="mx-auto h-10 w-10 text-slate-300 mb-3" />
          <p className="text-sm text-slate-500">Bu dönemde tedavi kaydı yok.</p>
          <p className="text-xs text-slate-400 mt-1">Yedek listeden veya randevu sayfasından not ekleyebilirsiniz.</p>
        </div>
      ) : (
        <div className="divide-y divide-slate-100">
          {grouped.map(([date, dayNotes]) => (
            <div key={date}>
              <div className="flex items-center gap-2 bg-slate-50/50 px-4 py-2">
                <CalendarIcon className="h-3.5 w-3.5 text-slate-400" />
                <span className="text-xs font-semibold text-slate-500">{date}</span>
                <span className="text-xs text-slate-400">({dayNotes.length} işlem)</span>
              </div>
              <div className="divide-y divide-slate-50">
                {dayNotes.map((n) => <NoteCard key={n.id} note={n} />)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Admin/Owner All Doctors Log ──────────────────────── */
export function AllDoctorsTreatmentLog() {
  const [groupBy, setGroupBy] = useState<GroupBy>('day');
  const dates = useMemo(() => periodDates(groupBy), [groupBy]);
  const params = useMemo(() => ({ ...dates, group_by: groupBy }), [dates, groupBy]);
  const { summaries, loading } = useAllDoctorsLog(params);
  const [expandedKey, setExpandedKey] = useState<string | null>(null);

  const totalNotes = summaries.reduce((s, g) => s + g.treatment_count, 0);

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 bg-slate-50 px-5 py-3">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-blue-600" />
          <span className="text-sm font-semibold text-slate-700">Hekim Tedavi Kayıtları</span>
          <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-semibold text-blue-700">
            {totalNotes} kayıt
          </span>
        </div>
        <PeriodFilter value={groupBy} onChange={setGroupBy} />
      </div>

      {/* Content */}
      {loading ? (
        <div className="p-8 text-center text-sm text-slate-400 animate-pulse">Yükleniyor...</div>
      ) : summaries.length === 0 ? (
        <div className="p-8 text-center">
          <FileText className="mx-auto h-10 w-10 text-slate-300 mb-3" />
          <p className="text-sm text-slate-500">Bu dönemde tedavi kaydı yok.</p>
        </div>
      ) : (
        <div className="divide-y divide-slate-100">
          {summaries.map((s) => {
            const key = `${s.doctor_id}-${s.period}`;
            const isExpanded = expandedKey === key;
            return (
              <div key={key}>
                <button
                  onClick={() => setExpandedKey(isExpanded ? null : key)}
                  className="w-full flex items-center gap-3 px-5 py-3 hover:bg-slate-50 transition-colors text-left"
                >
                  <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-100 shrink-0">
                    <Stethoscope className="h-4 w-4 text-blue-600" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-slate-800">{s.doctor_name}</span>
                      {s.specialty && (
                        <span className="text-xs text-slate-400">({s.specialty})</span>
                      )}
                    </div>
                    <div className="flex items-center gap-3 mt-0.5">
                      <span className="text-xs text-slate-500">{s.period}</span>
                      <span className="rounded-full bg-green-100 px-2 py-0.5 text-[10px] font-bold text-green-700">
                        {s.treatment_count} işlem
                      </span>
                    </div>
                  </div>
                  {isExpanded ? (
                    <ChevronUp className="h-4 w-4 text-slate-400" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-slate-400" />
                  )}
                </button>
                {isExpanded && s.notes.length > 0 && (
                  <div className="border-t border-slate-100 bg-slate-50/30 divide-y divide-slate-50">
                    {s.notes.map((n) => <NoteCard key={n.id} note={n} showDoctor={false} />)}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
