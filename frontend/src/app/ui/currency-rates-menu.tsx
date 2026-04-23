/* eslint-disable @typescript-eslint/no-unnecessary-condition */
// The currency list can be empty (fresh org, loading state) so every
// lookup against it returns a possibly-undefined value. TypeScript
// agrees with that but the ESLint rule over-narrows here — toggle it
// off for this widget instead of papering over with `!` assertions.
import { Banknote, ChevronDown, Loader2, RefreshCw } from 'lucide-react';
import { z } from 'zod';

import { Button } from '@/components/ui/button';
import { ErrorNotice } from '@/components/ui/error-notice';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { useToast } from '@/components/ui/toast';
import { apiClient } from '@/shared/api/api-client';
import { syncExchangeRatesFromCbu } from '@/shared/api/exchange-rates';
import { useApiMutation, useApiQuery } from '@/shared/api/react-query';
import { useI18n } from '@/shared/i18n';
import { cn } from '@/shared/lib/cn';

/**
 * Navbar widget for currency rates. Two goals:
 *   1. Keep the base currency (usually UZS) obvious — so the user can
 *      answer the "in what money am I looking at numbers?" question
 *      without hunting settings.
 *   2. Show the current rate for the few other currencies the org
 *      actually uses, without opening a full finance page.
 *
 * Non-admin users see a read-only list; admin/super_admin also get a
 * "Обновить из ЦБ" button that calls the existing sync endpoint.
 */

const currencySchema = z.object({
  id: z.string(),
  code: z.string(),
  name: z.string(),
  symbol: z.string().nullable().optional(),
  is_default: z.boolean().optional(),
  is_active: z.boolean().optional(),
  sort_order: z.number().optional(),
});

const currencyListSchema = z.object({
  items: z.array(currencySchema),
  total: z.number().optional(),
});

type Currency = z.infer<typeof currencySchema>;

const latestRateSchema = z.object({
  currency_id: z.string(),
  rate: z.string(),
  rate_date: z.string().nullable(),
  source: z.string(),
});

type LatestRate = z.infer<typeof latestRateSchema>;

type LatestRatesBatch = { items: LatestRate[] };

const rateNumberFormatter = new Intl.NumberFormat('ru-RU', {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

const formatRate = (raw: string): string => {
  const value = Number(raw);
  if (!Number.isFinite(value)) {
    return raw;
  }
  return rateNumberFormatter.format(value);
};

type CurrencyRatesMenuProps = {
  canSyncFromCbu: boolean;
};

export function CurrencyRatesMenu({ canSyncFromCbu }: CurrencyRatesMenuProps) {
  const { t } = useI18n();
  const { show: showToast } = useToast();

  const currenciesQuery = useApiQuery<z.infer<typeof currencyListSchema>>({
    queryKey: ['core', 'currencies', 'list'],
    queryFn: () =>
      apiClient.get('/core/currencies?limit=100&order_by=sort_order', currencyListSchema),
    staleTime: 5 * 60_000,
  });

  const currencies = (currenciesQuery.data?.items ?? []).filter((item) => item.is_active !== false);
  const baseCurrency: Currency | undefined =
    currencies.find((item) => item.is_default) ?? currencies[0];
  const otherCurrencies = currencies.filter((item) => !baseCurrency || item.id !== baseCurrency.id);
  const otherCurrencyIds = otherCurrencies.map((item) => item.id).sort();

  const ratesQuery = useApiQuery<LatestRatesBatch>({
    queryKey: ['core', 'currencies', 'latest-rates', otherCurrencyIds],
    queryFn: async () => {
      // The `/latest` endpoint is per-currency; fan out client-side so
      // one failed currency doesn't drag the whole menu into an error
      // state. Each missing currency just gets no rate row.
      const settled = await Promise.allSettled(
        otherCurrencyIds.map(async (currencyId) => {
          const qs = new URLSearchParams({ currency_id: currencyId }).toString();
          return apiClient.get<LatestRate>(
            `/core/currency-exchange-rates/latest?${qs}`,
            latestRateSchema,
          );
        }),
      );
      const items: LatestRate[] = [];
      for (const result of settled) {
        if (result.status === 'fulfilled') {
          items.push(result.value);
        }
      }
      return { items };
    },
    enabled: otherCurrencyIds.length > 0,
    staleTime: 60_000,
  });

  const syncMutation = useApiMutation({
    mutationKey: ['core', 'currency-exchange-rates', 'sync'],
    mutationFn: () => syncExchangeRatesFromCbu(),
    onSuccess: async (data) => {
      showToast({
        tone: 'success',
        title: t('currencyMenu.syncSuccess', undefined, 'Курсы обновлены'),
        description: `${data.inserted} + ${data.updated}`,
      });
      await ratesQuery.refetch();
    },
    onError: (error) => {
      showToast({
        tone: 'error',
        title: t('currencyMenu.syncFailed', undefined, 'Не удалось обновить курсы'),
        description: error.message,
      });
    },
  });

  const ratesById = new Map<string, LatestRate>();
  for (const rate of ratesQuery.data?.items ?? []) {
    ratesById.set(rate.currency_id, rate);
  }

  // Compact trigger: show base code + one-line rate summary for the
  // most likely currency (USD, or the first non-base active one).
  const primaryNonBase = otherCurrencies.find((item) => item.code === 'USD') ?? otherCurrencies[0];
  const primaryRate = primaryNonBase ? ratesById.get(primaryNonBase.id) : null;

  const triggerSummary = (() => {
    if (!baseCurrency) {
      return t('currencyMenu.trigger', undefined, 'Курсы');
    }
    if (!primaryNonBase || !primaryRate) {
      return baseCurrency.code;
    }
    return `${primaryNonBase.code} ${formatRate(primaryRate.rate)}`;
  })();

  return (
    <Popover>
      <PopoverTrigger
        aria-label={t('currencyMenu.label', undefined, 'Курсы валют')}
        className={cn(
          'border-primary/24 inline-flex h-8 items-center gap-1.5 rounded-full border bg-white px-3 text-xs font-medium text-foreground',
          'shadow-[0_14px_32px_-26px_rgba(15,23,42,0.1)] outline-none transition-all',
          'hover:bg-secondary/58 aria-expanded:border-primary/34 aria-expanded:bg-secondary/72',
          'focus-visible:ring-3 focus-visible:border-ring focus-visible:ring-ring/50',
        )}
      >
        <Banknote className="h-3.5 w-3.5 opacity-70" />
        <span className="hidden sm:inline">{triggerSummary}</span>
        <ChevronDown className="h-3 w-3 opacity-70" />
      </PopoverTrigger>
      <PopoverContent
        align="end"
        sideOffset={8}
        className="w-80 rounded-2xl border border-slate-200 bg-white p-3 shadow-[0_28px_72px_-42px_rgba(15,23,42,0.2)]"
      >
        <div className="mb-2 flex items-center justify-between gap-2">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {t('currencyMenu.title', undefined, 'Курсы валют')}
            </div>
            {baseCurrency ? (
              <div className="text-xs text-muted-foreground">
                {t(
                  'currencyMenu.baseLabel',
                  { code: baseCurrency.code, name: baseCurrency.name },
                  'База: {code} · {name}',
                )}
              </div>
            ) : null}
          </div>
          {canSyncFromCbu ? (
            <Button
              type="button"
              variant="outline"
              size="xs"
              onClick={() => syncMutation.mutate()}
              disabled={syncMutation.isPending}
              title={t('currencyMenu.syncHint', undefined, 'Обновить из ЦБ РУз')}
            >
              {syncMutation.isPending ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <RefreshCw className="h-3 w-3" />
              )}
              <span className="hidden sm:inline">
                {t('currencyMenu.sync', undefined, 'Обновить')}
              </span>
            </Button>
          ) : null}
        </div>

        {currenciesQuery.isLoading ? (
          <div className="flex items-center gap-2 rounded-xl bg-muted/30 px-3 py-4 text-xs text-muted-foreground">
            <Loader2 className="h-3 w-3 animate-spin" />
            {t('common.loadingLabel', undefined, 'Загружаем…')}
          </div>
        ) : null}

        {currenciesQuery.error ? <ErrorNotice error={currenciesQuery.error} /> : null}

        {!currenciesQuery.isLoading && otherCurrencies.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-200 bg-muted/20 px-3 py-4 text-center text-xs text-muted-foreground">
            {t('currencyMenu.empty', undefined, 'Других валют кроме базовой пока не добавлено.')}
          </div>
        ) : null}

        {otherCurrencies.length > 0 ? (
          <ul className="divide-y divide-slate-100">
            {otherCurrencies.map((currency) => {
              const rate = ratesById.get(currency.id);
              return (
                <li key={currency.id} className="flex items-center justify-between gap-3 py-2">
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-foreground">
                      1 {currency.code}
                      <span className="text-muted-foreground"> → </span>
                      {rate ? (
                        <>
                          {formatRate(rate.rate)}
                          <span className="text-xs text-muted-foreground">
                            {' '}
                            {baseCurrency?.code ?? ''}
                          </span>
                        </>
                      ) : (
                        <span className="text-xs text-muted-foreground">
                          {t('currencyMenu.noRate', undefined, 'нет курса')}
                        </span>
                      )}
                    </div>
                    <div className="truncate text-xs text-muted-foreground">
                      {currency.name}
                      {rate?.rate_date ? ` · ${rate.rate_date}` : ''}
                    </div>
                  </div>
                  {rate ? (
                    <span
                      className={cn(
                        'inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide',
                        rate.source === 'cbu'
                          ? 'bg-emerald-500/10 text-emerald-700 ring-1 ring-inset ring-emerald-500/25'
                          : 'bg-slate-100 text-muted-foreground',
                      )}
                    >
                      {rate.source}
                    </span>
                  ) : null}
                </li>
              );
            })}
          </ul>
        ) : null}

        {ratesQuery.isFetching && otherCurrencies.length > 0 ? (
          <div className="mt-2 flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <Loader2 className="h-3 w-3 animate-spin" />
            {t('currencyMenu.fetching', undefined, 'Обновляем…')}
          </div>
        ) : null}
      </PopoverContent>
    </Popover>
  );
}
