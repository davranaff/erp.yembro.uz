import { useMemo } from 'react';

import type { CrudAuditEntry, CrudFieldMeta } from '@/shared/api/backend-crud';

import {
  formatDateTimeDisplayValue,
  formatDateValue,
  getDisplayValue,
  humanizeKey,
  isAuditSnapshot,
  isPasswordFieldName,
} from '../module-crud-page.helpers';

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

export interface AuditFormatters {
  getAuditActionLabel: (action: CrudAuditEntry['action']) => string;
  getAuditActionBadgeClassName: (action: CrudAuditEntry['action']) => string;
  formatAuditTimestamp: (value: string) => string;
  getAuditFieldLabel: (fieldName: string) => string;
  formatFallbackAuditValue: (value: unknown) => string;
  getAuditFieldDisplayValue: (fieldName: string, value: unknown) => string;
  getAuditFieldNames: (entry: CrudAuditEntry) => string[];
}

export interface UseAuditFormattersOptions {
  locale: string;
  t: TranslateFn;
  fieldMetaByName: Map<string, CrudFieldMeta>;
  emptyLabel: string;
  yesLabel: string;
  noLabel: string;
  translateReferenceLabel: ReferenceLabelTranslator;
}

export function useAuditFormatters({
  locale,
  t,
  fieldMetaByName,
  emptyLabel,
  yesLabel,
  noLabel,
  translateReferenceLabel,
}: UseAuditFormattersOptions): AuditFormatters {
  const auditDateTimeFormatter = useMemo(
    () =>
      new Intl.DateTimeFormat(locale, {
        dateStyle: 'medium',
        timeStyle: 'short',
      }),
    [locale],
  );

  return useMemo(() => {
    const getAuditActionLabel = (action: CrudAuditEntry['action']): string => {
      switch (action) {
        case 'create':
          return t('crud.auditActionCreate');
        case 'delete':
          return t('crud.auditActionDelete');
        case 'update':
        default:
          return t('crud.auditActionUpdate');
      }
    };

    const getAuditActionBadgeClassName = (action: CrudAuditEntry['action']): string => {
      switch (action) {
        case 'create':
          return 'border-emerald-200 bg-emerald-50 text-emerald-700';
        case 'delete':
          return 'border-destructive/20 bg-destructive/10 text-destructive';
        case 'update':
        default:
          return 'border-primary/20 bg-primary/10 text-primary';
      }
    };

    const formatAuditTimestamp = (value: string): string => {
      const changedAt = new Date(value);
      if (Number.isNaN(changedAt.getTime())) {
        return value;
      }
      return auditDateTimeFormatter.format(changedAt);
    };

    const getAuditFieldLabel = (fieldName: string): string => {
      const field = fieldMetaByName.get(fieldName);
      return t(`fields.${fieldName}`, undefined, field?.label || humanizeKey(fieldName));
    };

    const formatFallbackAuditValue = (value: unknown): string => {
      if (value === null || value === undefined || value === '') {
        return emptyLabel;
      }

      if (typeof value === 'boolean') {
        return value ? yesLabel : noLabel;
      }

      if (typeof value === 'string') {
        if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
          return formatDateValue(value);
        }
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
        return value.map((item) => formatFallbackAuditValue(item)).join(', ');
      }

      return JSON.stringify(value, null, 2);
    };

    const getAuditFieldDisplayValue = (fieldName: string, value: unknown): string => {
      if (isPasswordFieldName(fieldName)) {
        return emptyLabel;
      }

      if (Array.isArray(value) || isAuditSnapshot(value)) {
        return formatFallbackAuditValue(value);
      }

      const field = fieldMetaByName.get(fieldName);
      if (field) {
        return getDisplayValue(
          field,
          value,
          yesLabel,
          noLabel,
          emptyLabel,
          translateReferenceLabel,
        );
      }

      return formatFallbackAuditValue(value);
    };

    const getAuditFieldNames = (entry: CrudAuditEntry): string[] => {
      const explicitFieldNames = (entry.changed_fields ?? [])
        .map((fieldName) => String(fieldName).trim())
        .filter((fieldName) => fieldName.length > 0 && !isPasswordFieldName(fieldName));
      if (explicitFieldNames.length > 0) {
        return explicitFieldNames;
      }

      const fieldNames = new Set<string>();
      if (isAuditSnapshot(entry.before_data)) {
        Object.keys(entry.before_data).forEach((fieldName) => {
          if (!isPasswordFieldName(fieldName)) {
            fieldNames.add(fieldName);
          }
        });
      }
      if (isAuditSnapshot(entry.after_data)) {
        Object.keys(entry.after_data).forEach((fieldName) => {
          if (!isPasswordFieldName(fieldName)) {
            fieldNames.add(fieldName);
          }
        });
      }

      return Array.from(fieldNames).sort();
    };

    return {
      getAuditActionLabel,
      getAuditActionBadgeClassName,
      formatAuditTimestamp,
      getAuditFieldLabel,
      formatFallbackAuditValue,
      getAuditFieldDisplayValue,
      getAuditFieldNames,
    };
  }, [
    auditDateTimeFormatter,
    emptyLabel,
    fieldMetaByName,
    noLabel,
    t,
    translateReferenceLabel,
    yesLabel,
  ]);
}
