import { cn } from '@/lib/cn';

export function Kbd({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <kbd
      className={cn(
        'inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded border border-line/60 bg-bg-subtle px-1 font-mono text-2xs text-ink-muted',
        className,
      )}
    >
      {children}
    </kbd>
  );
}
