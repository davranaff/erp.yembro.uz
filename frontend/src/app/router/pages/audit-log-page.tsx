import { Search, X } from 'lucide-react';
import { useDeferredValue, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import { RouteStatusScreen } from '@/app/router/ui/route-status-screen';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { CrudDrawer, CrudDrawerFooter } from '@/components/ui/crud-drawer';
import { CustomSelect } from '@/components/ui/custom-select';
import { ErrorNotice } from '@/components/ui/error-notice';
import { Input } from '@/components/ui/input';
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination';
import { Sheet } from '@/components/ui/sheet';
import {
  listSystemAuditLogs,
  type CrudAuditAction,
  type CrudAuditEntry,
  type CrudAuditResponse,
} from '@/shared/api/backend-crud';
import { baseQueryKeys } from '@/shared/api/query-keys';
import { useApiQuery } from '@/shared/api/react-query';
import { canReadAuditLogs, useAuthStore } from '@/shared/auth';
import { useI18n } from '@/shared/i18n';
import { cn } from '@/shared/lib/cn';

const pageSize = 20;
const changedFieldsPreviewLimit = 3;
const heroCardClassName =
  'relative overflow-hidden rounded-[30px] border border-border/70 bg-card shadow-[0_28px_88px_-56px_rgba(15,23,42,0.16)]';
const frostedPanelClassName =
  'rounded-[24px] border border-border/70 bg-card shadow-[0_20px_56px_-40px_rgba(15,23,42,0.14)]';
const compactPillClassName =
  'rounded-full border border-border/75 bg-card px-3 py-1.5 text-xs font-medium text-muted-foreground shadow-[0_16px_36px_-30px_rgba(15,23,42,0.1)]';
const inputBaseClassName =
  'flex h-11 w-full rounded-2xl border border-border/75 bg-card px-4 py-3 text-sm text-foreground shadow-[0_16px_38px_-30px_rgba(15,23,42,0.12)] ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50';
const EMPTY_AUTH_LIST: string[] = [];

type AuditSnapshot = Record<string, unknown>;

const humanizeKey = (value: string): string =>
  value
    .split(/[-_]/g)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');

const isAuditSnapshot = (value: unknown): value is AuditSnapshot => {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
};

const isStructuredAuditValue = (value: unknown): boolean => {
  if (Array.isArray(value)) {
    return value.some((item) => typeof item === 'object' && item !== null);
  }

  return typeof value === 'object' && value !== null;
};

const formatDateTimeDisplayValue = (value: unknown): string => {
  if (typeof value !== 'string' || value.length === 0) {
    return '';
  }

  const parsed = new Date(value);
  if (!Number.isNaN(parsed.getTime())) {
    return parsed.toLocaleString();
  }

  const normalized = value.replace(/Z$/, '');
  return normalized ? normalized.replace('T', ' ') : '';
};

const formatAuditValue = (
  value: unknown,
  emptyLabel: string,
  yesLabel: string,
  noLabel: string,
): string => {
  if (value === null || value === undefined || value === '') {
    return emptyLabel;
  }

  if (typeof value === 'boolean') {
    return value ? yesLabel : noLabel;
  }

  if (typeof value === 'string') {
    if (/^\d{4}-\d{2}-\d{2}[tT ]/.test(value)) {
      return formatDateTimeDisplayValue(value);
    }
    return value;
  }

  if (typeof value === 'number' || typeof value === 'bigint') {
    return String(value);
  }

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return emptyLabel;
    }
    if (value.some((item) => typeof item === 'object' && item !== null)) {
      return JSON.stringify(value, null, 2);
    }
    return value.map((item) => formatAuditValue(item, emptyLabel, yesLabel, noLabel)).join(', ');
  }

  return JSON.stringify(value, null, 2);
};

const toUtcIsoString = (value: string): string | undefined => {
  const normalized = value.trim();
  if (!normalized) {
    return undefined;
  }

  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) {
    return undefined;
  }

  return parsed.toISOString();
};

const getPaginationItems = (currentPage: number, totalPages: number): Array<number | string> => {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  const items: Array<number | string> = [1];
  const windowStart = Math.max(2, currentPage - 1);
  const windowEnd = Math.min(totalPages - 1, currentPage + 1);

  if (windowStart > 2) {
    items.push('left-ellipsis');
  }

  for (let page = windowStart; page <= windowEnd; page += 1) {
    items.push(page);
  }

  if (windowEnd < totalPages - 1) {
    items.push('right-ellipsis');
  }

  items.push(totalPages);
  return items;
};

export function AuditLogPage() {
  const { t, locale } = useI18n();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const storedSessionRoles = useAuthStore((state) => state.session?.roles);
  const storedSessionPermissions = useAuthStore((state) => state.session?.permissions);
  const sessionRoles = storedSessionRoles ?? EMPTY_AUTH_LIST;
  const sessionPermissions = storedSessionPermissions ?? EMPTY_AUTH_LIST;
  const canOpenPage = canReadAuditLogs(sessionRoles, sessionPermissions);

  const search = searchParams.get('search') ?? '';
  const entityTable = searchParams.get('entityTable') ?? '';
  const entityId = searchParams.get('entityId') ?? '';
  const action = searchParams.get('action') ?? '';
  const changedFrom = searchParams.get('changedFrom') ?? '';
  const changedTo = searchParams.get('changedTo') ?? '';
  const pageParam = Number.parseInt(searchParams.get('page') ?? '1', 10);
  const currentPage = Number.isFinite(pageParam) && pageParam > 0 ? pageParam : 1;
  const offset = (currentPage - 1) * pageSize;
  const deferredSearch = useDeferredValue(search.trim());
  const deferredEntityTable = useDeferredValue(entityTable.trim());
  const deferredEntityId = useDeferredValue(entityId.trim());
  const deferredAction = useDeferredValue(action.trim());
  const [selectedEntryId, setSelectedEntryId] = useState('');
  const [isDetailsSheetOpen, setIsDetailsSheetOpen] = useState(false);
  const emptyLabel = t('common.empty');
  const auditActionOptions = useMemo(
    () => [
      { value: '', label: t('audit.actionAll', undefined, 'Все') },
      { value: 'create', label: t('crud.auditActionCreate') },
      { value: 'update', label: t('crud.auditActionUpdate') },
      { value: 'delete', label: t('crud.auditActionDelete') },
    ],
    [t],
  );
  const yesLabel = t('common.yes');
  const noLabel = t('common.no');

  const auditQuery = useApiQuery<CrudAuditResponse>({
    queryKey: [
      ...baseQueryKeys.system.audit,
      deferredSearch,
      deferredEntityTable,
      deferredEntityId,
      deferredAction,
      changedFrom.trim(),
      changedTo.trim(),
      currentPage,
    ],
    queryFn: () =>
      listSystemAuditLogs({
        search: deferredSearch || undefined,
        entityTable: deferredEntityTable || undefined,
        entityId: deferredEntityId || undefined,
        action: (deferredAction as CrudAuditAction | '') || undefined,
        changedFrom: toUtcIsoString(changedFrom),
        changedTo: toUtcIsoString(changedTo),
        limit: pageSize,
        offset,
      }),
    enabled: canOpenPage,
  });

  const auditEntries = useMemo(() => auditQuery.data?.items ?? [], [auditQuery.data?.items]);
  const totalCount = auditQuery.data?.total ?? 0;
  const totalPages = Math.max(Math.ceil(totalCount / pageSize), 1);
  const activeFilterCount = useMemo(
    () =>
      [search, entityTable, entityId, action, changedFrom, changedTo].filter(
        (value) => value.trim().length > 0,
      ).length,
    [action, changedFrom, changedTo, entityId, entityTable, search],
  );
  const paginationItems = useMemo(
    () => getPaginationItems(currentPage, totalPages),
    [currentPage, totalPages],
  );
  const selectedEntry = useMemo(
    () => auditEntries.find((entry) => entry.id === selectedEntryId) ?? null,
    [auditEntries, selectedEntryId],
  );
  const dateTimeFormatter = useMemo(
    () =>
      new Intl.DateTimeFormat(locale, {
        dateStyle: 'medium',
        timeStyle: 'short',
      }),
    [locale],
  );

  const updateSearch = (updates: Record<string, string | undefined>) => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);

      Object.entries(updates).forEach(([key, value]) => {
        const normalized = (value ?? '').trim();
        if (normalized) {
          next.set(key, normalized);
        } else {
          next.delete(key);
        }
      });

      if (!('page' in updates)) {
        next.delete('page');
      }

      return next;
    });
  };

  const openEntryDetails = (entry: CrudAuditEntry) => {
    setSelectedEntryId(entry.id);
    setIsDetailsSheetOpen(true);
  };

  const formatEntryTimestamp = (value: string): string => {
    const changedAt = new Date(value);
    if (Number.isNaN(changedAt.getTime())) {
      return value;
    }
    return dateTimeFormatter.format(changedAt);
  };

  const getEntryActionLabel = (entryAction: CrudAuditAction): string => {
    switch (entryAction) {
      case 'create':
        return t('crud.auditActionCreate');
      case 'delete':
        return t('crud.auditActionDelete');
      case 'update':
      default:
        return t('crud.auditActionUpdate');
    }
  };

  const getEntryActionBadgeClassName = (entryAction: CrudAuditAction): string => {
    switch (entryAction) {
      case 'create':
        return 'border-emerald-200 bg-emerald-50 text-emerald-700';
      case 'delete':
        return 'border-destructive/20 bg-destructive/10 text-destructive';
      case 'update':
      default:
        return 'border-primary/20 bg-primary/10 text-primary';
    }
  };

  const getChangedFieldNames = (entry: CrudAuditEntry): string[] => {
    const explicitFields = (entry.changed_fields ?? [])
      .map((fieldName) => String(fieldName).trim())
      .filter((fieldName) => fieldName.length > 0);
    if (explicitFields.length > 0) {
      return explicitFields;
    }

    const fieldNames = new Set<string>();
    if (isAuditSnapshot(entry.before_data)) {
      Object.keys(entry.before_data).forEach((fieldName) => fieldNames.add(fieldName));
    }
    if (isAuditSnapshot(entry.after_data)) {
      Object.keys(entry.after_data).forEach((fieldName) => fieldNames.add(fieldName));
    }
    return Array.from(fieldNames).sort();
  };
  const selectedChangedFields = useMemo(
    () => (selectedEntry ? getChangedFieldNames(selectedEntry) : []),
    [selectedEntry],
  );

  const renderAuditCards = () => {
    if (auditQuery.isLoading) {
      return (
        <div className="px-4 py-14 text-center text-sm text-muted-foreground">
          {t('common.loadingLabel')}
        </div>
      );
    }

    if (totalCount === 0) {
      return (
        <div className="px-4 py-14 text-center text-sm text-muted-foreground">
          {t('audit.empty', undefined, 'По текущим фильтрам изменений не найдено.')}
        </div>
      );
    }

    return (
      <div className="space-y-3 p-3">
        {auditEntries.map((entry) => {
          const changedFields = getChangedFieldNames(entry);
          const changedFieldsPreview = changedFields.slice(0, changedFieldsPreviewLimit);
          const hiddenChangedFieldsCount = Math.max(
            0,
            changedFields.length - changedFieldsPreview.length,
          );
          const isActive = selectedEntryId === entry.id;

          return (
            <button
              key={entry.id}
              type="button"
              onClick={() => openEntryDetails(entry)}
              data-tour="audit-open-details"
              className={cn(
                'w-full rounded-[22px] border p-4 text-left shadow-[0_18px_42px_-34px_rgba(15,23,42,0.14)] transition-colors',
                isActive
                  ? 'border-primary/30 bg-primary/5'
                  : 'hover:border-primary/18 border-border/65 bg-card hover:bg-muted/20',
              )}
            >
              <div className="flex flex-col gap-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 space-y-1">
                    <p className="text-sm font-semibold text-foreground">
                      {formatEntryTimestamp(entry.changed_at)}
                    </p>
                    <p className="truncate text-xs text-muted-foreground" title={entry.entity_id}>
                      {entry.entity_id}
                    </p>
                  </div>
                  <span
                    className={cn(
                      'inline-flex rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em]',
                      getEntryActionBadgeClassName(entry.action),
                    )}
                  >
                    {getEntryActionLabel(entry.action)}
                  </span>
                </div>

                <div className="grid gap-3">
                  <div className="space-y-1">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                      {t('common.record', undefined, 'Запись')}
                    </p>
                    <p className="text-sm font-medium text-foreground">
                      {humanizeKey(entry.entity_table)}
                    </p>
                  </div>

                  <div className="space-y-1">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                      {t('crud.auditChangedBy')}
                    </p>
                    <p className="text-sm text-foreground">{entry.actor_username || emptyLabel}</p>
                  </div>

                  <div className="space-y-2">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                      {t('crud.auditChangedFields')}
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {changedFieldsPreview.length > 0 ? (
                        <>
                          {changedFieldsPreview.map((fieldName) => (
                            <span
                              key={fieldName}
                              className={cn(
                                compactPillClassName,
                                'max-w-full truncate px-2.5 py-1 shadow-none',
                              )}
                              title={humanizeKey(fieldName)}
                            >
                              {humanizeKey(fieldName)}
                            </span>
                          ))}
                          {hiddenChangedFieldsCount > 0 ? (
                            <span
                              key={`${entry.id}-hidden-fields`}
                              className={cn(compactPillClassName, 'px-2.5 py-1 shadow-none')}
                              title={t(
                                'audit.hiddenFieldsCount',
                                { count: hiddenChangedFieldsCount },
                                `Скрыто полей: ${hiddenChangedFieldsCount}`,
                              )}
                            >
                              +{hiddenChangedFieldsCount}
                            </span>
                          ) : null}
                        </>
                      ) : (
                        <span className={cn(compactPillClassName, 'px-2.5 py-1 shadow-none')}>
                          {emptyLabel}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    );
  };

  const renderSnapshot = (snapshot: AuditSnapshot | null | undefined, changedFields: string[]) => {
    if (!isAuditSnapshot(snapshot)) {
      return (
        <div className={`${frostedPanelClassName} px-4 py-6 text-sm text-muted-foreground`}>
          {t('crud.auditNoSnapshot')}
        </div>
      );
    }

    const orderedFields =
      changedFields.length > 0
        ? changedFields.filter((fieldName) => fieldName in snapshot)
        : Object.keys(snapshot).sort();

    if (orderedFields.length === 0) {
      return (
        <div className={`${frostedPanelClassName} px-4 py-6 text-sm text-muted-foreground`}>
          {t('crud.auditNoSnapshot')}
        </div>
      );
    }

    return (
      <div className="space-y-2">
        {orderedFields.map((fieldName) => {
          const rawValue = snapshot[fieldName];
          const displayValue = formatAuditValue(rawValue, emptyLabel, yesLabel, noLabel);

          return (
            <div
              key={fieldName}
              className={`${frostedPanelClassName} border-border/60 px-4 py-3 shadow-none`}
            >
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                {humanizeKey(fieldName)}
              </p>
              {isStructuredAuditValue(rawValue) ? (
                <pre className="mt-2 whitespace-pre-wrap break-all text-xs leading-5 text-foreground">
                  {displayValue}
                </pre>
              ) : (
                <p className="mt-1 break-words text-sm text-foreground">{displayValue}</p>
              )}
            </div>
          );
        })}
      </div>
    );
  };

  if (!canOpenPage) {
    return (
      <RouteStatusScreen
        label={t('nav.audit', undefined, 'Аудит')}
        title={t('route.forbiddenTitle', undefined, 'Доступ ограничен')}
        description={t('route.auditForbiddenDescription')}
        status="forbidden"
        actionLabel={t('common.back')}
        onAction={() => navigate(-1)}
      />
    );
  }

  return (
    <div className="space-y-6" data-tour="audit-page">
      <Card className={heroCardClassName} data-tour="audit-hero">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              'radial-gradient(circle at 86% 12%, hsl(var(--accent) / 0.12), transparent 26%), radial-gradient(circle at 10% 0%, hsl(var(--primary) / 0.1), transparent 18%)',
          }}
        />
        <CardContent className="relative space-y-5 p-5 sm:p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-2">
              <span className="inline-flex items-center rounded-full border border-border/70 bg-card/80 px-3 py-1 text-xs font-medium text-muted-foreground">
                {t('common.history')}
              </span>
              <h1
                className="text-3xl font-semibold tracking-[-0.05em] text-foreground sm:text-4xl"
                style={{ fontFamily: 'Fraunces, serif' }}
              >
                {t('nav.audit', undefined, 'Аудит')}
              </h1>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <div className={cn(frostedPanelClassName, 'p-4 shadow-none')}>
              <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                {t('common.totalRecords', { count: totalCount })}
              </p>
              <p className="mt-2 text-2xl font-semibold text-foreground">{totalCount}</p>
            </div>
            <div className={cn(frostedPanelClassName, 'p-4 shadow-none')}>
              <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                {t('common.pageStatus', { current: currentPage, total: totalPages })}
              </p>
              <p className="mt-2 text-2xl font-semibold text-foreground">
                {currentPage}/{totalPages}
              </p>
            </div>
            <div className={cn(frostedPanelClassName, 'p-4 shadow-none')}>
              <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                {t(
                  'audit.activeFilters',
                  { count: activeFilterCount },
                  `Фильтров: ${activeFilterCount}`,
                )}
              </p>
              <p className="mt-2 text-2xl font-semibold text-foreground">{activeFilterCount}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card
        className="rounded-[28px] border-border/70 bg-card shadow-[0_24px_80px_-52px_rgba(15,23,42,0.16)]"
        data-tour="audit-filters"
      >
        <CardHeader className="gap-4 pb-0">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-wrap items-center gap-2">
              <CardTitle className="text-lg tracking-[-0.03em]">
                {t('audit.filtersTitle', undefined, 'Фильтры')}
              </CardTitle>
              <span className={compactPillClassName}>
                {t(
                  'audit.activeFilters',
                  { count: activeFilterCount },
                  `Фильтров: ${activeFilterCount}`,
                )}
              </span>
            </div>
            <Button
              type="button"
              variant="outline"
              className="rounded-full border-border/75 bg-card px-4 shadow-[0_16px_38px_-28px_rgba(15,23,42,0.1)]"
              onClick={() => {
                setSearchParams(new URLSearchParams());
                setSelectedEntryId('');
                setIsDetailsSheetOpen(false);
              }}
              disabled={activeFilterCount === 0}
            >
              {t('common.reset')}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="grid gap-3 p-4 sm:grid-cols-2 sm:p-5 xl:grid-cols-12">
          <div className="space-y-1.5 sm:col-span-2 xl:col-span-4" data-tour="audit-search">
            <label className="block text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
              {t('audit.searchLabel', undefined, 'Поиск')}
            </label>
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={(event) => updateSearch({ search: event.target.value })}
                className={cn(inputBaseClassName, 'pl-10 pr-10')}
                placeholder={t(
                  'audit.searchPlaceholder',
                  undefined,
                  'Пользователь, таблица или действие',
                )}
              />
              {search.trim().length > 0 ? (
                <button
                  type="button"
                  className="absolute right-3 top-1/2 inline-flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground transition-colors hover:text-foreground"
                  onClick={() => updateSearch({ search: '' })}
                  aria-label={t('common.clearSelection', undefined, 'Очистить выбор')}
                >
                  <X className="h-4 w-4" />
                </button>
              ) : null}
            </div>
          </div>

          <div className="space-y-1.5 xl:col-span-2">
            <label className="block text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
              {t('audit.actionLabel', undefined, 'Действие')}
            </label>
            <CustomSelect
              value={action}
              onChange={(nextValue) => updateSearch({ action: nextValue })}
              options={auditActionOptions}
              className={inputBaseClassName}
              searchable={false}
            />
          </div>

          <div className="space-y-1.5 xl:col-span-2">
            <label className="block text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
              {t('audit.entityTableLabel', undefined, 'Таблица')}
            </label>
            <Input
              value={entityTable}
              onChange={(event) => updateSearch({ entityTable: event.target.value })}
              className={inputBaseClassName}
              placeholder={t(
                'audit.entityTablePlaceholder',
                undefined,
                'roles, employees, expenses',
              )}
            />
          </div>

          <div className="space-y-1.5 sm:col-span-2 xl:col-span-4">
            <label className="block text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
              {t('audit.entityIdLabel', undefined, 'Идентификатор записи')}
            </label>
            <Input
              value={entityId}
              onChange={(event) => updateSearch({ entityId: event.target.value })}
              className={inputBaseClassName}
              placeholder={t(
                'audit.entityIdPlaceholder',
                undefined,
                'UUID или внутренний идентификатор',
              )}
            />
          </div>

          <div className="space-y-1.5 xl:col-span-3">
            <label className="block text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
              {t('audit.changedFromLabel', undefined, 'Изменено с')}
            </label>
            <Input
              type="datetime-local"
              value={changedFrom}
              onChange={(event) => updateSearch({ changedFrom: event.target.value })}
              className={inputBaseClassName}
            />
          </div>

          <div className="space-y-1.5 xl:col-span-3">
            <label className="block text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
              {t('audit.changedToLabel', undefined, 'Изменено до')}
            </label>
            <Input
              type="datetime-local"
              value={changedTo}
              onChange={(event) => updateSearch({ changedTo: event.target.value })}
              className={inputBaseClassName}
            />
          </div>
        </CardContent>
      </Card>

      <Card className={heroCardClassName} data-tour="audit-feed">
        <CardHeader className="gap-4 border-b border-border/60 pb-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-wrap items-center gap-2">
              <CardTitle className="text-2xl tracking-[-0.04em]">
                {t('audit.feedTitle', undefined, 'Все изменения')}
              </CardTitle>
              <span className={compactPillClassName}>
                {totalCount > 0
                  ? t(
                      'audit.pageRange',
                      {
                        start: offset + 1,
                        end: Math.min(offset + auditEntries.length, totalCount),
                        total: totalCount,
                      },
                      `${offset + 1}-${Math.min(offset + auditEntries.length, totalCount)} из ${totalCount}`,
                    )
                  : t('crud.currentPageRangeEmpty')}
              </span>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4 pt-5">
          {auditQuery.error ? (
            <ErrorNotice
              error={auditQuery.error}
              className="shadow-[0_16px_42px_-30px_rgba(244,63,94,0.16)]"
            />
          ) : null}

          <div className={`${frostedPanelClassName} overflow-hidden`} data-tour="audit-main-table">
            <div className="sm:hidden">{renderAuditCards()}</div>
            <div className="hidden max-h-[680px] overflow-auto overscroll-x-contain sm:block">
              <table className="w-full min-w-[940px] border-collapse text-left text-sm">
                <thead className="sticky top-0 z-10 bg-card">
                  <tr className="border-primary/16 border-b">
                    <th className="whitespace-nowrap px-4 py-3 text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                      {t('crud.auditChangedAt')}
                    </th>
                    <th className="whitespace-nowrap px-4 py-3 text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                      {t('audit.actionLabel', undefined, 'Действие')}
                    </th>
                    <th className="whitespace-nowrap px-4 py-3 text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                      {t('common.record', undefined, 'Запись')}
                    </th>
                    <th className="whitespace-nowrap px-4 py-3 text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                      {t('crud.auditChangedBy')}
                    </th>
                    <th className="w-[320px] whitespace-nowrap px-4 py-3 text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                      {t('crud.auditChangedFields')}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {auditEntries.map((entry, index) => {
                    const changedFields = getChangedFieldNames(entry);
                    const changedFieldsPreview = changedFields.slice(0, changedFieldsPreviewLimit);
                    const hiddenChangedFieldsCount = Math.max(
                      0,
                      changedFields.length - changedFieldsPreview.length,
                    );
                    const isActive = selectedEntryId === entry.id;

                    return (
                      <tr
                        key={entry.id}
                        onClick={() => openEntryDetails(entry)}
                        data-tour="audit-open-details"
                        className={cn(
                          'cursor-pointer border-b border-border/50 transition-colors last:border-b-0',
                          isActive
                            ? 'bg-primary/5 shadow-[inset_4px_0_0_hsl(var(--primary))]'
                            : index % 2 === 0
                              ? 'bg-card hover:bg-muted/25'
                              : 'bg-muted/10 hover:bg-muted/25',
                        )}
                      >
                        <td className="px-4 py-3.5 align-top">
                          <p className="min-w-[168px] text-sm font-medium text-foreground">
                            {formatEntryTimestamp(entry.changed_at)}
                          </p>
                        </td>
                        <td className="px-4 py-3.5 align-top">
                          <span
                            className={cn(
                              'inline-flex rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em]',
                              getEntryActionBadgeClassName(entry.action),
                            )}
                          >
                            {getEntryActionLabel(entry.action)}
                          </span>
                        </td>
                        <td className="px-4 py-3.5 align-top">
                          <div className="min-w-[220px] max-w-[320px]">
                            <p className="text-sm font-medium text-foreground">
                              {humanizeKey(entry.entity_table)}
                            </p>
                            <p
                              className="mt-1 truncate text-xs text-muted-foreground"
                              title={entry.entity_id}
                            >
                              {entry.entity_id}
                            </p>
                          </div>
                        </td>
                        <td className="px-4 py-3.5 align-top">
                          <p className="max-w-[220px] truncate text-sm text-foreground">
                            {entry.actor_username || emptyLabel}
                          </p>
                        </td>
                        <td className="w-[320px] px-4 py-3.5 align-top">
                          <div className="flex max-w-[320px] flex-wrap gap-2">
                            {changedFieldsPreview.length > 0 ? (
                              <>
                                {changedFieldsPreview.map((fieldName) => (
                                  <span
                                    key={fieldName}
                                    className={cn(
                                      compactPillClassName,
                                      'max-w-[160px] truncate px-2.5 py-1 shadow-none',
                                    )}
                                    title={humanizeKey(fieldName)}
                                  >
                                    {humanizeKey(fieldName)}
                                  </span>
                                ))}
                                {hiddenChangedFieldsCount > 0 ? (
                                  <span
                                    key={`${entry.id}-hidden-fields`}
                                    className={cn(compactPillClassName, 'px-2.5 py-1 shadow-none')}
                                    title={t(
                                      'audit.hiddenFieldsCount',
                                      { count: hiddenChangedFieldsCount },
                                      `Скрыто полей: ${hiddenChangedFieldsCount}`,
                                    )}
                                  >
                                    +{hiddenChangedFieldsCount}
                                  </span>
                                ) : null}
                              </>
                            ) : (
                              <span className={cn(compactPillClassName, 'px-2.5 py-1 shadow-none')}>
                                {emptyLabel}
                              </span>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}

                  {auditQuery.isLoading ? (
                    <tr>
                      <td colSpan={5} className="px-5 py-14 text-center text-muted-foreground">
                        {t('common.loadingLabel')}
                      </td>
                    </tr>
                  ) : null}

                  {!auditQuery.isLoading && totalCount === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-5 py-14 text-center text-muted-foreground">
                        {t('audit.empty', undefined, 'По текущим фильтрам изменений не найдено.')}
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </div>

          <div
            className="flex flex-col gap-3 pt-1 sm:flex-row sm:items-center sm:justify-between"
            data-tour="audit-pagination"
          >
            <p className="text-sm text-muted-foreground">
              {totalCount > 0
                ? t(
                    'audit.pageRange',
                    {
                      start: offset + 1,
                      end: Math.min(offset + auditEntries.length, totalCount),
                      total: totalCount,
                    },
                    `${offset + 1}-${Math.min(offset + auditEntries.length, totalCount)} из ${totalCount}`,
                  )
                : t('crud.currentPageRangeEmpty')}
            </p>
            <Pagination className="mx-0 w-full justify-start sm:w-auto sm:justify-end">
              <PaginationContent>
                <PaginationItem>
                  <PaginationPrevious
                    href="#"
                    text={t('common.previous')}
                    className={cn(currentPage === 1 && 'pointer-events-none opacity-50')}
                    onClick={(event) => {
                      event.preventDefault();
                      if (currentPage > 1) {
                        updateSearch({ page: String(currentPage - 1) });
                      }
                    }}
                  />
                </PaginationItem>
                {paginationItems.map((item, index) => (
                  <PaginationItem key={`${item}-${index}`}>
                    {typeof item === 'number' ? (
                      <PaginationLink
                        href="#"
                        isActive={item === currentPage}
                        onClick={(event) => {
                          event.preventDefault();
                          updateSearch({ page: String(item) });
                        }}
                      >
                        {item}
                      </PaginationLink>
                    ) : (
                      <PaginationEllipsis />
                    )}
                  </PaginationItem>
                ))}
                <PaginationItem>
                  <PaginationNext
                    href="#"
                    text={t('common.next')}
                    className={cn(currentPage === totalPages && 'pointer-events-none opacity-50')}
                    onClick={(event) => {
                      event.preventDefault();
                      if (currentPage < totalPages) {
                        updateSearch({ page: String(currentPage + 1) });
                      }
                    }}
                  />
                </PaginationItem>
              </PaginationContent>
            </Pagination>
          </div>
        </CardContent>
      </Card>

      <Sheet
        open={isDetailsSheetOpen}
        onOpenChange={(open) => {
          setIsDetailsSheetOpen(open);
          if (!open) {
            setSelectedEntryId('');
          }
        }}
      >
        <CrudDrawer
          dataTour="audit-details-drawer"
          size="audit-wide"
          title={t('crud.auditTitle')}
          footer={
            <CrudDrawerFooter
              closeLabel={t('common.close')}
              onClose={() => {
                setIsDetailsSheetOpen(false);
                setSelectedEntryId('');
              }}
            />
          }
        >
          {selectedEntry ? (
            <>
              <article className="space-y-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={cn(
                      'rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em]',
                      getEntryActionBadgeClassName(selectedEntry.action),
                    )}
                  >
                    {getEntryActionLabel(selectedEntry.action)}
                  </span>
                  <span className={compactPillClassName}>
                    {`${t('crud.auditChangedBy')}: ${selectedEntry.actor_username || emptyLabel}`}
                  </span>
                  <span className={compactPillClassName}>
                    {`${t('crud.auditChangedAt')}: ${formatEntryTimestamp(selectedEntry.changed_at)}`}
                  </span>
                </div>

                <div className="grid gap-3 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
                  <div className={cn(frostedPanelClassName, 'space-y-3 p-4 shadow-none')}>
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                        {t('audit.entityTableLabel', undefined, 'Таблица')}
                      </p>
                      <p className="mt-1 text-sm text-foreground">
                        {humanizeKey(selectedEntry.entity_table)}
                      </p>
                    </div>
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                        {t('audit.entityIdLabel', undefined, 'Идентификатор записи')}
                      </p>
                      <p className="mt-1 break-all text-sm text-foreground">
                        {selectedEntry.entity_id}
                      </p>
                    </div>
                  </div>
                  <div className={cn(frostedPanelClassName, 'space-y-3 p-4 shadow-none')}>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                      {t('crud.auditChangedFields')}
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {selectedChangedFields.length > 0 ? (
                        selectedChangedFields.map((fieldName) => (
                          <span key={fieldName} className={cn(compactPillClassName, 'shadow-none')}>
                            {humanizeKey(fieldName)}
                          </span>
                        ))
                      ) : (
                        <span className={cn(compactPillClassName, 'shadow-none')}>
                          {emptyLabel}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </article>

              <div className="grid gap-4 xl:grid-cols-2" data-tour="audit-details-snapshots">
                <div className="space-y-2">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                    {t('crud.auditBefore')}
                  </p>
                  {renderSnapshot(selectedEntry.before_data, selectedChangedFields)}
                </div>
                <div className="space-y-2">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                    {t('crud.auditAfter')}
                  </p>
                  {renderSnapshot(selectedEntry.after_data, selectedChangedFields)}
                </div>
              </div>
            </>
          ) : (
            <div className={`${frostedPanelClassName} px-4 py-8 text-sm text-muted-foreground`}>
              {t('audit.emptySelection', undefined, 'Выберите изменение из списка.')}
            </div>
          )}
        </CrudDrawer>
      </Sheet>
    </div>
  );
}
