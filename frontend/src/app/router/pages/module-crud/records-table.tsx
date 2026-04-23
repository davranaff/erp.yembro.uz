import { MoreHorizontal } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { EmptyState } from '@/components/ui/empty-state';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { CardSkeleton, TableSkeleton } from '@/components/ui/skeleton';
import type { CrudFieldMeta, CrudRecord } from '@/shared/api/backend-crud';
import { cn } from '@/shared/lib/cn';

import {
  EMPTY_TEXT,
  frostedPanelClassName,
  getDisplayValue,
  getRecordId,
  getStatusBadge,
  humanizeKey,
} from '../module-crud-page.helpers';

import type { ReactNode } from 'react';

function RecordActionsMenu({
  actions,
  triggerLabel,
}: {
  actions: ReactNode[];
  triggerLabel: string;
}) {
  if (actions.length === 0) {
    return null;
  }

  // Single-action cell: don't bother with the menu wrapper.
  if (actions.length === 1) {
    return <div className="flex justify-end">{actions}</div>;
  }

  return (
    <Popover>
      <PopoverTrigger
        aria-label={triggerLabel}
        onClick={(event) => {
          // The row's onClick also selects the record — stop it so the
          // menu trigger doesn't double-fire as "open record".
          event.stopPropagation();
        }}
        className={cn(
          'inline-flex h-8 w-8 items-center justify-center rounded-lg border border-border/75 bg-card',
          'text-muted-foreground shadow-[0_10px_24px_-20px_rgba(15,23,42,0.2)]',
          'transition-colors hover:bg-muted/60 hover:text-foreground',
          'outline-none aria-expanded:border-primary/40 aria-expanded:bg-secondary/60 aria-expanded:text-foreground',
          'focus-visible:ring-3 focus-visible:border-ring focus-visible:ring-ring/50',
        )}
      >
        <MoreHorizontal className="h-4 w-4" />
      </PopoverTrigger>
      <PopoverContent
        align="end"
        sideOffset={6}
        className={cn(
          'bg-popover w-56 rounded-xl border border-border/80 p-1.5',
          'shadow-[0_24px_56px_-36px_rgba(15,23,42,0.28)]',
        )}
        onClick={(event) => event.stopPropagation()}
      >
        <div
          className={cn(
            'flex flex-col gap-1',
            '[&>[data-slot=button]]:w-full [&>[data-slot=button]]:justify-start',
          )}
        >
          {actions}
        </div>
      </PopoverContent>
    </Popover>
  );
}

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

export interface RecordsTableViewProps {
  tableFields: CrudFieldMeta[];
  records: CrudRecord[];
  idColumn: string;
  selectedRecordId: string;
  totalCount: number;
  isLoading: boolean;
  hasRecordActions: boolean;
  activeResourceLabel: string;
  emptyLabel: string;
  yesLabel: string;
  noLabel: string;
  t: TranslateFn;
  translateReferenceLabel: ReferenceLabelTranslator;
  getRecordSummaryLabel: (record: CrudRecord) => string;
  onRecordFocus: (record: CrudRecord) => void;
  renderRecordActionButtons: (record: CrudRecord) => ReactNode[];
}

export function RecordsTableView({
  tableFields,
  records,
  idColumn,
  selectedRecordId,
  totalCount,
  isLoading,
  hasRecordActions,
  activeResourceLabel,
  emptyLabel,
  yesLabel,
  noLabel,
  t,
  translateReferenceLabel,
  getRecordSummaryLabel,
  onRecordFocus,
  renderRecordActionButtons,
}: RecordsTableViewProps) {
  const emptyTitle = t('crud.emptyResource', { resource: activeResourceLabel });
  const emptyDescription = t(
    'crud.emptyHint',
    undefined,
    'Создайте первую запись или измените фильтры, чтобы увидеть данные.',
  );

  return (
    <div className={`${frostedPanelClassName} overflow-hidden`}>
      <div className="max-h-[680px] overflow-y-auto p-3 sm:hidden">
        {isLoading ? (
          <CardSkeleton lines={3} />
        ) : totalCount === 0 ? (
          <EmptyState title={emptyTitle} description={emptyDescription} />
        ) : (
          <div className="space-y-3">
            {records.map((record) => {
              const recordId = getRecordId(record, idColumn);
              const isActive = recordId !== EMPTY_TEXT && recordId === selectedRecordId;
              const recordFieldEntries = tableFields.map((field) => {
                const displayValue = getDisplayValue(
                  field,
                  record[field.name],
                  yesLabel,
                  noLabel,
                  emptyLabel,
                  translateReferenceLabel,
                );

                return {
                  fieldName: field.name,
                  label: t(
                    `fields.${field.name}`,
                    undefined,
                    field.label || humanizeKey(field.name),
                  ),
                  displayValue,
                };
              });
              const primaryEntry =
                recordFieldEntries.find((entry) => entry.displayValue !== emptyLabel) ?? null;
              const detailEntries = recordFieldEntries.filter(
                (entry) => entry.fieldName !== primaryEntry?.fieldName,
              );

              return (
                <div
                  key={recordId || JSON.stringify(record)}
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
                          {primaryEntry?.displayValue ?? getRecordSummaryLabel(record)}
                        </p>
                        <p className="truncate text-xs text-muted-foreground">
                          {recordId || emptyLabel}
                        </p>
                      </div>
                    </button>
                  ) : (
                    <div className="space-y-1">
                      <p className="text-sm font-semibold text-foreground">
                        {primaryEntry?.displayValue ?? getRecordSummaryLabel(record)}
                      </p>
                      <p className="truncate text-xs text-muted-foreground">
                        {recordId || emptyLabel}
                      </p>
                    </div>
                  )}

                  <div className="mt-4 space-y-2">
                    {detailEntries.map((entry) => (
                      <div
                        key={entry.fieldName}
                        className="rounded-2xl border border-border/60 bg-background/80 px-3.5 py-3"
                      >
                        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                          {entry.label}
                        </p>
                        <p className="mt-1 break-words text-sm text-foreground">
                          {entry.displayValue}
                        </p>
                      </div>
                    ))}
                  </div>

                  {hasRecordActions ? (
                    <div className="mt-4 grid gap-2 [&>[data-slot=button]]:w-full">
                      {renderRecordActionButtons(record)}
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="hidden max-h-[680px] overflow-auto overscroll-x-contain sm:block">
        <table className="w-full min-w-[960px] border-collapse text-left text-sm">
          <thead className="sticky top-0 z-10 bg-card">
            <tr className="border-primary/16 border-b">
              {tableFields.map((field) => (
                <th
                  key={field.name}
                  className="whitespace-nowrap px-5 py-4 text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground"
                >
                  {t(`fields.${field.name}`, undefined, field.label || humanizeKey(field.name))}
                </th>
              ))}
              {hasRecordActions ? (
                <th className="sticky right-0 whitespace-nowrap bg-card px-5 py-4 text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                  {t('crud.actions')}
                </th>
              ) : null}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={tableFields.length + (hasRecordActions ? 1 : 0)} className="px-5 py-4">
                  <TableSkeleton rows={6} cols={Math.min(tableFields.length, 4)} />
                </td>
              </tr>
            ) : null}
            {records.map((record, rowIndex) => {
              const recordId = getRecordId(record, idColumn);
              const isActive = recordId !== EMPTY_TEXT && recordId === selectedRecordId;

              return (
                <tr
                  key={recordId || JSON.stringify(record)}
                  onClick={hasRecordActions ? () => onRecordFocus(record) : undefined}
                  aria-selected={hasRecordActions ? isActive : undefined}
                  className={cn(
                    'border-b border-border/50 transition-colors last:border-b-0',
                    isActive
                      ? 'bg-card shadow-[inset_4px_0_0_hsl(var(--primary))]'
                      : rowIndex % 2 === 0
                        ? 'bg-card'
                        : 'bg-card hover:bg-card',
                  )}
                >
                  {tableFields.map((field) => {
                    const rawValue = record[field.name];
                    const badge = getStatusBadge(field.name, rawValue);
                    if (badge) {
                      return (
                        <td key={field.name} className="px-5 py-4 align-top">
                          <Badge variant={badge.variant}>{badge.label}</Badge>
                        </td>
                      );
                    }
                    const displayValue = getDisplayValue(
                      field,
                      rawValue,
                      yesLabel,
                      noLabel,
                      emptyLabel,
                      translateReferenceLabel,
                    );

                    return (
                      <td key={field.name} className="px-5 py-4 align-top">
                        <span
                          className="block max-w-[240px] rounded-xl border border-border/75 bg-card px-3 py-2 text-foreground shadow-[0_12px_32px_-28px_rgba(15,23,42,0.1)]"
                          title={displayValue}
                        >
                          {displayValue}
                        </span>
                      </td>
                    );
                  })}
                  {hasRecordActions ? (
                    <td className="sticky right-0 whitespace-nowrap bg-inherit px-5 py-4 text-right">
                      <RecordActionsMenu
                        actions={renderRecordActionButtons(record)}
                        triggerLabel={t('crud.actions')}
                      />
                    </td>
                  ) : null}
                </tr>
              );
            })}
            {totalCount === 0 && !isLoading ? (
              <tr>
                <td colSpan={tableFields.length + (hasRecordActions ? 1 : 0)} className="px-5 py-2">
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
