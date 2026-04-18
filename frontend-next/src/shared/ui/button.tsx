import { forwardRef } from 'react';

import { cn } from '@/lib/cn';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
type Size = 'sm' | 'md';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

const variantClass: Record<Variant, string> = {
  primary:
    'bg-ink text-ink-invert border-ink/10 hover:bg-ink/90 active:bg-ink/80 disabled:bg-ink/40',
  secondary:
    'bg-bg-subtle text-ink border-line hover:bg-bg-inset hover:border-line-strong disabled:text-ink-muted',
  ghost:
    'bg-transparent text-ink border-transparent hover:bg-bg-subtle disabled:text-ink-muted',
  danger:
    'bg-danger text-white border-danger/30 hover:bg-danger/90 disabled:bg-danger/50',
};

const sizeClass: Record<Size, string> = {
  sm: 'h-7 px-2.5 text-xs gap-1.5',
  md: 'h-8 px-3 text-sm gap-2',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'secondary', size = 'sm', loading, className, children, disabled, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={rest.type ?? 'button'}
      disabled={disabled || loading}
      className={cn(
        'inline-flex select-none items-center justify-center whitespace-nowrap rounded border font-medium transition-colors',
        'disabled:cursor-not-allowed',
        variantClass[variant],
        sizeClass[size],
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  );
});
