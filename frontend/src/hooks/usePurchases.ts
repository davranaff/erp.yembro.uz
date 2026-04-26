'use client';

import { makeCrud } from '@/lib/crudFactory';
import type { PurchaseOrder } from '@/types/auth';

/**
 * Тело POST/PATCH на закуп.
 * amount_*, exchange_rate*, payment_status, paid_amount_uzs — read-only,
 * заполняются сервером при confirm.
 */
export interface PurchaseOrderInput {
  date: string;
  module: string;
  counterparty: string;
  warehouse: string;
  currency: string | null;
  batch?: string | null;
  notes?: string;
  items: Array<{
    nomenclature: string;
    quantity: string;
    unit_price: string;
  }>;
}

export const purchasesCrud = makeCrud<PurchaseOrder, PurchaseOrderInput, PurchaseOrderInput>({
  key: ['purchases', 'orders'],
  path: '/api/purchases/orders/',
  ordering: '-date',
});

export const useConfirmPurchase = purchasesCrud.makeAction<void, PurchaseOrder>(
  (id) => `/api/purchases/orders/${id}/confirm/`,
);

export const useReversePurchase = purchasesCrud.makeAction<{ reason?: string }, PurchaseOrder>(
  (id) => `/api/purchases/orders/${id}/reverse/`,
);
