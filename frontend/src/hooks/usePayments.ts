'use client';

import { makeCrud } from '@/lib/crudFactory';
import type { Payment } from '@/types/auth';

/**
 * Тело POST /api/payments/ (создание платежа перед проведением).
 *
 * Два основных сценария:
 *   1. kind='counterparty' — обычная оплата PO/SO. Поля:
 *      counterparty, direction, allocations → проводка пойдёт на 60.XX/62.XX.
 *   2. kind ∈ {opex, income, salary} — прочая операция. Поля:
 *      contra_subaccount (обязательно), counterparty (опционально).
 */
export interface PaymentInput {
  date: string;
  module: string | null;
  direction: 'out' | 'in';
  channel: 'cash' | 'transfer' | 'click' | 'other';
  kind: 'counterparty' | 'opex' | 'income' | 'salary' | 'internal';
  counterparty?: string | null;
  amount_uzs: string;
  cash_subaccount?: string | null;
  contra_subaccount?: string | null;
  expense_article?: string | null;
  currency?: string | null;
  exchange_rate?: string | null;
  exchange_rate_source?: string | null;
  amount_foreign?: string | null;
  notes?: string;
}

export const paymentsCrud = makeCrud<Payment, PaymentInput, PaymentInput>({
  key: ['payments'],
  path: '/api/payments/',
  ordering: '-date',
});

export const usePostPayment = paymentsCrud.makeAction<void, Payment>(
  (id) => `/api/payments/${id}/post/`,
);

export const useReversePayment = paymentsCrud.makeAction<{ reason?: string }, Payment>(
  (id) => `/api/payments/${id}/reverse/`,
);

export const useCancelPayment = paymentsCrud.makeAction<{ reason?: string }, Payment>(
  (id) => `/api/payments/${id}/cancel/`,
);
