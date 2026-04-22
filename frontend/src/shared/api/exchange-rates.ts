import { z } from 'zod';

import { apiClient } from './api-client';

/** One row of the exchange-rate history (as stored in the DB).
 *
 * We keep ``rate`` as ``string`` to avoid floating-point rounding
 * issues — backends serialize Numeric as strings and the UI formats
 * the value with ``Intl.NumberFormat`` anyway. */
export const currencyExchangeRateSchema = z.object({
  id: z.string(),
  organization_id: z.string(),
  currency_id: z.string(),
  rate_date: z.string(),
  rate: z.string(),
  source: z.string(),
  source_ref: z.string().nullable().optional(),
  created_at: z.string().optional(),
  updated_at: z.string().optional(),
});

export type CurrencyExchangeRate = z.infer<typeof currencyExchangeRateSchema>;

export const currencyExchangeRateListResponseSchema = z.object({
  items: z.array(currencyExchangeRateSchema),
  total: z.number(),
  limit: z.number(),
  offset: z.number(),
  has_more: z.boolean(),
});

export type CurrencyExchangeRateListResponse = z.infer<
  typeof currencyExchangeRateListResponseSchema
>;

export const resolvedRateSchema = z.object({
  currency_id: z.string(),
  currency_code: z.string(),
  rate: z.string(),
  rate_date: z.string().nullable(),
  source: z.string(),
  is_base: z.boolean(),
  on_date: z.string(),
});

export type ResolvedRate = z.infer<typeof resolvedRateSchema>;

export const latestRateSchema = z.object({
  currency_id: z.string(),
  rate: z.string(),
  rate_date: z.string().nullable(),
  source: z.string(),
  source_ref: z.string().nullable().optional(),
});

export type LatestRate = z.infer<typeof latestRateSchema>;

export const cbuSyncResponseSchema = z.object({
  ok: z.boolean(),
  inserted: z.number(),
  updated: z.number(),
  skipped: z.number(),
  rates: z.array(
    z.object({
      currency_id: z.string(),
      currency_code: z.string(),
      rate_date: z.string(),
      rate: z.string(),
    }),
  ),
});

export type CbuSyncResponse = z.infer<typeof cbuSyncResponseSchema>;

export type ListExchangeRatesParams = {
  currencyId?: string;
  dateFrom?: string;
  dateTo?: string;
  limit?: number;
  offset?: number;
  orderBy?: string;
};

export const listExchangeRates = (params: ListExchangeRatesParams = {}) => {
  const search = new URLSearchParams();
  if (params.currencyId) search.set('currency_id', params.currencyId);
  if (params.dateFrom) search.set('date_from', params.dateFrom);
  if (params.dateTo) search.set('date_to', params.dateTo);
  if (params.limit != null) search.set('limit', String(params.limit));
  if (params.offset != null) search.set('offset', String(params.offset));
  if (params.orderBy) search.set('order_by', params.orderBy);
  const qs = search.toString();
  const path = qs
    ? `/core/currency-exchange-rates?${qs}`
    : `/core/currency-exchange-rates`;
  return apiClient.get<CurrencyExchangeRateListResponse>(
    path,
    currencyExchangeRateListResponseSchema,
  );
};

export const getLatestExchangeRate = (currencyId: string) => {
  const qs = new URLSearchParams({ currency_id: currencyId }).toString();
  return apiClient.get<LatestRate>(
    `/core/currency-exchange-rates/latest?${qs}`,
    latestRateSchema,
  );
};

export const resolveExchangeRate = (currencyId: string, onDate?: string) => {
  const search = new URLSearchParams({ currency_id: currencyId });
  if (onDate) search.set('on_date', onDate);
  return apiClient.get<ResolvedRate>(
    `/core/currency-exchange-rates/resolve?${search.toString()}`,
    resolvedRateSchema,
  );
};

export const syncExchangeRatesFromCbu = (codes?: string[]) => {
  return apiClient.post<CbuSyncResponse, { codes?: string[] }>(
    '/core/currency-exchange-rates/sync',
    codes && codes.length > 0 ? { codes } : {},
    cbuSyncResponseSchema,
  );
};

export type CreateManualExchangeRatePayload = {
  currency_id: string;
  rate_date: string;
  rate: string | number;
  source?: 'manual';
  source_ref?: string | null;
};

export const createManualExchangeRate = (payload: CreateManualExchangeRatePayload) => {
  return apiClient.post<CurrencyExchangeRate, CreateManualExchangeRatePayload>(
    '/core/currency-exchange-rates',
    { ...payload, source: payload.source ?? 'manual' },
    currencyExchangeRateSchema,
  );
};
