import { Loader2 } from 'lucide-react';

import { cn } from '@/shared/lib/cn';

type InlineLoaderProps = {
  label?: string;
  className?: string;
};

export function InlineLoader({ label, className }: InlineLoaderProps) {
  return (
    <div
      className={cn(
        'flex items-center justify-center gap-2 px-6 py-12 text-sm text-muted-foreground',
        className,
      )}
      role="status"
      aria-live="polite"
    >
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
      {label ? <span>{label}</span> : null}
    </div>
  );
}
