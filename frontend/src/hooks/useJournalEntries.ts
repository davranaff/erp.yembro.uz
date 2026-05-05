'use client';

import { useQuery } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import { asList } from '@/lib/paginated';
import type { JournalEntry, Paginated } from '@/types/auth';

export interface LedgerFilter {
  module?: string;
  debit_subaccount?: string;
  credit_subaccount?: string;
  counterparty?: string;
  search?: string;
  entry_date_after?: string;
  entry_date_before?: string;
  limit?: number;
}

function buildLedgerParams(filter: LedgerFilter): URLSearchParams {
  const params = new URLSearchParams();
  if (filter.module) params.set('module', filter.module);
  if (filter.debit_subaccount) params.set('debit_subaccount', filter.debit_subaccount);
  if (filter.credit_subaccount) params.set('credit_subaccount', filter.credit_subaccount);
  if (filter.counterparty) params.set('counterparty', filter.counterparty);
  if (filter.search) params.set('search', filter.search);
  if (filter.entry_date_after) params.set('entry_date_after', filter.entry_date_after);
  if (filter.entry_date_before) params.set('entry_date_before', filter.entry_date_before);
  return params;
}

export function useJournalEntries(filter: LedgerFilter) {
  const params = buildLedgerParams(filter);
  params.set('ordering', '-entry_date');
  params.set('page_size', '2000');
  const qs = params.toString();

  return useQuery<JournalEntry[], ApiError>({
    queryKey: ['journal-entries', qs],
    queryFn: async () => {
      const data = await apiFetch<Paginated<JournalEntry> | JournalEntry[]>(
        `/api/accounting/entries/?${qs}`,
      );
      const rows = asList(data);
      return filter.limit ? rows.slice(0, filter.limit) : rows;
    },
    staleTime: 15_000,
  });
}

export function useJournalEntriesPaginated(
  filter: LedgerFilter,
  page = 1,
  pageSize = 50,
) {
  const params = buildLedgerParams(filter);
  params.set('ordering', '-entry_date');
  params.set('page', String(page));
  params.set('page_size', String(pageSize));
  const qs = params.toString();
  return useQuery<Paginated<JournalEntry>, ApiError>({
    queryKey: ['journal-entries', 'page', qs],
    queryFn: () => apiFetch<Paginated<JournalEntry>>(`/api/accounting/entries/?${qs}`),
    staleTime: 15_000,
    placeholderData: (prev) => prev,
  });
}
