'use client';

import { Dialog } from '@base-ui/react/dialog';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

type ConfirmDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  confirmLabel: string;
  cancelLabel: string;
  onConfirm: () => void;
  onCancel?: () => void;
  confirmVariant?: 'default' | 'destructive';
  confirmDisabled?: boolean;
  cancelDisabled?: boolean;
};

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  cancelLabel,
  onConfirm,
  onCancel,
  confirmVariant = 'destructive',
  confirmDisabled = false,
  cancelDisabled = false,
}: ConfirmDialogProps) {
  return (
    <Dialog.Root open={open} onOpenChange={(nextOpen) => onOpenChange(nextOpen)}>
      <Dialog.Portal>
        <Dialog.Backdrop
          className={cn(
            'data-ending-style:opacity-0 data-starting-style:opacity-0 fixed inset-0 z-[70] bg-[rgba(15,23,42,0.28)] backdrop-blur-[3px] transition-opacity duration-200 ease-out',
          )}
        />
        <Dialog.Popup
          className={cn(
            'data-ending-style:opacity-0 data-starting-style:opacity-0 data-ending-style:scale-[0.98] data-starting-style:scale-[0.98] bg-background/98 fixed left-1/2 top-1/2 z-[71] w-[min(92vw,32rem)] -translate-x-1/2 -translate-y-1/2 rounded-[28px] border border-border/75 p-6 shadow-[0_32px_96px_-48px_rgba(15,23,42,0.28)] backdrop-blur-xl transition duration-200 ease-out',
          )}
        >
          <div className="space-y-2">
            <Dialog.Title className="text-lg font-semibold tracking-[-0.03em] text-foreground">
              {title}
            </Dialog.Title>
            {description ? (
              <Dialog.Description className="text-sm leading-6 text-muted-foreground">
                {description}
              </Dialog.Description>
            ) : null}
          </div>

          <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button
              type="button"
              variant="outline"
              className="border-border/75 bg-card"
              disabled={cancelDisabled}
              onClick={() => {
                onCancel?.();
                onOpenChange(false);
              }}
            >
              {cancelLabel}
            </Button>
            <Button
              type="button"
              variant={confirmVariant}
              disabled={confirmDisabled}
              onClick={() => {
                onConfirm();
                onOpenChange(false);
              }}
            >
              {confirmLabel}
            </Button>
          </div>
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
