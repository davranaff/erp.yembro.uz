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
  params.set('page_size', '2000');
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

export function useCounterpartiesPaginated(
  filter: CounterpartiesFilter,
  page: number,
  pageSize = 25,
) {
  const params = new URLSearchParams();
  if (filter.kind) params.set('kind', filter.kind);
  if (filter.is_active) params.set('is_active', filter.is_active);
  if (filter.search) params.set('search', filter.search);
  params.set('ordering', 'code');
  params.set('page', String(page));
  params.set('page_size', String(pageSize));
  const qs = params.toString();
  return useQuery<Paginated<Counterparty>, ApiError>({
    queryKey: [...KEY, 'page', qs],
    queryFn: () =>
      apiFetch<Paginated<Counterparty>>(`/api/counterparties/?${qs}`),
    staleTime: 30_000,
    placeholderData: (prev) => prev,
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
  /**
   * Стартовые предоплаты (kind=opening_balance_prepayment) — синтетические
   * Payment'ы миграции с отрицательного opening_debt. Кассир может
   * аллоцировать `free_uzs` к новым SO/PO через
   * POST /api/payments/{id}/apply_prepayment/.
   */
  prepayments: Array<{
    id: string;
    doc_number: string;
    date: string;
    amount_uzs: string;
    used_uzs: string;
    free_uzs: string;
    direction: 'in' | 'out';
  }>;
  prepayments_total_free_uzs: string;
}

// ── Расширенная сводка для детальной страницы (full_summary) ────────────

export interface CounterpartyFullSummary extends CounterpartyDebtSummary {
  all_orders: Array<{
    id: string;
    kind: 'sale' | 'purchase';
    doc_number: string;
    date: string;
    due_date: string | null;
    status: string;
    payment_status: string | null;
    amount_uzs: string;
    paid_amount_uzs: string;
    outstanding_uzs: string;
  }>;
  all_orders_count: number;
  all_payments: Array<{
    id: string;
    doc_number: string;
    date: string;
    direction: 'in' | 'out';
    channel: string;
    kind: string;
    status: string;
    amount_uzs: string;
    currency_code: string | null;
    amount_foreign: string | null;
    exchange_rate: string | null;
    notes: string;
  }>;
  all_payments_count: number;
  monthly_turnover: Array<{
    month: string; // "YYYY-MM"
    /** Реально оплаченная клиентом часть продаж за месяц (актуальные деньги). */
    sales_uzs: string;
    /** Полный объём отгрузок за месяц (начисление, включая неоплаченное). */
    sales_invoiced_uzs: string;
    purchases_uzs: string;
    payments_in_uzs: string;
    payments_out_uzs: string;
  }>;
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

export function useCounterpartyFullSummary(id: string | null | undefined) {
  return useQuery<CounterpartyFullSummary, ApiError>({
    queryKey: ['counterparties', 'full-summary', id ?? ''],
    enabled: Boolean(id),
    queryFn: () =>
      apiFetch<CounterpartyFullSummary>(
        `/api/counterparties/${id}/full_summary/`,
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


export interface NotifyChannelResult {
  channel: 'sms' | 'tg';
  ok: boolean;
  detail: string;
  record_id: string | null;
}

export interface NotifyDebtResponse {
  results: NotifyChannelResult[];
  any_ok: boolean;
}

export function useNotifyDebt() {
  return useMutation<
    NotifyDebtResponse,
    ApiError,
    { id: string; channels: Array<'sms' | 'tg'> }
  >({
    mutationFn: ({ id, channels }) =>
      apiFetch<NotifyDebtResponse>(
        `/api/counterparties/${id}/notify-debt/`,
        { method: 'POST', body: { channels } },
      ),
  });
}

export function useInviteToTg() {
  return useMutation<NotifyChannelResult, ApiError, string>({
    mutationFn: (id) =>
      apiFetch<NotifyChannelResult>(
        `/api/counterparties/${id}/invite-tg/`,
        { method: 'POST', body: {} },
      ),
  });
}
