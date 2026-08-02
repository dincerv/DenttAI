'use client';
import { useState, useRef, useEffect } from 'react';
import { Info, Package, AlertTriangle, Clock, ArrowDown } from 'lucide-react';
import type { BatchSummary } from '@/types';

interface Props {
  summary: BatchSummary;
}

export function BatchTooltip({ summary }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  const hasBatches = summary.batches.length > 1;

  // FEFO sıralaması: expiry_date en yakın olan önce (null en sona)
  const sortedBatches = [...summary.batches].sort((a, b) => {
    if (a.expiry_date === null && b.expiry_date === null) return 0;
    if (a.expiry_date === null) return 1;
    if (b.expiry_date === null) return -1;
    return a.expiry_date.localeCompare(b.expiry_date);
  });

  return (
    <div ref={ref} className="relative inline-flex items-center">
      <button
        type="button"
        className="ml-1.5 rounded-full p-0.5 text-blue-400 hover:text-blue-600 hover:bg-blue-50 transition-colors"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}
        aria-label="Parti bilgisi"
      >
        <Info className="h-3.5 w-3.5" />
      </button>

      {open && (
        <div className="absolute left-1/2 bottom-full mb-2 z-50 -translate-x-1/2 w-80 rounded-xl border border-blue-100 bg-white shadow-xl ring-1 ring-blue-50 animate-in fade-in-0 zoom-in-95 duration-150">
          {/* Header */}
          <div className="border-b border-blue-50 bg-gradient-to-r from-blue-600 to-blue-700 px-4 py-2.5 rounded-t-xl">
            <div className="flex items-center gap-2 text-white">
              <Package className="h-4 w-4 shrink-0" />
              <span className="text-sm font-semibold truncate">{summary.name}</span>
            </div>
            <div className="mt-1 flex items-center gap-3 text-blue-100 text-xs">
              <span>Toplam: <b className="text-white">{summary.total_quantity}</b> {summary.unit}</span>
              <span className="flex items-center gap-0.5">
                {summary.batches.length} Parti
              </span>
              {summary.is_low_stock && (
                <span className="flex items-center gap-0.5 text-amber-300">
                  <AlertTriangle className="h-3 w-3" /> Düşük
                </span>
              )}
            </div>
          </div>

          {/* FEFO badge */}
          {hasBatches && (
            <div className="flex items-center gap-1.5 px-4 py-1.5 bg-blue-50/80 border-b border-blue-100 text-[10px] text-blue-600 font-semibold">
              <ArrowDown className="h-3 w-3" />
              FEFO Sırası — İlk vadesi dolan önce tüketilir
            </div>
          )}

          {/* Batch list — FEFO ordered */}
          <div className="max-h-56 overflow-y-auto px-3 py-2 space-y-1.5">
            {summary.batches.length === 0 ? (
              <p className="py-3 text-center text-xs text-slate-400">Parti bulunamadı</p>
            ) : (
              sortedBatches.map((b, i) => {
                const isExpiringSoon = b.days_until_expiry != null && b.days_until_expiry <= 30;
                const isExpired = b.days_until_expiry != null && b.days_until_expiry < 0;
                const isFirst = i === 0 && hasBatches;
                return (
                  <div
                    key={b.batch_id}
                    className={`flex items-center justify-between rounded-lg px-3 py-2.5 text-xs transition-colors ${
                      isExpired
                        ? 'bg-red-50 border border-red-200'
                        : isExpiringSoon
                        ? 'bg-amber-50 border border-amber-200'
                        : isFirst
                        ? 'bg-blue-50 border-2 border-blue-300'
                        : 'bg-blue-50/50 border border-blue-100'
                    }`}
                  >
                    <div className="flex flex-col gap-0.5 min-w-0 flex-1">
                      <div className="flex items-center gap-1.5">
                        {isFirst && (
                          <span className="shrink-0 flex h-4 w-4 items-center justify-center rounded-full bg-blue-600 text-[9px] font-bold text-white" title="Önce tüketilecek">1</span>
                        )}
                        <span className="font-semibold text-slate-700 truncate">
                          {b.batch_number ?? `Parti ${i + 1}`}
                        </span>
                      </div>
                      <span className={`text-[10px] flex items-center gap-1 ${
                        isExpired ? 'text-red-600 font-bold' :
                        isExpiringSoon ? 'text-amber-600 font-semibold' :
                        'text-slate-400'
                      }`}>
                        <Clock className="h-2.5 w-2.5 shrink-0" />
                        {b.expiry_date
                          ? isExpired
                            ? `SKT Geçmiş (${Math.abs(b.days_until_expiry!)} gün)`
                            : `${b.days_until_expiry} Gün Kaldı`
                          : 'SKT yok'}
                      </span>
                    </div>
                    <div className="text-right shrink-0 ml-2">
                      <span className={`text-sm font-bold ${
                        b.is_low_stock ? 'text-red-600' : 'text-blue-700'
                      }`}>
                        {b.quantity}
                      </span>
                      <span className="ml-0.5 text-slate-400">{summary.unit}</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Summary footer */}
          <div className="border-t border-blue-100 px-4 py-2 flex items-center justify-between text-[10px]">
            <span className="text-slate-400">
              {summary.batches.map((b) => b.quantity).join(' + ')} = {summary.total_quantity} {summary.unit}
            </span>
            {summary.nearest_expiry_date && summary.days_until_nearest_expiry != null && (
              <span className={`font-semibold ${summary.days_until_nearest_expiry <= 30 ? 'text-orange-600' : 'text-slate-500'}`}>
                En yakın SKT: {summary.days_until_nearest_expiry}g
              </span>
            )}
          </div>
          
          {/* Arrow */}
          <div className="absolute left-1/2 top-full -translate-x-1/2 -mt-px">
            <div className="h-2 w-2 rotate-45 border-r border-b border-blue-100 bg-white" />
          </div>
        </div>
      )}
    </div>
  );
}
