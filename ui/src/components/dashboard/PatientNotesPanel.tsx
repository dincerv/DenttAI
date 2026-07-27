'use client';
import { useState, useMemo } from 'react';
import { toast } from 'sonner';
import {
  FileText, Send, Stethoscope, Bot, StickyNote, ChevronDown, ChevronUp,
} from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { tr } from 'date-fns/locale';
import { patientNotesApi } from '@/lib/api-client';
import { usePatientNotes } from '@/hooks/usePatientNotes';
import type { PatientNote, NoteType } from '@/types';

const NOTE_TYPE_CONFIG: Record<NoteType, { label: string; icon: React.ReactNode; color: string; bg: string }> = {
  treatment:   { label: 'Tedavi',       icon: <Stethoscope className="h-3.5 w-3.5" />, color: 'text-blue-700',  bg: 'bg-blue-50 border-blue-200' },
  ai_feedback: { label: 'Yapay Zeka Notu', icon: <Bot className="h-3.5 w-3.5" />,   color: 'text-purple-700', bg: 'bg-purple-50 border-purple-200' },
  general:     { label: 'Genel Not',    icon: <StickyNote className="h-3.5 w-3.5" />,  color: 'text-slate-700',  bg: 'bg-slate-50 border-slate-200' },
};

interface Props {
  patientId: string;
  patientName?: string;
  /** Gösterilecek not tipi filtresi (boş = hepsi) */
  filterType?: NoteType;
  /** Not ekleme izni var mı? */
  canAdd?: boolean;
  /** Varsayılan yeni not türü */
  defaultNoteType?: NoteType;
  /** Compact mod — waitlist satırı içi */
  compact?: boolean;
}

export function PatientNotesPanel({
  patientId,
  patientName,
  filterType,
  canAdd = true,
  defaultNoteType = 'treatment',
  compact = false,
}: Props) {
  const params = useMemo(() => {
    const p: Record<string, string> = { patient_id: patientId };
    if (filterType) p.note_type = filterType;
    return p;
  }, [patientId, filterType]);

  const { notes, loading, refresh } = usePatientNotes(params);
  const [newContent, setNewContent] = useState('');
  const [noteType, setNoteType] = useState<NoteType>(defaultNoteType);
  const [saving, setSaving] = useState(false);
  const [expanded, setExpanded] = useState(!compact);

  async function handleAdd() {
    if (!newContent.trim()) return;
    setSaving(true);
    try {
      await patientNotesApi.create({
        patient_id: patientId,
        note_type: noteType,
        content: newContent.trim(),
      });
      toast.success('Not kaydedildi');
      setNewContent('');
      refresh();
    } catch {
      toast.error('Not kaydedilemedi');
    } finally {
      setSaving(false);
    }
  }

  if (compact && !expanded) {
    return (
      <button
        onClick={() => setExpanded(true)}
        className="flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-800"
      >
        <FileText className="h-3.5 w-3.5" />
        {notes.length > 0 ? `${notes.length} not` : 'Not ekle'}
        <ChevronDown className="h-3 w-3" />
      </button>
    );
  }

  return (
    <div className={`rounded-xl border border-slate-200 bg-white overflow-hidden ${compact ? 'shadow-lg' : 'shadow-sm'}`}>
      {/* Header */}
      <div className="flex items-center justify-between bg-gradient-to-r from-blue-600 to-blue-700 px-4 py-3">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-white" />
          <h3 className="text-sm font-semibold text-white">
            {patientName ? `${patientName} — Notlar` : 'Hasta Notları'}
          </h3>
          {notes.length > 0 && (
            <span className="rounded-full bg-white/20 px-2 py-0.5 text-xs font-medium text-white">
              {notes.length}
            </span>
          )}
        </div>
        {compact && (
          <button
            onClick={() => setExpanded(false)}
            className="text-white/70 hover:text-white"
          >
            <ChevronUp className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Add form */}
      {canAdd && (
        <div className="border-b border-slate-100 p-4 space-y-3">
          <div className="flex gap-2">
            {(Object.keys(NOTE_TYPE_CONFIG) as NoteType[]).filter(t => t !== 'ai_feedback').map((t) => {
              const cfg = NOTE_TYPE_CONFIG[t];
              return (
                <button
                  key={t}
                  onClick={() => setNoteType(t)}
                  className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
                    noteType === t
                      ? 'bg-blue-600 text-white shadow-sm'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  {cfg.icon}
                  {cfg.label}
                </button>
              );
            })}
          </div>
          <div className="flex gap-2">
            <textarea
              value={newContent}
              onChange={(e) => setNewContent(e.target.value)}
              rows={2}
              className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none resize-none"
              placeholder={noteType === 'treatment' ? 'Uygulanan tedavi: kanal tedavisi, dolgu...' : 'Not giriniz...'}
            />
            <button
              onClick={handleAdd}
              disabled={saving || !newContent.trim()}
              className="self-end flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              <Send className="h-3.5 w-3.5" />
              {saving ? '...' : 'Kaydet'}
            </button>
          </div>
        </div>
      )}

      {/* Notes list */}
      <div className="max-h-80 overflow-y-auto divide-y divide-slate-50">
        {loading ? (
          <div className="p-6 text-center text-sm text-slate-400 animate-pulse">Yükleniyor...</div>
        ) : notes.length === 0 ? (
          <div className="p-6 text-center text-sm text-slate-400">Henüz not yok</div>
        ) : (
          notes.map((note) => <NoteRow key={note.id} note={note} />)
        )}
      </div>
    </div>
  );
}

function NoteRow({ note }: { note: PatientNote }) {
  const cfg = NOTE_TYPE_CONFIG[note.note_type as NoteType] ?? NOTE_TYPE_CONFIG.general;
  const authorLabel = note.note_type === 'ai_feedback'
    ? 'DentAI Yapay Zeka'
    : note.doctor_name;
  const isAiNote = note.note_type === 'ai_feedback';
  return (
    <div className={`px-4 py-3 transition-colors ${isAiNote ? 'border-l-4 border-purple-400 bg-purple-50/40 hover:bg-purple-50/60' : 'hover:bg-slate-50'}`}>
      <div className="flex items-start gap-3">
        <div className={`mt-0.5 flex h-7 w-7 items-center justify-center rounded-full border ${cfg.bg}`}>
          <span className={cfg.color}>{cfg.icon}</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-xs font-semibold ${cfg.color}`}>{cfg.label}</span>
            {isAiNote && (
              <span className="rounded-full bg-purple-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-purple-700">
                AI
              </span>
            )}
            {authorLabel && (
              <span className="text-xs text-slate-500">— {authorLabel}</span>
            )}
            <span className="text-xs text-slate-400">
              {format(parseISO(note.created_at), 'd MMM yyyy HH:mm', { locale: tr })}
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-700 whitespace-pre-wrap">{note.content}</p>
          {note.patient_name && (
            <p className="mt-0.5 text-xs text-slate-400">Hasta: {note.patient_name}</p>
          )}
        </div>
      </div>
    </div>
  );
}
