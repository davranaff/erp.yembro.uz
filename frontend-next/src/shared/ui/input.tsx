import { forwardRef } from 'react';

import { cn } from '@/lib/cn';

type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, ...rest },
  ref,
) {
  return (
    <input
      ref={ref}
      className={cn(
        'h-8 w-full rounded border border-line bg-bg-subtle px-2.5 text-sm text-ink placeholder:text-ink-faint',
        'transition-colors hover:border-line-strong focus:border-accent',
        'disabled:cursor-not-allowed disabled:opacity-60',
        className,
      )}
      {...rest}
    />
  );
});
