'use client';

import { Check, ChevronDown, LoaderCircle } from 'lucide-react';
import { useCallback, useDeferredValue, useEffect, useMemo, useState } from 'react';

import { cn } from '@/lib/utils';
import {
  getCrudReferenceOptions,
  type CrudFieldMeta,
  type CrudReferenceOption,
} from '@/shared/api/backend-crud';
import { toQueryKey } from '@/shared/api/query-keys';
import { useApiQuery } from '@/shared/api/react-query';
import { useI18n } from '@/shared/i18n';
import { getReadableReferenceLabel } from '@/shared/lib/reference-label';

import { Badge } from './badge';
import { Button } from './button';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from './command';
import { ErrorNotice } from './error-notice';
import { Popover, PopoverContent, PopoverTrigger } from './popover';

type SearchableReferenceSelectProps = {
  moduleKey: string;
  resourcePath: string;
  field: CrudFieldMeta;
  value: string | string[];
  onChange: (value: string | string[]) => void;
  disabled?: boolean;
  className?: string;
  placeholder?: string;
  emptySearchLabel?: string;
  searchPlaceholder?: string;
  translateOptionLabel?: (field: CrudFieldMeta, optionValue: string, optionLabel: string) => string;
  useLocalOptionsOnly?: boolean;
  referenceQueryParams?: Record<string, string | undefined>;
};

const normalizeValues = (value: string | string[]): string[] => {
  if (Array.isArray(value)) {
    return value.map((item) => item.trim()).filter((item) => item.length > 0);
  }

  return typeof value === 'string' && value.trim() ? [value.trim()] : [];
};

const mergeOptions = (
  baseOptions: CrudReferenceOption[],
  extraOptions: CrudReferenceOption[],
): CrudReferenceOption[] => {
  const optionMap = new Map<string, CrudReferenceOption>();

  [...baseOptions, ...extraOptions].forEach((option) => {
    const normalizedValue = option.value.trim();
    if (!normalizedValue) {
      return;
    }

    if (!optionMap.has(normalizedValue)) {
      optionMap.set(normalizedValue, {
        ...option,
        value: normalizedValue,
      });
    }
  });

  return [...optionMap.values()];
};

const filterOptions = (options: CrudReferenceOption[], search: string): CrudReferenceOption[] => {
  const normalizedSearch = search.trim().toLowerCase();
  if (!normalizedSearch) {
    return options;
  }

  return options.filter((option) =>
    `${option.label} ${option.value}`.toLowerCase().includes(normalizedSearch),
  );
};

export function SearchableReferenceSelect({
  moduleKey,
  resourcePath,
  field,
  value,
  onChange,
  disabled = false,
  className,
  placeholder,
  emptySearchLabel,
  searchPlaceholder,
  translateOptionLabel,
  useLocalOptionsOnly = false,
  referenceQueryParams,
}: SearchableReferenceSelectProps) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const deferredSearch = useDeferredValue(search);
  const normalizedDeferredSearch = deferredSearch.trim().toLowerCase();
  const selectedValues = useMemo(() => {
    const normalizedValues = normalizeValues(value);
    if (field.type !== 'uuid') {
      return normalizedValues;
    }

    return normalizedValues.filter((item) => {
      if (item) {
        return true;
      }

      return false;
    });
  }, [field.type, value]);
  const isMultiple = Boolean(field.reference?.multiple);

  const resolvedPlaceholder = placeholder ?? t('common.chooseValue');
  const resolvedSearchPlaceholder = searchPlaceholder ?? t('common.search', undefined, 'Поиск');
  const resolvedEmptySearchLabel =
    emptySearchLabel ?? t('common.noResults', undefined, 'Ничего не найдено');
  const localOptions = useMemo(() => field.reference?.options ?? [], [field.reference?.options]);
  const localFilteredOptions = useMemo(
    () => filterOptions(localOptions, normalizedDeferredSearch),
    [localOptions, normalizedDeferredSearch],
  );

  const referenceQuery = useApiQuery({
    queryKey: toQueryKey(
      'crud',
      'reference-options',
      moduleKey,
      resourcePath,
      field.name,
      normalizedDeferredSearch,
      selectedValues.join(','),
      JSON.stringify(referenceQueryParams ?? {}),
    ),
    queryFn: () =>
      getCrudReferenceOptions(moduleKey, resourcePath, field.name, {
        search: normalizedDeferredSearch,
        values: selectedValues,
        limit: isMultiple ? 40 : 24,
        extraParams: referenceQueryParams,
      }),
    enabled:
      Boolean(field.reference) &&
      !useLocalOptionsOnly &&
      (selectedValues.length > 0 ||
        (open && (normalizedDeferredSearch.length > 0 || localOptions.length === 0))),
  });

  useEffect(() => {
    if (!open) {
      setSearch('');
    }
  }, [open]);

  const options = useMemo(
    () => mergeOptions(localOptions, referenceQuery.data?.options ?? []),
    [localOptions, referenceQuery.data?.options],
  );
  const visibleOptions = useMemo(() => {
    if (!useLocalOptionsOnly) {
      return normalizedDeferredSearch
        ? mergeOptions(localFilteredOptions, referenceQuery.data?.options ?? [])
        : options;
    }

    return localFilteredOptions;
  }, [
    localFilteredOptions,
    normalizedDeferredSearch,
    options,
    referenceQuery.data?.options,
    useLocalOptionsOnly,
  ]);

  const selectedOptions = useMemo(() => {
    return selectedValues.map((selectedValue) => {
      const matchedOption = options.find((option) => option.value === selectedValue);
      return matchedOption ?? { value: selectedValue, label: selectedValue };
    });
  }, [options, selectedValues]);

  const formatLabel = useCallback(
    (option: CrudReferenceOption): string => {
      const readableLabel = getReadableReferenceLabel({
        fieldName: field.name,
        fieldLabel: field.label,
        optionValue: option.value,
        optionLabel: option.label,
      });

      return translateOptionLabel
        ? translateOptionLabel(field, option.value, readableLabel)
        : readableLabel;
    },
    [field, translateOptionLabel],
  );

  const triggerLabel = useMemo(() => {
    if (selectedOptions.length === 0) {
      return resolvedPlaceholder;
    }

    if (!isMultiple) {
      return formatLabel(selectedOptions[0]);
    }

    if (selectedOptions.length <= 2) {
      return selectedOptions.map((option) => formatLabel(option)).join(', ');
    }

    return t(
      'common.selectedCount',
      { count: selectedOptions.length },
      `${selectedOptions.length} выбрано`,
    );
  }, [formatLabel, isMultiple, resolvedPlaceholder, selectedOptions, t]);

  const handleSelect = (optionValue: string) => {
    if (isMultiple) {
      const nextValues = selectedValues.includes(optionValue)
        ? selectedValues.filter((valueItem) => valueItem !== optionValue)
        : [...selectedValues, optionValue];
      onChange(nextValues);
      return;
    }

    onChange(optionValue);
    setOpen(false);
  };

  const handleClear = () => {
    onChange(isMultiple ? [] : '');
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        className={cn(
          'flex min-h-11 w-full items-center justify-between gap-3 rounded-2xl border border-border/75 bg-card px-4 py-3 text-left text-sm text-foreground shadow-[0_16px_38px_-30px_rgba(15,23,42,0.12)] transition-colors hover:bg-background disabled:cursor-not-allowed disabled:opacity-50',
          className,
        )}
        disabled={disabled}
      >
        <span
          className={cn(
            'min-w-0 flex-1 truncate',
            selectedOptions.length === 0 && 'text-muted-foreground',
          )}
        >
          {triggerLabel}
        </span>
        <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
      </PopoverTrigger>

      <PopoverContent
        align="start"
        sideOffset={10}
        className="bg-background/98 w-[min(36rem,calc(100vw-2rem))] rounded-[24px] border border-border/80 p-3"
      >
        <Command shouldFilter={false} className="space-y-3">
          <CommandInput
            value={search}
            onValueChange={setSearch}
            placeholder={resolvedSearchPlaceholder}
          />

          {selectedOptions.length > 0 && isMultiple ? (
            <div className="flex flex-wrap gap-2">
              {selectedOptions.map((option) => (
                <Badge
                  key={option.value}
                  variant="outline"
                  className="gap-1 normal-case tracking-normal"
                >
                  {formatLabel(option)}
                </Badge>
              ))}
            </div>
          ) : null}

          <CommandSeparator />

          <CommandList className="max-h-72 space-y-1 pr-1">
            {referenceQuery.isLoading ? (
              <div className="flex items-center gap-2 rounded-2xl border border-border/70 bg-card px-3 py-3 text-sm text-muted-foreground">
                <LoaderCircle className="h-4 w-4 animate-spin" />
                {t('common.loadingOptions', undefined, 'Загрузка вариантов')}
              </div>
            ) : referenceQuery.isError ? (
              <ErrorNotice error={referenceQuery.error} className="rounded-2xl px-3 py-3" />
            ) : visibleOptions.length === 0 ? (
              <CommandEmpty>{resolvedEmptySearchLabel}</CommandEmpty>
            ) : (
              <CommandGroup className="space-y-1 p-0">
                {visibleOptions.map((option) => {
                  const isSelected = selectedValues.includes(option.value);

                  return (
                    <CommandItem
                      key={option.value}
                      value={option.value}
                      className={cn(
                        'cursor-pointer',
                        isSelected && 'bg-primary/8 border-primary/30',
                      )}
                      onSelect={() => handleSelect(option.value)}
                    >
                      <span
                        className={cn(
                          'flex h-5 w-5 shrink-0 items-center justify-center rounded-md border border-border/70 bg-background text-transparent',
                          isSelected && 'border-primary/40 bg-primary text-primary-foreground',
                        )}
                      >
                        <Check className="h-3.5 w-3.5" />
                      </span>
                      <span className="min-w-0 flex-1 break-words text-foreground">
                        {formatLabel(option)}
                      </span>
                    </CommandItem>
                  );
                })}
              </CommandGroup>
            )}
          </CommandList>

          {selectedOptions.length > 0 ? (
            <Button
              type="button"
              variant="outline"
              className="w-full rounded-2xl"
              onClick={handleClear}
            >
              {isMultiple
                ? t('common.clearAll', undefined, 'Очистить все')
                : t('common.clearSelection', undefined, 'Очистить выбор')}
            </Button>
          ) : null}
        </Command>
      </PopoverContent>
    </Popover>
  );
}
