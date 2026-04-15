import { type ComponentProps, type ReactNode } from 'react';

import { Button } from '@/components/ui/button';
import {
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { cn } from '@/shared/lib/cn';

type CrudDrawerSize = 'default' | 'wide' | 'xwide' | 'audit' | 'audit-wide';

type CrudDrawerProps = {
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  size?: CrudDrawerSize;
  dataTour?: string;
  className?: string;
  headerClassName?: string;
  bodyClassName?: string;
  titleClassName?: string;
  descriptionClassName?: string;
  formProps?: Omit<ComponentProps<'form'>, 'children'>;
};

type CrudDrawerFooterProps = {
  children?: ReactNode;
  closeLabel: ReactNode;
  closeDisabled?: boolean;
  closeButtonClassName?: string;
  className?: string;
  actionsClassName?: string;
  align?: 'auto' | 'between' | 'end';
  onClose: () => void;
};

const contentSizeClassNames: Record<CrudDrawerSize, string> = {
  default: 'data-[side=right]:sm:max-w-[760px]',
  wide: 'data-[side=right]:xl:max-w-[1080px]',
  xwide: 'data-[side=right]:xl:max-w-[1140px]',
  audit: 'data-[side=right]:sm:max-w-[860px]',
  'audit-wide': 'data-[side=right]:sm:max-w-[880px]',
};

const contentBaseClassName =
  'border-primary/16 w-full min-h-0 gap-0 border-l p-0 shadow-[0_32px_120px_-56px_rgba(15,23,42,0.28)]';
const bodyBaseClassName =
  'min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain bg-background px-4 py-4 sm:space-y-5 sm:px-6 sm:py-5';
const closeButtonBaseClassName =
  'bg-card border-border/75 shadow-[0_16px_38px_-28px_rgba(15,23,42,0.1)]';

export function CrudDrawer({
  title,
  description,
  children,
  footer,
  size = 'default',
  dataTour,
  className,
  headerClassName,
  bodyClassName,
  titleClassName,
  descriptionClassName,
  formProps,
}: CrudDrawerProps) {
  const body = <div className={cn(bodyBaseClassName, bodyClassName)}>{children}</div>;

  return (
    <SheetContent
      side="right"
      showCloseButton={false}
      data-tour={dataTour}
      className={cn(contentBaseClassName, contentSizeClassNames[size], className)}
    >
      <SheetHeader className={cn('gap-2 px-4 py-4 sm:px-6 sm:py-5', headerClassName)}>
        <SheetTitle className={cn('text-xl tracking-[-0.04em] sm:text-2xl', titleClassName)}>
          {title}
        </SheetTitle>
        {description ? (
          <SheetDescription className={cn('leading-6', descriptionClassName)}>
            {description}
          </SheetDescription>
        ) : null}
      </SheetHeader>

      {formProps ? (
        <form {...formProps} className={cn('flex min-h-0 flex-1 flex-col', formProps.className)}>
          {body}
          {footer}
        </form>
      ) : (
        <>
          {body}
          {footer}
        </>
      )}
    </SheetContent>
  );
}

export function CrudDrawerFooter({
  children,
  closeLabel,
  closeDisabled = false,
  closeButtonClassName,
  className,
  actionsClassName,
  align = 'auto',
  onClose,
}: CrudDrawerFooterProps) {
  const resolvedAlign = align === 'auto' ? (children ? 'between' : 'end') : align;

  return (
    <SheetFooter
      className={cn(
        'px-4 py-4 sm:flex-row sm:items-center sm:px-6 sm:py-5',
        resolvedAlign === 'between' ? 'sm:justify-between' : 'sm:justify-end',
        className,
      )}
    >
      {children ? (
        <div
          className={cn(
            'flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:flex-wrap',
            actionsClassName,
          )}
        >
          {children}
        </div>
      ) : null}
      <Button
        type="button"
        variant="outline"
        className={cn(closeButtonBaseClassName, 'w-full sm:w-auto', closeButtonClassName)}
        onClick={onClose}
        disabled={closeDisabled}
      >
        {closeLabel}
      </Button>
    </SheetFooter>
  );
}
