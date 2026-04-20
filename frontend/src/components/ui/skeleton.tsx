import { cn } from '@/shared/lib/cn';

type SkeletonProps = {
  className?: string;
};

export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        'relative overflow-hidden rounded-md bg-muted/60',
        'before:absolute before:inset-0 before:-translate-x-full before:animate-[skeletonShimmer_1.6s_infinite] before:bg-gradient-to-r before:from-transparent before:via-background/70 before:to-transparent',
        className,
      )}
    >
      <style>{`
        @keyframes skeletonShimmer {
          100% { transform: translateX(100%); }
        }
      `}</style>
    </div>
  );
}

type TableSkeletonProps = {
  rows?: number;
  cols?: number;
  className?: string;
};

export function TableSkeleton({ rows = 6, cols = 5, className }: TableSkeletonProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="Loading table"
      className={cn('w-full space-y-3', className)}
    >
      <div className="flex items-center gap-3">
        {Array.from({ length: cols }).map((_, colIndex) => (
          <Skeleton
            key={`header-${colIndex}`}
            className={colIndex === 0 ? 'h-4 w-32' : 'h-4 flex-1'}
          />
        ))}
      </div>
      <div className="space-y-2 rounded-2xl border border-border/60 bg-card p-3">
        {Array.from({ length: rows }).map((_, rowIndex) => (
          <div
            key={`row-${rowIndex}`}
            className="flex items-center gap-3 rounded-xl border border-transparent px-2 py-2"
          >
            {Array.from({ length: cols }).map((_, colIndex) => (
              <Skeleton
                key={`cell-${rowIndex}-${colIndex}`}
                className={colIndex === 0 ? 'h-3.5 w-24' : 'h-3.5 flex-1'}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

type CardSkeletonProps = {
  lines?: number;
  className?: string;
};

export function CardSkeleton({ lines = 3, className }: CardSkeletonProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn('space-y-3 rounded-2xl border border-border/60 bg-card p-5', className)}
    >
      <Skeleton className="h-4 w-1/3" />
      {Array.from({ length: lines }).map((_, index) => (
        <Skeleton
          key={`line-${index}`}
          className={index === lines - 1 ? 'h-3.5 w-3/4' : 'h-3.5 w-full'}
        />
      ))}
    </div>
  );
}

type MetricSkeletonProps = {
  count?: number;
  className?: string;
};

export function MetricSkeleton({ count = 4, className }: MetricSkeletonProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn('grid gap-3 sm:grid-cols-2 lg:grid-cols-4', className)}
    >
      {Array.from({ length: count }).map((_, index) => (
        <div
          key={`metric-${index}`}
          className="space-y-3 rounded-2xl border border-border/60 bg-card p-4"
        >
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-8 w-20" />
          <Skeleton className="h-3 w-16" />
        </div>
      ))}
    </div>
  );
}
