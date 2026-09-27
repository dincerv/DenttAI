'use client';

import { cn } from '@/lib/utils';

const UPPER = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28];
const LOWER = [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38];

export const TOOTH_STATUS_LABEL: Record<string, string> = {
  healthy: 'Sağlam',
  caries: 'Çürük',
  filled: 'Dolgu',
  rct: 'Kanal',
  crown: 'Kron',
  missing: 'Eksik',
  implant: 'İmplant',
  bridge: 'Köprü',
  planned: 'Planlı',
};

const STATUS_CLASS: Record<string, string> = {
  healthy: 'bg-white border-slate-300 text-slate-700',
  caries: 'bg-red-500 border-red-600 text-white',
  filled: 'bg-blue-500 border-blue-600 text-white',
  rct: 'bg-violet-500 border-violet-600 text-white',
  crown: 'bg-amber-400 border-amber-500 text-slate-900',
  missing: 'bg-slate-300 border-slate-400 text-slate-500 line-through',
  implant: 'bg-teal-500 border-teal-600 text-white',
  bridge: 'bg-sky-400 border-sky-500 text-slate-900',
  planned: 'bg-orange-100 border-orange-400 text-orange-800',
};

export const TOOTH_STATUSES = Object.keys(TOOTH_STATUS_LABEL);

type Tooth = { tooth_fdi: number; status: string };

export function Odontogram({
  teeth,
  selected,
  onSelect,
}: {
  teeth: Tooth[];
  selected: number | null;
  onSelect: (n: number) => void;
}) {
  const byId = new Map(teeth.map((t) => [t.tooth_fdi, t.status]));

  function row(nums: number[]) {
    return (
      <div className="flex flex-wrap justify-center gap-1">
        {nums.map((n, i) => (
          <button
            key={n}
            type="button"
            onClick={() => onSelect(n)}
            className={cn(
              'h-9 w-9 sm:h-10 sm:w-10 rounded-md border text-[11px] font-semibold',
              STATUS_CLASS[byId.get(n) ?? 'healthy'],
              selected === n && 'ring-2 ring-brand-600 ring-offset-1',
              i === 7 && 'mr-2 sm:mr-3',
            )}
            title={`${n} · ${TOOTH_STATUS_LABEL[byId.get(n) ?? 'healthy']}`}
          >
            {n}
          </button>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <p className="text-[11px] text-center text-slate-400">Üst çene</p>
      {row(UPPER)}
      <p className="text-[11px] text-center text-slate-400 pt-1">Alt çene</p>
      {row(LOWER)}
    </div>
  );
}
