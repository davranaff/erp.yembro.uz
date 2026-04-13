import { cva, type VariantProps } from 'class-variance-authority';
import * as React from 'react';

import { cn } from '@/shared/lib/cn';

const badgeVariants = cva(
  'inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] transition-colors',
  {
    variants: {
      variant: {
        default: 'border-primary/18 bg-primary/10 text-primary',
        secondary: 'border-border/75 bg-card text-foreground',
        outline: 'border-border/75 bg-background text-muted-foreground',
        muted: 'border-border/60 bg-muted/70 text-muted-foreground',
        success: 'border-emerald-200/70 bg-emerald-50/90 text-emerald-700',
        warning: 'border-amber-200/70 bg-amber-50/90 text-amber-700',
        destructive: 'border-rose-200/70 bg-rose-50/90 text-rose-700',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
);

function Badge({
  className,
  variant,
  ...props
}: React.ComponentProps<'span'> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
