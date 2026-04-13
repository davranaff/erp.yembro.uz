import { Check, ChevronDown } from 'lucide-react';
import { useDeferredValue, useEffect, useMemo, useState } from 'react';

import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from '@/components/ui/command';
import { useI18n } from '@/shared/i18n';
import { cn } from '@/shared/lib/cn';

import { Popover, PopoverContent, PopoverTrigger } from './popover';

export type CustomSelectOption = {
  value: string;
  label: string;
  searchText?: string;
  disabled?: boolean;
};

type CustomSelectProps = {
  value: string;
  options: CustomSelectOption[];
  onChange: (value: string) => void;
  disabled?: boolean;
  className?: string;
  contentClassName?: string;
  placeholder?: string;
  searchPlaceholder?: string;
  emptySearchLabel?: string;
  searchable?: boolean;
};

const triggerBaseClassName =
  'flex min-h-11 w-full items-center justify-between gap-3 rounded-2xl border border-border/75 bg-card px-4 py-3 text-left text-sm text-foreground shadow-[0_16px_38px_-30px_rgba(15,23,42,0.12)] transition-colors hover:bg-background disabled:cursor-not-allowed disabled:opacity-50';

export function CustomSelect({
  value,
  options,
  onChange,
  disabled = false,
  className,
  contentClassName,
  placeholder,
  searchPlaceholder,
  emptySearchLabel,
  searchable = true,
}: CustomSelectProps) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const deferredSearch = useDeferredValue(search.trim().toLowerCase());

  const resolvedPlaceholder = placeholder ?? t('common.chooseValue');
  const resolvedSearchPlaceholder = searchPlaceholder ?? t('common.search', undefined, 'Поиск');
  const resolvedEmptySearchLabel =
    emptySearchLabel ?? t('common.noResults', undefined, 'Ничего не найдено');

  useEffect(() => {
    if (!open) {
      setSearch('');
    }
  }, [open]);

  const selectedOption = useMemo(
    () => options.find((option) => option.value === value) ?? null,
    [options, value],
  );

  const filteredOptions = useMemo(() => {
    if (!searchable || !deferredSearch) {
      return options;
    }

    return options.filter((option) => {
      const haystack = [option.label, option.searchText]
        .filter((part): part is string => typeof part === 'string' && part.trim().length > 0)
        .join(' ')
        .toLowerCase();

      return haystack.includes(deferredSearch);
    });
  }, [deferredSearch, options, searchable]);

  const triggerLabel = selectedOption?.label ?? resolvedPlaceholder;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger className={cn(triggerBaseClassName, className)} disabled={disabled}>
        <span
          className={cn(
            'min-w-0 flex-1 truncate whitespace-pre-wrap',
            selectedOption === null && 'text-muted-foreground',
          )}
        >
          {triggerLabel}
        </span>
        <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
      </PopoverTrigger>

      <PopoverContent
        align="start"
        sideOffset={10}
        className={cn(
          'bg-background/98 w-[min(36rem,calc(100vw-2rem))] rounded-[24px] border border-border/80 p-3',
          contentClassName,
        )}
      >
        <Command shouldFilter={false} className="space-y-3">
          {searchable ? (
            <CommandInput
              value={search}
              onValueChange={setSearch}
              placeholder={resolvedSearchPlaceholder}
            />
          ) : null}

          {searchable ? <CommandSeparator /> : null}

          <CommandList className="max-h-72 space-y-1 pr-1">
            {filteredOptions.length === 0 ? (
              <CommandEmpty>{resolvedEmptySearchLabel}</CommandEmpty>
            ) : (
              <CommandGroup className="space-y-1 p-0">
                {filteredOptions.map((option) => {
                  const isSelected = option.value === value;

                  return (
                    <CommandItem
                      key={`${option.value}::${option.label}`}
                      value={option.value}
                      disabled={option.disabled}
                      className={cn(
                        'cursor-pointer',
                        isSelected && 'bg-primary/8 border-primary/30',
                      )}
                      onSelect={() => {
                        if (option.disabled) {
                          return;
                        }

                        onChange(option.value);
                        setOpen(false);
                      }}
                    >
                      <span
                        className={cn(
                          'flex h-5 w-5 shrink-0 items-center justify-center rounded-md border border-border/70 bg-background text-transparent',
                          isSelected && 'border-primary/40 bg-primary text-primary-foreground',
                        )}
                      >
                        <Check className="h-3.5 w-3.5" />
                      </span>
                      <span className="min-w-0 flex-1 whitespace-pre-wrap break-words text-foreground">
                        {option.label}
                      </span>
                    </CommandItem>
                  );
                })}
              </CommandGroup>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
