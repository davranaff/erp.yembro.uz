import * as React from 'react';

import { cn } from '@/shared/lib/cn';

const inferInputMode = (
  type: React.HTMLInputTypeAttribute | undefined,
  explicit: React.HTMLAttributes<HTMLInputElement>['inputMode'] | undefined,
): React.HTMLAttributes<HTMLInputElement>['inputMode'] | undefined => {
  if (explicit !== undefined) {
    return explicit;
  }
  switch (type) {
    case 'email':
      return 'email';
    case 'tel':
      return 'tel';
    case 'url':
      return 'url';
    case 'search':
      return 'search';
    case 'number':
      return 'decimal';
    default:
      return undefined;
  }
};

const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<'input'>>(
  ({ className, type, inputMode, ...props }, ref) => {
    return (
      <input
        type={type}
        inputMode={inferInputMode(type, inputMode)}
        className={cn(
          'bg-background/98 flex h-9 w-full rounded-md border border-border/80 px-3 py-1 text-sm shadow-[0_14px_30px_-24px_rgba(15,23,42,0.18)] transition-colors',
          'file:border-0 file:bg-transparent file:text-sm file:font-medium',
          'disabled:cursor-not-allowed disabled:opacity-50',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
          className,
        )}
        ref={ref}
        {...props}
      />
    );
  },
);

Input.displayName = 'Input';

export { Input };
