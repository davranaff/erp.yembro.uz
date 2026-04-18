import { History, Trash2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { InlineLoader } from '@/components/ui/inline-loader';
import type { CrudFieldMeta, CrudRecord } from '@/shared/api/backend-crud';
import { cn } from '@/shared/lib/cn';

import {
  EMPTY_TEXT,
  formatDateValue,
  frostedPanelClassName,
  getRecordId,
  humanizeKey,
} from '../module-crud-page.helpers';

import { getWarehouseRecordLabel, type WarehouseRecord } from './warehouse-utils';

import type { MouseEvent as ReactMouseEvent, ReactNode } from 'react';

type TranslateFn = (
  key: string,
  params?: Record<string, string | number>,
  fallback?: string,
) => string;

type ReferenceLabelTranslator = (
  field: CrudFieldMeta,
  optionValue: string,
  optionLabel: string,
) => string;

export interface StockMovementCardsProps {
  records: CrudRecord[];
  isLoading: boolean;
  idColumn: string;
  selectedRecordId: string;
  deleteConfirmRecordId: string;
  pendingAction: boolean;
  hasRecordActions: boolean;
  canReadAuditActiveResource: boolean;
  canDeleteActiveResource: boolean;
  activeResourceLabel: string;
  emptyLabel: string;
  deleteConfirmLabel: string;
  deleteConfirmClassName: string;
  movementKindField: CrudFieldMeta | null;
  itemTypeField: CrudFieldMeta | null;
  unitField: CrudFieldMeta | null;
  warehouseById: Map<string, WarehouseRecord>;
  t: TranslateFn;
  translateReferenceLabel: ReferenceLabelTranslator;
  getInventoryPositionLabel: (itemType: string, itemKey: string) => string;
  onRecordFocus: (record: CrudRecord) => void;
  onOpenAudit: (record: CrudRecord) => void;
  onDeleteRecord: (event: ReactMouseEvent<HTMLButtonElement>, record: CrudRecord) => void;
}

type MovementDisplay = {
  recordId: string;
  movementKindLabel: string;
  itemTypeLabel: string;
  itemKeyLabel: string;
  unitLabel: string;
  warehouseLabel: string;
  counterpartyWarehouseLabel: string;
  quantity: string;
  note: string;
};

function buildMovementDisplay(
  record: CrudRecord,
  props: Pick<
    StockMovementCardsProps,
    | 'idColumn'
    | 'movementKindField'
    | 'itemTypeField'
    | 'unitField'
    | 'warehouseById'
    | 'emptyLabel'
    | 'translateReferenceLabel'
    | 'getInventoryPositionLabel'
  >,
): MovementDisplay {
  const {
    idColumn,
    movementKindField,
    itemTypeField,
    unitField,
    warehouseById,
    emptyLabel,
    translateReferenceLabel,
    getInventoryPositionLabel,
  } = props;

  const recordId = getRecordId(record, idColumn);
  const movementKind = typeof record.movement_kind === 'string' ? record.movement_kind.trim() : '';
  const itemType = typeof record.item_type === 'string' ? record.item_type.trim() : '';
  const itemKey = typeof record.item_key === 'string' ? record.item_key.trim() : '';
  const quantity = typeof record.quantity === 'string' ? record.quantity.trim() : '';
  const unit = typeof record.unit === 'string' ? record.unit.trim() : '';
  const warehouseId = typeof record.warehouse_id === 'string' ? record.warehouse_id.trim() : '';
  const counterpartyWarehouseId =
    typeof record.counterparty_warehouse_id === 'string'
      ? record.counterparty_warehouse_id.trim()
      : '';
  const note = typeof record.note === 'string' ? record.note.trim() : '';

  const movementKindLabel =
    movementKindField && movementKind
      ? translateReferenceLabel(movementKindField, movementKind, movementKind)
      : humanizeKey(movementKind);
  const itemTypeLabel =
    itemTypeField && itemType
      ? translateReferenceLabel(itemTypeField, itemType, itemType)
      : humanizeKey(itemType);
  const itemKeyLabel = getInventoryPositionLabel(itemType, itemKey);
  const unitLabel =
    unitField && unit ? translateReferenceLabel(unitField, unit, unit) : unit || emptyLabel;
  const warehouseLabel = warehouseId
    ? warehouseById.get(warehouseId)
      ? getWarehouseRecordLabel(warehouseById.get(warehouseId)!)
      : warehouseId
    : emptyLabel;
  const counterpartyWarehouseLabel = counterpartyWarehouseId
    ? warehouseById.get(counterpartyWarehouseId)
      ? getWarehouseRecordLabel(warehouseById.get(counterpartyWarehouseId)!)
      : counterpartyWarehouseId
    : '';

  return {
    recordId,
    movementKindLabel,
    itemTypeLabel,
    itemKeyLabel,
    unitLabel,
    warehouseLabel,
    counterpartyWarehouseLabel,
    quantity,
    note,
  };
}

export function StockMovementCards(props: StockMovementCardsProps) {
  const {
    records,
    isLoading,
    idColumn,
    selectedRecordId,
    deleteConfirmRecordId,
    pendingAction,
    hasRecordActions,
    canReadAuditActiveResource,
    canDeleteActiveResource,
    activeResourceLabel,
    emptyLabel,
    deleteConfirmLabel,
    deleteConfirmClassName,
    t,
    onRecordFocus,
    onOpenAudit,
    onDeleteRecord,
  } = props;

  const renderMovementActionButtons = (record: CrudRecord): ReactNode[] => {
    const recordId = getRecordId(record, idColumn);
    const actionKeyPrefix = recordId || 'movement';
    const isDeleteConfirming = recordId !== EMPTY_TEXT && deleteConfirmRecordId === recordId;
    const buttons: ReactNode[] = [];

    if (canReadAuditActiveResource) {
      buttons.push(
        <Button
          key={`${actionKeyPrefix}-history`}
          type="button"
          size="sm"
          variant="outline"
          className="border-border/75 bg-card"
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            onOpenAudit(record);
          }}
          disabled={pendingAction}
        >
          <History className="h-3.5 w-3.5" />
          {t('common.history')}
        </Button>,
      );
    }

    if (canDeleteActiveResource) {
      buttons.push(
        <Button
          key={`${actionKeyPrefix}-delete`}
          type="button"
          size="sm"
          variant={isDeleteConfirming ? 'destructive' : 'outline'}
          className={cn(
            isDeleteConfirming
              ? deleteConfirmClassName
              : 'border-destructive/25 bg-destructive/5 text-destructive hover:bg-destructive/10 hover:text-destructive',
          )}
          onClick={(event) => onDeleteRecord(event, record)}
          disabled={pendingAction}
        >
          <Trash2 className="h-3.5 w-3.5" />
          {isDeleteConfirming ? deleteConfirmLabel : t('common.delete')}
        </Button>,
      );
    }

    return buttons;
  };

  const emptyTitle = t('crud.emptyResource', { resource: activeResourceLabel });
  const emptyDescription = t(
    'crud.emptyHint',
    undefined,
    'Создайте первую запись или измените фильтры, чтобы увидеть данные.',
  );

  return (
    <div
      className={`${frostedPanelClassName} overflow-hidden`}
      data-tour="inventory-movements-list"
    >
      <div className="max-h-[680px] overflow-y-auto p-3 sm:hidden">
        {isLoading ? (
          <InlineLoader label={t('crud.loadingRecords', undefined, 'Загружаем данные…')} />
        ) : records.length === 0 ? (
          <EmptyState title={emptyTitle} description={emptyDescription} />
        ) : (
          <div className="space-y-3">
            {records.map((record) => {
              const display = buildMovementDisplay(record, props);
              const isActive =
                display.recordId !== EMPTY_TEXT && display.recordId === selectedRecordId;

              return (
                <div
                  key={display.recordId || JSON.stringify(record)}
                  className={cn(
                    'rounded-[22px] border p-4 shadow-[0_18px_42px_-34px_rgba(15,23,42,0.14)]',
                    isActive ? 'border-primary/30 bg-primary/5' : 'border-border/65 bg-card',
                  )}
                >
                  {hasRecordActions ? (
                    <button
                      type="button"
                      onClick={() => onRecordFocus(record)}
                      className="w-full text-left"
                    >
                      <div className="space-y-1">
                        <p className="text-sm font-semibold text-foreground">
                          {display.movementKindLabel}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {formatDateValue(record.occurred_on)}
                        </p>
                      </div>
                    </button>
                  ) : (
                    <div className="space-y-1">
                      <p className="text-sm font-semibold text-foreground">
                        {display.movementKindLabel}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {formatDateValue(record.occurred_on)}
                      </p>
                    </div>
                  )}

                  <div className="mt-4 space-y-2">
                    <div className="rounded-2xl border border-border/60 bg-background/80 px-3.5 py-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                        {t('fields.item_key', undefined, 'Позиция')}
                      </p>
                      <p className="mt-1 text-sm text-foreground">{display.itemKeyLabel}</p>
                      <p className="mt-1 text-xs text-muted-foreground">{display.itemTypeLabel}</p>
                    </div>

                    <div className="rounded-2xl border border-border/60 bg-background/80 px-3.5 py-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                        {t('fields.warehouse_id', undefined, 'Склад')}
                      </p>
                      <p className="mt-1 text-sm text-foreground">{display.warehouseLabel}</p>
                      {display.counterpartyWarehouseLabel ? (
                        <p className="mt-1 break-words text-xs text-muted-foreground">
                          {`${t('fields.counterparty_warehouse_id', undefined, 'Куда')}: ${display.counterpartyWarehouseLabel}`}
                        </p>
                      ) : null}
                    </div>

                    <div className="rounded-2xl border border-border/60 bg-background/80 px-3.5 py-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                        {t('fields.quantity', undefined, 'Количество')}
                      </p>
                      <p className="mt-1 text-sm text-foreground">
                        {display.quantity ? `${display.quantity} ${display.unitLabel}` : emptyLabel}
                      </p>
                    </div>

                    <div className="rounded-2xl border border-border/60 bg-background/80 px-3.5 py-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                        {t('fields.note', undefined, 'Комментарий')}
                      </p>
                      <p className="mt-1 break-words text-sm text-foreground">
                        {display.note || emptyLabel}
                      </p>
                    </div>
                  </div>

                  {hasRecordActions ? (
                    <div className="mt-4 grid gap-2 [&>[data-slot=button]]:w-full">
                      {renderMovementActionButtons(record)}
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="hidden max-h-[680px] overflow-auto overscroll-x-contain sm:block">
        <table className="w-full min-w-[980px] border-collapse text-left text-sm">
          <thead className="sticky top-0 z-10 bg-card">
            <tr className="border-primary/16 border-b">
              <th className="whitespace-nowrap px-5 py-4 text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                {t('fields.occurred_on', undefined, 'Дата')}
              </th>
              <th className="whitespace-nowrap px-5 py-4 text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                {t('fields.movement_kind', undefined, 'Операция')}
              </th>
              <th className="whitespace-nowrap px-5 py-4 text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                {t('fields.warehouse_id', undefined, 'Склад')}
              </th>
              <th className="whitespace-nowrap px-5 py-4 text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                {t('fields.item_key', undefined, 'Позиция')}
              </th>
              <th className="whitespace-nowrap px-5 py-4 text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                {t('fields.quantity', undefined, 'Количество')}
              </th>
              <th className="whitespace-nowrap px-5 py-4 text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                {t('fields.note', undefined, 'Комментарий')}
              </th>
              {hasRecordActions ? (
                <th className="whitespace-nowrap px-5 py-4 text-right text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                  {t('common.actions', undefined, 'Действия')}
                </th>
              ) : null}
            </tr>
          </thead>
          <tbody>
            {records.map((record) => {
              const display = buildMovementDisplay(record, props);

              return (
                <tr
                  key={display.recordId || JSON.stringify(record)}
                  className="border-b border-primary/10 last:border-b-0"
                >
                  <td className="whitespace-nowrap px-5 py-4 align-top text-foreground">
                    {formatDateValue(record.occurred_on)}
                  </td>
                  <td className="px-5 py-4 align-top">
                    <div className="space-y-1">
                      <p className="font-medium text-foreground">{display.movementKindLabel}</p>
                      <p className="text-xs text-muted-foreground">{display.itemTypeLabel}</p>
                    </div>
                  </td>
                  <td className="px-5 py-4 align-top">
                    <div className="space-y-1">
                      <p className="text-foreground">{display.warehouseLabel}</p>
                      {display.counterpartyWarehouseLabel ? (
                        <p className="text-xs text-muted-foreground">
                          {`${t('fields.counterparty_warehouse_id', undefined, 'Куда')}: ${display.counterpartyWarehouseLabel}`}
                        </p>
                      ) : null}
                    </div>
                  </td>
                  <td className="px-5 py-4 align-top text-foreground">{display.itemKeyLabel}</td>
                  <td className="whitespace-nowrap px-5 py-4 align-top text-foreground">
                    {display.quantity ? `${display.quantity} ${display.unitLabel}` : emptyLabel}
                  </td>
                  <td className="max-w-[280px] px-5 py-4 align-top text-muted-foreground">
                    {display.note || emptyLabel}
                  </td>
                  {hasRecordActions ? (
                    <td className="px-5 py-4 align-top">
                      <div className="flex justify-end gap-2">
                        {renderMovementActionButtons(record)}
                      </div>
                    </td>
                  ) : null}
                </tr>
              );
            })}
            {records.length === 0 && !isLoading ? (
              <tr>
                <td colSpan={hasRecordActions ? 7 : 6} className="px-5 py-2">
                  <EmptyState title={emptyTitle} description={emptyDescription} />
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
