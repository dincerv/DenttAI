'use client';
import { useState } from 'react';
import { toast } from 'sonner';
import { Trash2, RefreshCw, Calendar, User, StickyNote, Plus } from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { tr } from 'date-fns/locale';
import { useWaitlist } from '@/hooks/useWaitlist';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { TableRowSkeleton } from '@/components/ui/Skeleton';
import { formatDate } from '@/lib/utils';
import { PatientNotesPanel } from '@/components/dashboard/PatientNotesPanel';
import WaitlistForm from '@/components/dashboard/WaitlistForm';
import type { WaitlistEntry } from '@/types';

function getPriority(p: number) {
  if (p <= 3) return { label: 'Yüksek', variant: 'red' as const };
  if (p <= 7) return { label: 'Normal', variant: 'orange' as const };
  return { label: 'Düşük', variant: 'blue' as const };
}

export default function WaitlistPage() {
  const { entries, loading, error, refresh, remove } = useWaitlist();
  const [notesEntry, setNotesEntry] = useState<WaitlistEntry | null>(null);
  const [showForm, setShowForm] = useState(false);

  async function handleRemove(id: string) {
    try {
      await remove(id);
      toast.success('Hasta yedek listeden çıkarıldı');
    } catch {
      toast.error('İşlem başarısız');
    }
  }

  const sorted = [...entries].sort((a, b) => a.priority - b.priority);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-slate-500">
          Bekleyen hasta sayısı:{' '}
          <span className="font-bold text-slate-800">{entries.length}</span>
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant={showForm ? 'secondary' : 'primary'}
            size="sm"
            onClick={() => setShowForm((v) => !v)}
          >
            <Plus className="h-3.5 w-3.5" />
            {showForm ? 'Formu kapat' : 'Hasta ekle'}
          </Button>
          <Button variant="secondary" size="sm" onClick={refresh}>
            <RefreshCw className="h-3.5 w-3.5" />
            Yenile
          </Button>
        </div>
      </div>

      {showForm && (
        <WaitlistForm
          onCreated={() => {
            toast.success('Yedek listeye eklendi');
            refresh();
          }}
        />
      )}

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-4 text-sm text-red-600">
          ⚠ {error}
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr className="bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
                <th className="px-4 py-3 text-left">Sıra</th>
                <th className="px-4 py-3 text-left">Hasta</th>
                <th className="px-4 py-3 text-left">Diş Hekimi</th>
                <th className="px-4 py-3 text-left">Branş</th>
                <th className="px-4 py-3 text-left">Öncelik</th>
                <th className="px-4 py-3 text-left">Sonraki Randevu</th>
                <th className="px-4 py-3 text-left">Listeye Eklenme</th>
                <th className="px-4 py-3 text-center">Notlar</th>
                <th className="px-4 py-3 text-right">İşlem</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                Array.from({ length: 5 }).map((_, i) => <TableRowSkeleton key={i} cols={9} />)
              ) : sorted.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-sm text-slate-400">
                    Yedek listede hasta yok
                  </td>
                </tr>
              ) : (
                sorted.map((entry, idx) => {
                  const prio = getPriority(entry.priority);
                  return (
                    <tr key={entry.id} className="hover:bg-slate-50 transition-colors">
                      <td className="px-4 py-3 text-sm font-bold text-slate-400">#{idx + 1}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-100">
                            <User className="h-4 w-4 text-blue-600" />
                          </div>
                          <span className="text-sm font-medium text-slate-800">
                            {entry.patient_name ?? entry.patient_id.slice(0, 8)}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-600">{entry.doctor_name ?? '—'}</td>
                      <td className="px-4 py-3 text-sm text-slate-600">{entry.specialty ?? '—'}</td>
                      <td className="px-4 py-3">
                        <Badge variant={prio.variant}>{prio.label}</Badge>
                      </td>
                      <td className="px-4 py-3">
                        {entry.next_appointment_date ? (
                          <div className="flex items-center gap-1.5 text-sm text-green-700">
                            <Calendar className="h-3.5 w-3.5" />
                            {format(parseISO(entry.next_appointment_date), 'd MMM yyyy HH:mm', { locale: tr })}
                          </div>
                        ) : (
                          <span className="text-xs text-slate-400">Randevu yok</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-500">{formatDate(entry.created_at)}</td>
                      <td className="px-4 py-3 text-center">
                        <button
                          type="button"
                          onClick={() => setNotesEntry(entry)}
                          className="inline-flex rounded-md p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-800"
                          aria-label="Notlar"
                        >
                          <StickyNote className="h-4 w-4" />
                        </button>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          type="button"
                          onClick={() => handleRemove(entry.id)}
                          className="inline-flex rounded-md p-1.5 text-red-500 hover:bg-red-50"
                          aria-label="Sil"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {notesEntry && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-lg">
            <div className="relative">
              <button
                type="button"
                onClick={() => setNotesEntry(null)}
                className="absolute -right-3 -top-3 z-10 rounded-full bg-white p-1.5 text-slate-400 shadow-lg hover:text-slate-600"
              >
                <span className="text-lg leading-none">&times;</span>
              </button>
              <PatientNotesPanel
                patientId={notesEntry.patient_id}
                patientName={notesEntry.patient_name ?? undefined}
                canAdd
                defaultNoteType="treatment"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
