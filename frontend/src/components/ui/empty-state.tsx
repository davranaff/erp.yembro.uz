import { Inbox, type LucideIcon } from 'lucide-react';
import { type ReactNode } from 'react';

import { cn } from '@/shared/lib/cn';

type EmptyStateProps = {
  title: string;
  description?: string;
  icon?: LucideIcon;
  action?: ReactNode;
  className?: string;
};

export function EmptyState({
  title,
  description,
  icon: Icon = Inbox,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 px-6 py-12 text-center',
        className,
      )}
    >
      <span className="inline-flex h-14 w-14 items-center justify-center rounded-2xl border border-border/70 bg-secondary/40 text-muted-foreground shadow-[0_18px_42px_-30px_rgba(15,23,42,0.18)]">
        <Icon className="h-6 w-6" aria-hidden="true" />
      </span>
      <div className="space-y-1.5">
        <p className="text-sm font-semibold text-foreground">{title}</p>
        {description ? (
          <p className="mx-auto max-w-sm text-xs leading-relaxed text-muted-foreground">
            {description}
          </p>
        ) : null}
      </div>
      {action ? <div className="pt-1">{action}</div> : null}
    </div>
  );
}
