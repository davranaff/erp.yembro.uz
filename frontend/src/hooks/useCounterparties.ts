'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import { asList } from '@/lib/paginated';
import type { Counterparty, Paginated } from '@/types/auth';

export interface CounterpartiesFilter {
  kind?: string;
  is_active?: string;
  search?: string;
}

const KEY = ['counterparties'] as const;

export function useCounterparties(filter: CounterpartiesFilter = {}) {
  const params = new URLSearchParams();
  if (filter.kind) params.set('kind', filter.kind);
  if (filter.is_active) params.set('is_active', filter.is_active);
  if (filter.search) params.set('search', filter.search);
  params.set('ordering', 'code');
  const qs = params.toString();
  return useQuery<Counterparty[], ApiError>({
    queryKey: [...KEY, qs],
    queryFn: async () => {
      const data = await apiFetch<Paginated<Counterparty> | Counterparty[]>(
        `/api/counterparties/?${qs}`,
      );
      return asList(data);
    },
    staleTime: 30_000,
  });
}

type CreatePayload = {
  code: string;
  kind: string;
  name: string;
  inn?: string;
  specialization?: string;
  phone?: string;
  email?: string;
  address?: string;
  is_active?: boolean;
  notes?: string;
};

export function useCreateCounterparty() {
  const qc = useQueryClient();
  return useMutation<Counterparty, ApiError, CreatePayload>({
    mutationFn: (body) =>
      apiFetch<Counterparty>('/api/counterparties/', { method: 'POST', body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEY });
    },
  });
}

export function useUpdateCounterparty() {
  const qc = useQueryClient();
  return useMutation<Counterparty, ApiError, { id: string; patch: Partial<CreatePayload> }>({
    mutationFn: ({ id, patch }) =>
      apiFetch<Counterparty>(`/api/counterparties/${id}/`, { method: 'PATCH', body: patch }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEY });
    },
  });
}

export function useDeleteCounterparty() {
  const qc = useQueryClient();
  return useMutation<void, ApiError, string>({
    mutationFn: (id) => apiFetch<void>(`/api/counterparties/${id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEY });
    },
  });
}
