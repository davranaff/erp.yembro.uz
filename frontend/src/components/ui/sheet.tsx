'use client';

import { Dialog as SheetPrimitive } from '@base-ui/react/dialog';
import { XIcon } from 'lucide-react';
import * as React from 'react';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useI18n } from '@/shared/i18n';

const SHEET_OPEN_EVENT = 'yembro:sheet-open';

type SheetOpenEventDetail = {
  id: string;
};

function Sheet({
  open,
  defaultOpen,
  onOpenChange,
  onOpenChangeComplete,
  ...props
}: SheetPrimitive.Root.Props) {
  const sheetId = React.useId();
  const isControlled = typeof open === 'boolean';
  const [internalOpen, setInternalOpen] = React.useState(Boolean(defaultOpen));
  const resolvedOpen = isControlled ? open : internalOpen;

  const handleOpenChange = React.useCallback<
    NonNullable<SheetPrimitive.Root.Props['onOpenChange']>
  >(
    (nextOpen, eventDetails) => {
      if (!isControlled) {
        setInternalOpen(nextOpen);
      }
      onOpenChange?.(nextOpen, eventDetails);
    },
    [isControlled, onOpenChange],
  );

  const handleOpenChangeComplete = React.useCallback<
    NonNullable<SheetPrimitive.Root.Props['onOpenChangeComplete']>
  >(
    (nextOpen) => {
      if (!isControlled) {
        setInternalOpen(nextOpen);
      }
      onOpenChangeComplete?.(nextOpen);
    },
    [isControlled, onOpenChangeComplete],
  );

  React.useEffect(() => {
    if (typeof window === 'undefined' || !resolvedOpen) {
      return;
    }
    window.dispatchEvent(
      new CustomEvent<SheetOpenEventDetail>(SHEET_OPEN_EVENT, { detail: { id: sheetId } }),
    );
  }, [resolvedOpen, sheetId]);

  React.useEffect(() => {
    if (typeof window === 'undefined' || !resolvedOpen) {
      return;
    }

    const handleOtherSheetOpen = (event: Event) => {
      const detail = (event as CustomEvent<SheetOpenEventDetail>).detail;
      if (detail.id === sheetId) {
        return;
      }
      handleOpenChange(false, {} as SheetPrimitive.Root.ChangeEventDetails);
    };

    window.addEventListener(SHEET_OPEN_EVENT, handleOtherSheetOpen as EventListener);
    return () => {
      window.removeEventListener(SHEET_OPEN_EVENT, handleOtherSheetOpen as EventListener);
    };
  }, [handleOpenChange, resolvedOpen, sheetId]);

  return (
    <SheetPrimitive.Root
      data-slot="sheet"
      open={resolvedOpen}
      onOpenChange={handleOpenChange}
      onOpenChangeComplete={handleOpenChangeComplete}
      {...props}
    />
  );
}

function SheetTrigger({ ...props }: SheetPrimitive.Trigger.Props) {
  return <SheetPrimitive.Trigger data-slot="sheet-trigger" {...props} />;
}

function SheetClose({ ...props }: SheetPrimitive.Close.Props) {
  return <SheetPrimitive.Close data-slot="sheet-close" {...props} />;
}

function SheetPortal({ ...props }: SheetPrimitive.Portal.Props) {
  return <SheetPrimitive.Portal data-slot="sheet-portal" {...props} />;
}

function SheetOverlay({ className, ...props }: SheetPrimitive.Backdrop.Props) {
  return (
    <SheetPrimitive.Backdrop
      data-slot="sheet-overlay"
      className={cn(
        'data-ending-style:opacity-0 data-starting-style:opacity-0 fixed inset-0 z-50 bg-[rgba(15,23,42,0.22)] backdrop-blur-[2px] transition-opacity duration-200 ease-out',
        className,
      )}
      {...props}
    />
  );
}

function SheetContent({
  className,
  children,
  side = 'right',
  showCloseButton = true,
  ...props
}: SheetPrimitive.Popup.Props & {
  side?: 'top' | 'right' | 'bottom' | 'left';
  showCloseButton?: boolean;
}) {
  const { t } = useI18n();

  return (
    <SheetPortal>
      <SheetOverlay />
      <SheetPrimitive.Popup
        data-slot="sheet-content"
        data-side={side}
        className={cn(
          'supports-[backdrop-filter]:bg-background/96 data-ending-style:opacity-0 data-starting-style:opacity-0 data-[side=bottom]:data-ending-style:translate-y-[2.5rem] data-[side=bottom]:data-starting-style:translate-y-[2.5rem] data-[side=left]:data-ending-style:translate-x-[-2.5rem] data-[side=left]:data-starting-style:translate-x-[-2.5rem] data-[side=right]:data-ending-style:translate-x-[2.5rem] data-[side=right]:data-starting-style:translate-x-[2.5rem] data-[side=top]:data-ending-style:translate-y-[-2.5rem] data-[side=top]:data-starting-style:translate-y-[-2.5rem] border-primary/16 bg-background/99 fixed z-50 flex min-h-0 flex-col gap-4 overflow-hidden overscroll-contain bg-clip-padding text-sm shadow-[0_32px_96px_-48px_rgba(15,23,42,0.26)] backdrop-blur-xl transition duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] will-change-transform data-[side=bottom]:inset-x-0 data-[side=left]:inset-y-0 data-[side=right]:inset-y-0 data-[side=top]:inset-x-0 data-[side=bottom]:bottom-0 data-[side=left]:left-0 data-[side=right]:right-0 data-[side=top]:top-0 data-[side=left]:h-[100dvh] data-[side=right]:h-[100dvh] data-[side=top]:h-auto data-[side=bottom]:max-h-[100dvh] data-[side=left]:max-h-[100dvh] data-[side=right]:max-h-[100dvh] data-[side=left]:w-3/4 data-[side=right]:w-3/4 data-[side=bottom]:border-t data-[side=left]:border-r data-[side=right]:border-l data-[side=top]:border-b data-[side=left]:sm:max-w-sm data-[side=right]:sm:max-w-sm',
          className,
        )}
        {...props}
      >
        {children}
        {showCloseButton && (
          <SheetPrimitive.Close
            data-slot="sheet-close"
            aria-label={t('common.close')}
            render={
              <Button
                variant="outline"
                className="border-primary/18 bg-background/98 absolute right-3 top-3 shadow-[0_14px_32px_-26px_rgba(15,23,42,0.14)]"
                size="icon-sm"
                aria-label={t('common.close')}
              />
            }
          >
            <XIcon />
            <span className="sr-only">{t('common.close')}</span>
          </SheetPrimitive.Close>
        )}
      </SheetPrimitive.Popup>
    </SheetPortal>
  );
}

function SheetHeader({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="sheet-header"
      className={cn(
        'border-primary/14 bg-background/96 flex shrink-0 flex-col gap-0.5 border-b p-4 backdrop-blur-xl',
        className,
      )}
      {...props}
    />
  );
}

function SheetFooter({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="sheet-footer"
      className={cn(
        'border-primary/14 bg-background/96 mt-auto flex shrink-0 flex-row flex-wrap items-center justify-end gap-2 border-t p-4 backdrop-blur-xl',
        className,
      )}
      {...props}
    />
  );
}

function SheetTitle({ className, ...props }: SheetPrimitive.Title.Props) {
  return (
    <SheetPrimitive.Title
      data-slot="sheet-title"
      className={cn('text-base font-medium text-foreground', className)}
      {...props}
    />
  );
}

function SheetDescription({ className, ...props }: SheetPrimitive.Description.Props) {
  return (
    <SheetPrimitive.Description
      data-slot="sheet-description"
      className={cn('text-sm text-muted-foreground', className)}
      {...props}
    />
  );
}

export {
  Sheet,
  SheetTrigger,
  SheetClose,
  SheetContent,
  SheetHeader,
  SheetFooter,
  SheetTitle,
  SheetDescription,
};
