export type GroupBy = 'day' | 'week' | 'month' | 'year';

export const PERIOD_LABELS: Record<GroupBy, string> = {
  day: 'Bugün',
  week: 'Bu Hafta',
  month: 'Bu Ay',
  year: 'Bu Yıl',
};

function formatLocalDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

/** groupBy değerine göre start_date / end_date (yerel takvim, YYYY-MM-DD) */
export function periodDates(groupBy: GroupBy): { start_date: string; end_date: string } {
  const today = new Date();
  const end = formatLocalDate(today);

  let start: string;
  if (groupBy === 'day') {
    start = end;
  } else if (groupBy === 'week') {
    const d = new Date(today);
    const mondayOffset = today.getDay() === 0 ? -6 : 1 - today.getDay();
    d.setDate(today.getDate() + mondayOffset);
    start = formatLocalDate(d);
  } else if (groupBy === 'month') {
    start = formatLocalDate(new Date(today.getFullYear(), today.getMonth(), 1));
  } else {
    start = formatLocalDate(new Date(today.getFullYear(), 0, 1));
  }
  return { start_date: start, end_date: end };
}
