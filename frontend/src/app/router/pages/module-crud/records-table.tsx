import { EmptyState } from '@/components/ui/empty-state';
import { InlineLoader } from '@/components/ui/inline-loader';
import type { CrudFieldMeta, CrudRecord } from '@/shared/api/backend-crud';
import { cn } from '@/shared/lib/cn';

import {
  EMPTY_TEXT,
  frostedPanelClassName,
  getDisplayValue,
  getRecordId,
  humanizeKey,
} from '../module-crud-page.helpers';

import type { ReactNode } from 'react';

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
          <InlineLoader label={t('crud.loadingRecords', undefined, 'Загружаем данные…')} />
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
                    const displayValue = getDisplayValue(
                      field,
                      record[field.name],
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
                    <td className="sticky right-0 whitespace-nowrap bg-inherit px-5 py-4">
                      <div className="flex flex-wrap justify-end gap-2">
                        {renderRecordActionButtons(record)}
                      </div>
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
