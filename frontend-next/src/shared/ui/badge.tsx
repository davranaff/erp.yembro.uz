import { cn } from '@/lib/cn';

type Tone = 'neutral' | 'accent' | 'ok' | 'warn' | 'danger';

const toneClass: Record<Tone, string> = {
  neutral: 'bg-bg-subtle text-ink-soft border-line',
  accent: 'bg-accent-soft/40 text-accent border-accent/30',
  ok: 'bg-ok-soft/40 text-ok border-ok/30',
  warn: 'bg-warn-soft/40 text-warn border-warn/30',
  danger: 'bg-danger-soft/40 text-danger border-danger/30',
};

export function Badge({
  tone = 'neutral',
  children,
  className,
}: {
  tone?: Tone;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        'inline-flex h-5 items-center rounded-sm border px-1.5 font-mono text-2xs uppercase tracking-wide',
        toneClass[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
