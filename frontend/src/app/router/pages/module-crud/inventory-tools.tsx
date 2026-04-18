import { Plus } from 'lucide-react';

import { Button } from '@/components/ui/button';

import type { InventoryCreateMode } from './warehouse-utils';

export interface InventoryToolsProps {
  canCreate: boolean;
  pendingAction: boolean;
  labels: {
    incoming: string;
    outgoing: string;
    transfer: string;
  };
  onCreate: (mode: InventoryCreateMode) => void;
}

export function InventoryTools({
  canCreate,
  pendingAction,
  labels,
  onCreate,
}: InventoryToolsProps) {
  return (
    <div className="flex flex-wrap gap-2" data-tour="module-inventory-tools">
      <Button
        type="button"
        className="rounded-full shadow-[0_18px_42px_-28px_rgba(234,88,12,0.42)]"
        onClick={() => onCreate('incoming')}
        disabled={pendingAction || !canCreate}
        data-tour="module-new-record"
      >
        <Plus className="h-4 w-4" />
        {labels.incoming}
      </Button>
      <Button
        type="button"
        variant="outline"
        className="rounded-full border-border/75 bg-card px-5 shadow-[0_16px_38px_-28px_rgba(15,23,42,0.1)]"
        onClick={() => onCreate('outgoing')}
        disabled={pendingAction || !canCreate}
      >
        <Plus className="h-4 w-4" />
        {labels.outgoing}
      </Button>
      <Button
        type="button"
        variant="outline"
        className="rounded-full border-border/75 bg-card px-5 shadow-[0_16px_38px_-28px_rgba(15,23,42,0.1)]"
        onClick={() => onCreate('transfer')}
        disabled={pendingAction || !canCreate}
      >
        <Plus className="h-4 w-4" />
        {labels.transfer}
      </Button>
    </div>
  );
}
