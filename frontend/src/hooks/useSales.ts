'use client';

import { makeCrud } from '@/lib/crudFactory';
import type { SaleOrder } from '@/types/auth';

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

export const useConfirmSale = salesCrud.makeAction<void, SaleOrder>(
  (id) => `/api/sales/orders/${id}/confirm/`,
);

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
