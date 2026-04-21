'use client';

import { Dialog } from '@base-ui/react/dialog';
import { useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { cn } from '@/shared/lib/cn';

interface ShipmentAcknowledgeDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  receivedQuantityLabel: string;
  noteLabel: string;
  confirmLabel: string;
  cancelLabel: string;
  defaultReceivedQuantity: string;
  submitting?: boolean;
  onConfirm: (payload: { received_quantity: string; note?: string }) => void;
}

export function ShipmentAcknowledgeDialog({
  open,
  onOpenChange,
  title,
  description,
  receivedQuantityLabel,
  noteLabel,
  confirmLabel,
  cancelLabel,
  defaultReceivedQuantity,
  submitting = false,
  onConfirm,
}: ShipmentAcknowledgeDialogProps) {
  const [receivedQuantity, setReceivedQuantity] = useState(defaultReceivedQuantity);
  const [note, setNote] = useState('');

  useEffect(() => {
    if (open) {
      setReceivedQuantity(defaultReceivedQuantity);
      setNote('');
    }
  }, [open, defaultReceivedQuantity]);

  const canSubmit = receivedQuantity.trim().length > 0 && !submitting;

  return (
    <Dialog.Root open={open} onOpenChange={(next) => onOpenChange(next)}>
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
            <Dialog.Description className="text-sm leading-6 text-muted-foreground">
              {description}
            </Dialog.Description>
          </div>

          <div className="mt-5 space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="ack-received-quantity">{receivedQuantityLabel}</Label>
              <Input
                id="ack-received-quantity"
                type="number"
                inputMode="decimal"
                step="0.001"
                min="0"
                value={receivedQuantity}
                onChange={(event) => setReceivedQuantity(event.target.value)}
                autoFocus
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ack-note">{noteLabel}</Label>
              <Input id="ack-note" value={note} onChange={(event) => setNote(event.target.value)} />
            </div>
          </div>

          <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:justify-end">
            <Button
              type="button"
              variant="outline"
              className="border-border/75 bg-card"
              disabled={submitting}
              onClick={() => onOpenChange(false)}
            >
              {cancelLabel}
            </Button>
            <Button
              type="button"
              disabled={!canSubmit}
              onClick={() => {
                onConfirm({
                  received_quantity: receivedQuantity.trim(),
                  note: note.trim() || undefined,
                });
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
