import { cn } from '@/lib/utils';

interface SkeletonProps {
  className?: string;
}

/** Single shimmer skeleton bar */
export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={cn(
        'animate-pulse rounded-md bg-slate-200',
        className,
      )}
    />
  );
}

/** Full-card skeleton for stat cards (used in dashboard) */
export function StatCardSkeleton() {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <Skeleton className="mb-3 h-4 w-32" />
      <Skeleton className="mb-2 h-8 w-40" />
      <Skeleton className="h-3 w-24" />
    </div>
  );
}

/** Skeleton for table rows */
export function TableRowSkeleton({ cols = 5 }: { cols?: number }) {
  return (
    <tr>
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <Skeleton className="h-4 w-full" />
        </td>
      ))}
    </tr>
  );
}
