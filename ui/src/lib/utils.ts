import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { format, parseISO } from 'date-fns';
import { tr } from 'date-fns/locale';

/** Tailwind class utility — clsx + twMerge */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/** TRY para formatı: 42000 → "₺42.000,00" */
export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('tr-TR', {
    style: 'currency',
    currency: 'TRY',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

/** ISO tarih → DD/MM/YYYY: "22/04/2026" */
export function formatDate(iso: string): string {
  return format(parseISO(iso), 'dd/MM/yyyy', { locale: tr });
}

/** ISO tarih → Türkçe uzun: "22 Nisan 2026, 14:30" */
export function formatDateTime(iso: string): string {
  return format(parseISO(iso), "d MMMM yyyy, HH:mm", { locale: tr });
}

/** Yüzde formatı: 75.3 → "%75,3" */
export function formatPercent(value: number | null | undefined): string {
  if (value == null) return '—';
  return `%${value.toFixed(1).replace('.', ',')}`;
}

/** Randevu durumuna göre badge rengi */
export const statusColorMap: Record<string, string> = {
  scheduled:  'bg-blue-100 text-blue-800',
  confirmed:  'bg-green-100 text-green-800',
  completed:  'bg-slate-100 text-slate-800',
  cancelled:  'bg-red-100 text-red-800',
  no_show:    'bg-orange-100 text-orange-800',
};

/** Randevu durumuna Türkçe label */
export const statusLabelMap: Record<string, string> = {
  scheduled:  'Planlandı',
  confirmed:  'Onaylandı',
  completed:  'Tamamlandı',
  cancelled:  'İptal',
  no_show:    'Gelmedi',
};
