import type { LucideIcon } from 'lucide-react';

import { cn } from '@/lib/cn';

export function EmptyState({
  icon: Icon,
  title,
  description,
  className,
  action,
}: {
  icon?: LucideIcon;
  title: string;
  description?: string;
  className?: string;
  action?: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-2 px-6 py-12 text-center',
        className,
      )}
    >
      {Icon ? (
        <div className="mb-1 flex h-8 w-8 items-center justify-center rounded border border-line bg-bg-subtle text-ink-muted">
          <Icon className="h-4 w-4" />
        </div>
      ) : null}
      <div className="text-sm font-medium text-ink">{title}</div>
      {description ? <div className="max-w-sm text-xs text-ink-muted">{description}</div> : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}
