import { differenceInCalendarDays, format, type Locale } from 'date-fns';
import { enUS, ru, uz } from 'date-fns/locale';
import { CalendarDays, RotateCcw } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { Button, buttonVariants } from '@/components/ui/button';
import { Calendar } from '@/components/ui/calendar';
import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from '@/components/ui/popover';
import { useI18n } from '@/shared/i18n';
import { cn } from '@/shared/lib/cn';

import type { DateRange } from 'react-day-picker';

type AnalyticsDateFilterProps = {
  startDate?: string;
  endDate?: string;
  onApply: (range: { startDate?: string; endDate?: string }) => void;
  resetRange?: {
    startDate?: string;
    endDate?: string;
  };
  triggerClassName?: string;
};

const toDate = (value?: string): Date | undefined =>
  value ? new Date(`${value}T00:00:00`) : undefined;

const toRange = (startDate?: string, endDate?: string): DateRange | undefined => {
  const from = toDate(startDate);
  const to = toDate(endDate);

  if (!from && !to) {
    return undefined;
  }

  return {
    from: from ?? to,
    to: to ?? from,
  };
};

const toIsoDate = (value?: Date): string | undefined => {
  if (!value) {
    return undefined;
  }

  return format(value, 'yyyy-MM-dd');
};

export const normalizeAnalyticsDateRange = (range?: DateRange): DateRange | undefined => {
  const from = range?.from;
  const to = range?.to ?? range?.from;

  if (!from && !to) {
    return undefined;
  }

  if (!from || !to) {
    const singleDate = from ?? to;
    return singleDate
      ? {
          from: singleDate,
          to: singleDate,
        }
      : undefined;
  }

  if (from <= to) {
    return { from, to };
  }

  return {
    from: to,
    to: from,
  };
};

export const buildAnalyticsDateFilterValue = (range?: DateRange) => {
  const normalizedRange = normalizeAnalyticsDateRange(range);

  return {
    startDate: toIsoDate(normalizedRange?.from),
    endDate: toIsoDate(normalizedRange?.to),
  };
};

export function AnalyticsDateFilter({
  startDate,
  endDate,
  onApply,
  resetRange,
  triggerClassName,
}: AnalyticsDateFilterProps) {
  const { language, t } = useI18n();
  const [open, setOpen] = useState(false);
  const initialRange = useMemo(() => toRange(startDate, endDate), [endDate, startDate]);
  const [draftRange, setDraftRange] = useState<DateRange | undefined>(initialRange);
  const normalizedResetRange = useMemo(
    () => toRange(resetRange?.startDate, resetRange?.endDate),
    [resetRange?.endDate, resetRange?.startDate],
  );
  const dayPickerLocale: Locale = useMemo(() => {
    if (language === 'en') {
      return enUS;
    }
    if (language === 'uz') {
      return uz;
    }
    return ru;
  }, [language]);

  useEffect(() => {
    setDraftRange(initialRange);
  }, [initialRange]);

  const label = useMemo(() => {
    if (startDate && endDate) {
      return `${format(new Date(`${startDate}T00:00:00`), 'dd.MM.yyyy')} - ${format(new Date(`${endDate}T00:00:00`), 'dd.MM.yyyy')}`;
    }

    if (startDate) {
      return format(new Date(`${startDate}T00:00:00`), 'dd.MM.yyyy');
    }

    if (endDate) {
      return format(new Date(`${endDate}T00:00:00`), 'dd.MM.yyyy');
    }

    return t('dashboard.dateRangePlaceholder');
  }, [endDate, startDate, t]);

  const rangeSummary = useMemo(() => {
    const from = draftRange?.from;
    const to = draftRange?.to;

    if (!from && !to) {
      return {
        title: t('dashboard.rangeSelectedCaption'),
        description: t('dashboard.rangeNoDateRestriction'),
      };
    }

    if (from && to) {
      const daysCount = differenceInCalendarDays(to, from) + 1;

      return {
        title:
          from.getTime() === to.getTime()
            ? format(from, 'dd.MM.yyyy')
            : `${format(from, 'dd.MM.yyyy')} - ${format(to, 'dd.MM.yyyy')}`,
        description: `${daysCount} ${t('dashboard.rangeDayUnit')}`,
      };
    }

    return {
      title: format(from ?? to!, 'dd.MM.yyyy'),
      description: t('dashboard.rangeSingleDay'),
    };
  }, [draftRange, t]);

  const handleReset = () => {
    setDraftRange(normalizedResetRange);
    onApply(buildAnalyticsDateFilterValue(normalizedResetRange));
    setOpen(false);
  };

  const handleApply = () => {
    onApply(buildAnalyticsDateFilterValue(draftRange));
    setOpen(false);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        className={cn(buttonVariants({ variant: 'outline' }), 'rounded-full', triggerClassName)}
      >
        <CalendarDays className="h-4 w-4" />
        {label}
      </PopoverTrigger>
      <PopoverContent
        align="end"
        className="w-[min(360px,calc(100vw-1rem))] max-w-[calc(100vw-1rem)] rounded-[28px] border border-border/75 bg-background p-0 shadow-[0_24px_80px_-40px_rgba(15,23,42,0.18)] backdrop-blur-none"
      >
        <PopoverHeader className="border-b border-border/70 px-5 py-4">
          <PopoverTitle>{t('dashboard.dateRangeTitle')}</PopoverTitle>
          <PopoverDescription>{t('dashboard.dateRangeDescription')}</PopoverDescription>
        </PopoverHeader>
        <div className="space-y-4 p-4">
          <div className="rounded-3xl border border-border/75 bg-background px-4 py-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
              {t('dashboard.dateRangeTitle')}
            </p>
            <p className="mt-2 text-sm font-semibold text-foreground">{rangeSummary.title}</p>
            <p className="mt-1 text-xs text-muted-foreground">{rangeSummary.description}</p>
          </div>
          <Calendar
            mode="range"
            selected={draftRange}
            onSelect={setDraftRange}
            numberOfMonths={1}
            locale={dayPickerLocale}
            className="rounded-2xl border border-border/75 bg-background p-2"
          />
        </div>
        <div className="flex flex-col-reverse gap-2 border-t border-border/70 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="w-full rounded-full sm:w-auto"
            onClick={handleReset}
          >
            <RotateCcw className="h-4 w-4" />
            {t('common.reset')}
          </Button>
          <Button
            type="button"
            size="sm"
            className="w-full rounded-full sm:w-auto"
            onClick={handleApply}
          >
            {t('common.apply')}
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
