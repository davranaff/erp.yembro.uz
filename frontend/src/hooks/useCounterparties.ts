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
  credit_limit_uzs?: string | null;
  max_overdue_days?: number | null;
};

// ── Карточка должника (debt card) ──────────────────────────────────────

export interface CounterpartyDebtSummary {
  counterparty: Counterparty;
  aging: {
    current: string;
    b_0_30: string;
    b_31_60: string;
    b_61_90: string;
    b_90_plus: string;
    total: string;
    oldest_overdue_days: number;
    orders_count: number;
    has_overdue: boolean;
  } | null;
  aging_as_of: string;
  credit: {
    ok: boolean;
    reasons: string[];
    current_debt_uzs: string;
    oldest_overdue_days: number;
    limit_uzs: string | null;
    max_overdue_days: number | null;
    new_sale_uzs: string;
    projected_debt_uzs: string;
  };
  credit_utilization_pct: number | null;
  open_orders: Array<{
    id: string;
    doc_number: string;
    date: string;
    due_date: string | null;
    amount_uzs: string;
    paid_amount_uzs: string;
    outstanding_uzs: string;
    payment_status: 'unpaid' | 'partial' | 'paid' | 'overpaid';
  }>;
  open_orders_count: number;
  communications: Array<{
    id: string;
    order_id: string;
    order_doc: string;
    contacted_at: string;
    method: string;
    method_display: string;
    outcome: string;
    outcome_display: string;
    customer_response: string;
    internal_note: string;
    promised_pay_date: string | null;
    expected_pay_date: string | null;
    next_action_date: string | null;
    contacted_by: string | null;
    contacted_by_name: string | null;
    created_at: string;
    updated_at: string;
  }>;
  communications_count: number;
}

export function useCounterparty(id: string | null | undefined) {
  return useQuery<Counterparty, ApiError>({
    queryKey: ['counterparties', 'detail', id ?? ''],
    enabled: Boolean(id),
    queryFn: () => apiFetch<Counterparty>(`/api/counterparties/${id}/`),
    staleTime: 30_000,
  });
}

export function useCounterpartyDebtSummary(id: string | null | undefined) {
  return useQuery<CounterpartyDebtSummary, ApiError>({
    queryKey: ['counterparties', 'debt-summary', id ?? ''],
    enabled: Boolean(id),
    queryFn: () =>
      apiFetch<CounterpartyDebtSummary>(
        `/api/counterparties/${id}/debt_summary/`,
      ),
    staleTime: 15_000,
  });
}

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
