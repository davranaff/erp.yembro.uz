'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import { makeCrud } from '@/lib/crudFactory';
import type {
  CreditCheckResult,
  SaleCommunication,
  SaleOrder,
} from '@/types/auth';

/**
 * Тело, отправляемое на POST/PATCH. Поля amount_*, cost_uzs, payment_status и
 * прочие snapshot-поля — read-only, заполняются сервером при confirm.
 */
export interface SaleOrderInput {
  date: string;
  module: string;
  customer: string;
  warehouse: string;
  currency: string | null;
  notes?: string;
  due_date?: string | null;
  items: Array<{
    nomenclature: string;
    batch: string | null;
    vet_stock_batch: string | null;
    feed_batch: string | null;
    quantity: string;
    unit_price_uzs: string;
  }>;
}

export const salesCrud = makeCrud<SaleOrder, SaleOrderInput, SaleOrderInput>({
  key: ['sales', 'orders'],
  path: '/api/sales/orders/',
  ordering: '-date',
});

export const useConfirmSale = salesCrud.makeAction<
  {
    force_credit_override?: boolean;
    /** Обязательна когда force_credit_override=true (>= 10 символов).
     * Сохраняется в SaleOrder.credit_override_reason и идёт в audit. */
    credit_override_reason?: string;
  } | void,
  SaleOrder
>(
  (id) => `/api/sales/orders/${id}/confirm/`,
);

/**
 * GET /api/sales/orders/{id}/credit_check/ — превью кредитного гейта.
 * Без побочных эффектов, для UI-предупреждения перед confirm.
 */
export function useCreditCheck(orderId: string | null | undefined) {
  return useQuery<CreditCheckResult, ApiError>({
    queryKey: ['sales', 'orders', orderId ?? '', 'credit-check'],
    enabled: Boolean(orderId),
    queryFn: () =>
      apiFetch<CreditCheckResult>(
        `/api/sales/orders/${orderId}/credit_check/`,
      ),
    staleTime: 10_000,
  });
}

// ── Детальная страница: /api/sales/orders/{id}/summary/ ────────────────

export interface SaleOrderSummary {
  order: {
    id: string;
    doc_number: string;
    date: string;
    due_date: string | null;
    status: string;
    payment_status: string;
    amount_uzs: string;
    cost_uzs: string;
    margin_uzs: string;
    paid_amount_uzs: string;
    outstanding_uzs: string;
    currency_code: string | null;
    amount_foreign: string | null;
    exchange_rate: string | null;
    notes: string;
    customer_id: string | null;
    customer_name: string | null;
    customer_code: string | null;
    warehouse_name: string | null;
    module_code: string | null;
  };
  items: Array<{
    id: string;
    nomenclature_id: string | null;
    nomenclature_name: string | null;
    quantity: string;
    unit_price_uzs: string;
    line_total_uzs: string;
    cost_per_unit_uzs: string | null;
    line_cost_uzs: string;
    batch_doc: string | null;
  }>;
  payments: Array<{
    id: string;
    allocation_id: string;
    doc_number: string;
    date: string;
    direction: string;
    channel: string;
    kind: string;
    status: string;
    amount_uzs: string;
    payment_amount_uzs: string;
    currency_code: string | null;
    notes: string;
  }>;
  communications: Array<{
    id: string;
    contacted_at: string;
    method: string;
    outcome: string;
    customer_response: string;
    internal_note: string;
    promised_pay_date: string | null;
    next_action_date: string | null;
    contacted_by_name: string | null;
  }>;
  timeline: Array<{
    at: string;
    kind: string;
    title: string;
    description?: string;
    actor?: string | null;
  }>;
}

export function useSaleOrderSummary(id: string | null | undefined) {
  return useQuery<SaleOrderSummary, ApiError>({
    queryKey: ['sales', 'summary', id ?? ''],
    enabled: Boolean(id),
    queryFn: () => apiFetch<SaleOrderSummary>(`/api/sales/orders/${id}/summary/`),
    staleTime: 15_000,
  });
}

export const useReverseSale = salesCrud.makeAction<{ reason?: string }, SaleOrder>(
  (id) => `/api/sales/orders/${id}/reverse/`,
);

export interface RecordPaymentInput {
  channel: 'cash' | 'transfer' | 'click' | 'other';
  /** UUID кассы/счёта (GLSubaccount). Без этого backend подставит
   * дефолтные 50.01/51.01 — все платежи свалятся в общий котёл. */
  cash_subaccount?: string;
  amount_uzs?: string;
  date?: string;
  notes?: string;
}

export const useRecordSalePayment = salesCrud.makeAction<RecordPaymentInput, SaleOrder>(
  (id) => `/api/sales/orders/${id}/record_payment/`,
);

// ── Касания клиента (call log) ─────────────────────────────────────────

export interface SaleCommunicationInput {
  order: string;
  contacted_at: string;
  method: SaleCommunication['method'];
  outcome: SaleCommunication['outcome'];
  customer_response: string;
  internal_note?: string;
  promised_pay_date?: string | null;
  expected_pay_date?: string | null;
  next_action_date?: string | null;
}

export const saleCommunicationsCrud = makeCrud<
  SaleCommunication,
  SaleCommunicationInput,
  Partial<SaleCommunicationInput>
>({
  key: ['sales', 'communications'],
  path: '/api/sales/communications/',
  ordering: '-contacted_at',
});

/**
 * Удаление касания + ручная инвалидация debt-summary (карточка клиента
 * показывает агрегат касаний, а её queryKey не покрывается стандартным
 * crudFactory-onSuccess).
 */
export function useDeleteCommunicationWithDebtRefresh() {
  const qc = useQueryClient();
  return useMutation<void, ApiError, { id: string; customerId?: string }>({
    mutationFn: ({ id }) =>
      apiFetch<void>(`/api/sales/communications/${id}/`, { method: 'DELETE' }),
    onSuccess: async (_data, vars) => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ['sales', 'communications'] }),
        qc.invalidateQueries({ queryKey: ['sales', 'tasks'] }),
        ...(vars.customerId ? [
          qc.invalidateQueries({
            queryKey: ['counterparties', 'debt-summary', vars.customerId],
          }),
        ] : []),
      ]);
    },
  });
}

// ── Workflow задач (collection tasks) ───────────────────────────────────

export type CollectionTaskType =
  | 'callback_due' | 'promise_broken' | 'forecast_due' | 'escalation';
export type CollectionTaskPriority = 'high' | 'medium' | 'low';

export interface CollectionTask {
  type: CollectionTaskType;
  priority: CollectionTaskPriority;
  order_id: string;
  order_doc: string;
  customer_id: string;
  customer_name: string;
  customer_code: string;
  outstanding_uzs: string;
  days_overdue: number;
  title: string;
  detail: string;
  communication_id: string | null;
  promised_date: string | null;
  expected_date: string | null;
  callback_date: string | null;
  last_touch_date: string | null;
  contacted_by_name: string | null;
}

export interface CollectionTasksReport {
  as_of: string;
  total: number;
  counts: {
    callback_due: number;
    promise_broken: number;
    forecast_due: number;
    escalation: number;
  };
  callback_due: CollectionTask[];
  promise_broken: CollectionTask[];
  forecast_due: CollectionTask[];
  escalation: CollectionTask[];
}

/**
 * GET /api/sales/orders/tasks/[?mine=true]
 *
 * Workflow задач сборщика дебиторки. mine=true — задачи на касания
 * текущего пользователя (escalation остаётся глобальной).
 */
export function useCollectionTasks(opts: { mine?: boolean } = {}) {
  const qs = opts.mine ? '?mine=true' : '';
  return useQuery<CollectionTasksReport, ApiError>({
    queryKey: ['sales', 'tasks', opts.mine ?? false],
    queryFn: () =>
      apiFetch<CollectionTasksReport>(`/api/sales/orders/tasks/${qs}`),
    staleTime: 30_000,
  });
}
