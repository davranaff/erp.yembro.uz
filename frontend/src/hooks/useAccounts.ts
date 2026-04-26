'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import { makeCrud } from '@/lib/crudFactory';
import { asList } from '@/lib/paginated';
import type { GLAccount, GLSubaccount, Paginated } from '@/types/auth';

const ACCOUNTS_KEY = ['accounting', 'accounts'];
const SUBACCOUNTS_KEY = ['accounting', 'subaccounts'];

export function useAccounts() {
  return useQuery<GLAccount[], ApiError>({
    queryKey: ACCOUNTS_KEY,
    queryFn: async () => {
      // page_size=1000 — счетов и субсчетов ≤ 100, нужен весь список сразу.
      const data = await apiFetch<Paginated<GLAccount> | GLAccount[]>(
        '/api/accounting/accounts/?ordering=code&page_size=1000',
      );
      return asList(data);
    },
    staleTime: 5 * 60_000,
  });
}

export interface SubaccountInput {
  account: string;
  code: string;
  name: string;
  module?: string | null;
}

/**
 * Базовая фабрика. Использует её `useList` и `useDelete`, но write-мутации
 * переопределены ниже чтобы инвалидировать и `['accounting', 'accounts']`
 * (вложенный список subaccounts в GLAccount) и `['accounting', 'subaccounts']`.
 */
export const subaccountsCrud = makeCrud<GLSubaccount, SubaccountInput, SubaccountInput>({
  key: SUBACCOUNTS_KEY,
  path: '/api/accounting/subaccounts/',
  ordering: 'code',
});

function invalidateBoth(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ACCOUNTS_KEY });
  qc.invalidateQueries({ queryKey: SUBACCOUNTS_KEY });
}

/**
 * Кастомные обёртки: inv кэша сразу обоих списков.
 * Дефолтные useCreate/useUpdate/useDelete из subaccountsCrud инвалидируют
 * только SUBACCOUNTS_KEY, но /accounts страница читает ACCOUNTS_KEY.
 */
export function useCreateSubaccount() {
  const qc = useQueryClient();
  return useMutation<GLSubaccount, ApiError, SubaccountInput>({
    mutationFn: (body) =>
      apiFetch<GLSubaccount>('/api/accounting/subaccounts/', {
        method: 'POST',
        body: body as unknown as Record<string, unknown>,
      }),
    onSuccess: () => invalidateBoth(qc),
  });
}

export function useUpdateSubaccount() {
  const qc = useQueryClient();
  return useMutation<GLSubaccount, ApiError, { id: string; patch: Partial<SubaccountInput> }>({
    mutationFn: ({ id, patch }) =>
      apiFetch<GLSubaccount>(`/api/accounting/subaccounts/${id}/`, {
        method: 'PATCH',
        body: patch as unknown as Record<string, unknown>,
      }),
    onSuccess: () => invalidateBoth(qc),
  });
}

export function useDeleteSubaccount() {
  const qc = useQueryClient();
  return useMutation<void, ApiError, string>({
    mutationFn: (id) =>
      apiFetch<void>(`/api/accounting/subaccounts/${id}/`, { method: 'DELETE' }),
    onSuccess: () => invalidateBoth(qc),
  });
}

/** Плоский список всех субсчетов (для селекторов в формах — касса, contra). */
export function useSubaccounts(filter?: { account?: string; module?: string }) {
  return subaccountsCrud.useList(filter ?? {});
}
