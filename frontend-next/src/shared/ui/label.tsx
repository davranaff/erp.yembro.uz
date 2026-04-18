import { cn } from '@/lib/cn';

export function Label({
  className,
  ...rest
}: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label
      className={cn('text-2xs font-medium uppercase tracking-wide text-ink-muted', className)}
      {...rest}
    />
  );
}
