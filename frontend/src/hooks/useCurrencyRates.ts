'use client';

import { useMemo } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import { asList } from '@/lib/paginated';
import type { CurrencyRef, ExchangeRate, Paginated } from '@/types/auth';

/**
 * Популярные валюты, которые должны быть сверху в dropdown-ах.
 * Порядок в массиве — порядок показа.
 */
export const POPULAR_CURRENCY_CODES = [
  'UZS', 'USD', 'EUR', 'RUB', 'KZT', 'CNY', 'GBP', 'JPY',
];

function rankOf(code: string): number {
  const i = POPULAR_CURRENCY_CODES.indexOf(code);
  return i === -1 ? Infinity : i;
}

/**
 * Сортировка: сначала валюты из POPULAR_CURRENCY_CODES в указанном порядке,
 * потом всё остальное по алфавиту кода.
 */
export function sortCurrencies(list: CurrencyRef[]): CurrencyRef[] {
  return [...list].sort((a, b) => {
    const ra = rankOf(a.code);
    const rb = rankOf(b.code);
    if (ra !== rb) return ra - rb;
    return a.code.localeCompare(b.code);
  });
}

export function useCurrencies() {
  return useQuery<CurrencyRef[], ApiError>({
    queryKey: ['currencies'],
    queryFn: async () => {
      // page_size=1000 — справочник валют ЦБ ~77 штук, показываем все в одном dropdown
      const data = await apiFetch<Paginated<CurrencyRef> | CurrencyRef[]>(
        '/api/currency/currencies/?is_active=true&page_size=1000',
        { skipOrg: true },
      );
      return asList(data);
    },
    staleTime: 10 * 60_000,
  });
}

/** Как useCurrencies, но сразу отсортированный по популярности. */
export function useCurrenciesSorted() {
  const q = useCurrencies();
  const sorted = useMemo(() => (q.data ? sortCurrencies(q.data) : undefined), [q.data]);
  return { ...q, data: sorted };
}

export function useLatestRates() {
  return useQuery<ExchangeRate[], ApiError>({
    queryKey: ['currency', 'latest'],
    queryFn: async () => {
      const data = await apiFetch<Paginated<ExchangeRate> | ExchangeRate[]>(
        '/api/currency/rates/latest/',
        { skipOrg: true },
      );
      return asList(data);
    },
    staleTime: 30_000,
  });
}

interface SyncResult {
  fetched: number;
  created: number;
  updated: number;
  skipped: number;
  currencies_created: number;
}

export function useSyncCbuRates() {
  const qc = useQueryClient();
  return useMutation<SyncResult, ApiError, void>({
    mutationFn: () =>
      apiFetch<SyncResult>('/api/currency/rates/sync_now/', {
        method: 'POST',
        skipOrg: true,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['currency', 'latest'] });
    },
  });
}

/**
 * Последний курс для валюты на указанную дату (с fallback до 7 дней назад —
 * поиск ведёт бэкенд через фильтр date_before).
 *
 * `currencyCode` — ISO-код ("USD", "EUR"). Для UZS хук возвращает null сразу
 * (не делает запрос).
 */
export function useRateOnDate(currencyCode: string | null | undefined, date: string) {
  const code = (currencyCode ?? '').toUpperCase();
  const enabled = Boolean(code) && code !== 'UZS' && Boolean(date);

  return useQuery<ExchangeRate | null, ApiError>({
    queryKey: ['currency', 'rate-on-date', code, date],
    enabled,
    queryFn: async () => {
      const qs = new URLSearchParams({
        currency: code,
        date_before: date,
        ordering: '-date',
      }).toString();
      const data = await apiFetch<Paginated<ExchangeRate> | ExchangeRate[]>(
        `/api/currency/rates/?${qs}`,
        { skipOrg: true },
      );
      const list = asList(data);
      return list.length > 0 ? list[0] : null;
    },
    staleTime: 5 * 60_000,
  });
}
