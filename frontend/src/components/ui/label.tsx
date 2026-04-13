import * as React from 'react';

import { cn } from '@/shared/lib/cn';

const Label = React.forwardRef<HTMLLabelElement, React.ComponentPropsWithoutRef<'label'>>(
  ({ className, ...props }, ref) => (
    <label ref={ref} className={cn('text-sm font-medium text-foreground', className)} {...props} />
  ),
);

Label.displayName = 'Label';

export { Label };
