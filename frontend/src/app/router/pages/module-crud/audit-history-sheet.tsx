import { History } from 'lucide-react';

import { CrudDrawer, CrudDrawerFooter } from '@/components/ui/crud-drawer';
import { EmptyState } from '@/components/ui/empty-state';
import { ErrorNotice } from '@/components/ui/error-notice';
import { InlineLoader } from '@/components/ui/inline-loader';
import { Sheet } from '@/components/ui/sheet';
import type { CrudAuditEntry } from '@/shared/api/backend-crud';
import { cn } from '@/shared/lib/cn';

import { compactPillClassName, frostedPanelClassName } from '../module-crud-page.helpers';

import { AuditSnapshotView } from './audit-snapshot';

type TranslateFn = (
  key: string,
  params?: Record<string, string | number>,
  fallback?: string,
) => string;

export interface AuditHistorySheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onClose: () => void;
  activeResourceLabel: string;
  auditRecordLabel: string;
  auditRecordId: string;
  emptyLabel: string;
  t: TranslateFn;
  query: {
    isLoading: boolean;
    error: unknown;
  };
  auditHistoryItems: CrudAuditEntry[];
  getAuditFieldNames: (entry: CrudAuditEntry) => string[];
  getAuditActionLabel: (action: CrudAuditEntry['action']) => string;
  getAuditActionBadgeClassName: (action: CrudAuditEntry['action']) => string;
  formatAuditTimestamp: (timestamp: string) => string;
  getAuditFieldLabel: (fieldName: string) => string;
  getAuditFieldDisplayValue: (fieldName: string, value: unknown) => string;
}

export function AuditHistorySheet({
  open,
  onOpenChange,
  onClose,
  activeResourceLabel,
  auditRecordLabel,
  auditRecordId,
  emptyLabel,
  t,
  query,
  auditHistoryItems,
  getAuditFieldNames,
  getAuditActionLabel,
  getAuditActionBadgeClassName,
  formatAuditTimestamp,
  getAuditFieldLabel,
  getAuditFieldDisplayValue,
}: AuditHistorySheetProps) {
  const auditNoSnapshotLabel = t('crud.auditNoSnapshot');

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <CrudDrawer
        dataTour="module-audit-drawer"
        size="audit"
        title={t('crud.auditTitle')}
        description=""
        footer={<CrudDrawerFooter closeLabel={t('common.close')} onClose={onClose} />}
      >
        <div className={`${frostedPanelClassName} space-y-2 px-4 py-4`}>
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            {activeResourceLabel}
          </p>
          <p className="text-lg font-semibold tracking-[-0.03em] text-foreground">
            {auditRecordLabel || auditRecordId || emptyLabel}
          </p>
        </div>

        <div className="space-y-4" data-tour="module-audit-history">
          {query.isLoading ? (
            <div className={frostedPanelClassName}>
              <InlineLoader
                label={t('crud.loadingAuditHistory', undefined, 'Загружаем историю…')}
              />
            </div>
          ) : null}

          {query.error ? <ErrorNotice error={query.error} /> : null}

          {!query.isLoading && !query.error && auditHistoryItems.length === 0 ? (
            <div className={frostedPanelClassName}>
              <EmptyState
                icon={History}
                title={t('crud.auditEmpty')}
                description={t(
                  'crud.auditEmptyHint',
                  undefined,
                  'Изменения по этой записи появятся здесь автоматически.',
                )}
              />
            </div>
          ) : null}

          {!query.isLoading && !query.error ? (
            <div className="space-y-4">
              {auditHistoryItems.map((entry) => {
                const entryFieldNames = getAuditFieldNames(entry);

                return (
                  <article key={entry.id} className={`${frostedPanelClassName} space-y-4 p-4`}>
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={cn(
                          'rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em]',
                          getAuditActionBadgeClassName(entry.action),
                        )}
                      >
                        {getAuditActionLabel(entry.action)}
                      </span>
                      <span className={compactPillClassName}>
                        {`${t('crud.auditChangedBy')}: ${entry.actor_username || emptyLabel}`}
                      </span>
                      <span className={compactPillClassName}>
                        {`${t('crud.auditChangedAt')}: ${formatAuditTimestamp(entry.changed_at)}`}
                      </span>
                    </div>

                    {entryFieldNames.length > 0 ? (
                      <div className="space-y-2">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                          {t('crud.auditChangedFields')}
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {entryFieldNames.map((fieldName) => (
                            <span key={fieldName} className={compactPillClassName}>
                              {getAuditFieldLabel(fieldName)}
                            </span>
                          ))}
                        </div>
                      </div>
                    ) : null}

                    <div className="grid gap-4 xl:grid-cols-2">
                      <div className="space-y-2">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                          {t('crud.auditBefore')}
                        </p>
                        <AuditSnapshotView
                          snapshot={entry.before_data}
                          fieldNames={entryFieldNames}
                          emptyLabel={auditNoSnapshotLabel}
                          getFieldLabel={getAuditFieldLabel}
                          getFieldDisplayValue={getAuditFieldDisplayValue}
                        />
                      </div>
                      <div className="space-y-2">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                          {t('crud.auditAfter')}
                        </p>
                        <AuditSnapshotView
                          snapshot={entry.after_data}
                          fieldNames={entryFieldNames}
                          emptyLabel={auditNoSnapshotLabel}
                          getFieldLabel={getAuditFieldLabel}
                          getFieldDisplayValue={getAuditFieldDisplayValue}
                        />
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          ) : null}
        </div>
      </CrudDrawer>
    </Sheet>
  );
}
