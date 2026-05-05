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

export const useReverseSale = salesCrud.makeAction<{ reason?: string }, SaleOrder>(
  (id) => `/api/sales/orders/${id}/reverse/`,
);

export interface RecordPaymentInput {
  channel: 'cash' | 'transfer' | 'click' | 'other';
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
