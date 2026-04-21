'use client';

import { Check, ChevronDown, LoaderCircle } from 'lucide-react';
import { useCallback, useMemo, useState } from 'react';

import { listCrudRecords, type CrudRecord } from '@/shared/api/backend-crud';
import { toQueryKey } from '@/shared/api/query-keys';
import { useApiQuery } from '@/shared/api/react-query';
import { useI18n } from '@/shared/i18n';
import { cn } from '@/shared/lib/cn';

import { Button } from './button';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from './command';
import { ErrorNotice } from './error-notice';
import { Popover, PopoverContent, PopoverTrigger } from './popover';

interface MeasurementUnitSelectProps {
  /** Either a unit code (e.g. "kg") or a measurement_unit_id. Writes the code. */
  value: string;
  onChange: (nextCode: string) => void;
  disabled?: boolean;
  className?: string;
  placeholder?: string;
}

export function MeasurementUnitSelect({
  value,
  onChange,
  disabled,
  className,
  placeholder,
}: MeasurementUnitSelectProps) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');

  const query = useApiQuery({
    queryKey: toQueryKey('crud', 'measurement-units-options'),
    queryFn: () => listCrudRecords('core', 'measurement-units', { limit: 200, offset: 0 }),
    enabled: open,
    staleTime: 300_000,
  });

  const units = useMemo(() => {
    const items = query.data?.items ?? [];
    return items
      .filter((row: CrudRecord) => row.is_active !== false)
      .map((row: CrudRecord) => ({
        id: String(row.id ?? ''),
        code: String(row.code ?? '').trim(),
        name: String(row.name ?? '').trim(),
        sortOrder: Number(row.sort_order ?? 100),
      }))
      .filter((unit) => unit.code.length > 0)
      .sort((a, b) => a.sortOrder - b.sortOrder || a.code.localeCompare(b.code));
  }, [query.data]);

  const normalizedValue = typeof value === 'string' ? value.trim() : '';
  const currentLabel = useMemo(() => {
    if (!normalizedValue) {
      return placeholder ?? t('common.chooseValue');
    }
    const byCode = units.find((unit) => unit.code.toLowerCase() === normalizedValue.toLowerCase());
    if (byCode) {
      return `${byCode.code} — ${byCode.name}`;
    }
    return normalizedValue;
  }, [normalizedValue, units, placeholder, t]);

  const filteredUnits = useMemo(() => {
    const s = search.trim().toLowerCase();
    if (!s) {
      return units;
    }
    return units.filter(
      (unit) => unit.code.toLowerCase().includes(s) || unit.name.toLowerCase().includes(s),
    );
  }, [units, search]);

  const handlePick = useCallback(
    (code: string) => {
      onChange(code);
      setOpen(false);
      setSearch('');
    },
    [onChange],
  );

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          disabled={disabled}
          className={cn(
            'w-full justify-between border-border/75 bg-card text-left font-normal',
            !normalizedValue && 'text-muted-foreground',
            className,
          )}
        >
          <span className="truncate">{currentLabel}</span>
          <ChevronDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[min(320px,92vw)] p-0" align="start">
        <Command shouldFilter={false}>
          <CommandInput
            placeholder={t('common.search', undefined, 'Поиск')}
            value={search}
            onValueChange={setSearch}
          />
          <CommandList>
            {query.isLoading ? (
              <div className="flex items-center justify-center gap-2 px-3 py-6 text-sm text-muted-foreground">
                <LoaderCircle className="h-4 w-4 animate-spin" />
                {t('common.loading', undefined, 'Загрузка...')}
              </div>
            ) : query.error ? (
              <div className="px-3 py-4">
                <ErrorNotice error={query.error} />
              </div>
            ) : filteredUnits.length === 0 ? (
              <CommandEmpty>
                {t('crud.referenceNoOptions', undefined, 'Подходящие варианты не найдены.')}
              </CommandEmpty>
            ) : (
              <CommandGroup>
                {filteredUnits.map((unit) => (
                  <CommandItem
                    key={unit.id}
                    value={`${unit.code} ${unit.name}`}
                    onSelect={() => handlePick(unit.code)}
                  >
                    <span className="font-medium text-foreground">{unit.code}</span>
                    <span className="ml-2 truncate text-muted-foreground">{unit.name}</span>
                    {unit.code.toLowerCase() === normalizedValue.toLowerCase() ? (
                      <Check className="ml-auto h-4 w-4 text-primary" />
                    ) : null}
                  </CommandItem>
                ))}
              </CommandGroup>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
