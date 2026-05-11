'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import { makeCrud } from '@/lib/crudFactory';
import type { PurchaseAttachment, PurchaseOrder } from '@/types/auth';

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

// ── Файл-приложения к закупам ─────────────────────────────────────────

export const MAX_PURCHASE_ATTACHMENT_BYTES = 50 * 1024 * 1024;

export function usePurchaseAttachments(purchaseId: string | null | undefined) {
  return useQuery<PurchaseAttachment[], ApiError>({
    queryKey: ['purchases', 'attachments', purchaseId ?? ''],
    enabled: Boolean(purchaseId),
    queryFn: async () => {
      const data = await apiFetch<unknown>(
        `/api/purchases/attachments/?purchase=${purchaseId}`,
      );
      // DRF при пагинации возвращает {results}, без — массив
      if (Array.isArray(data)) return data as PurchaseAttachment[];
      const results = (data as { results?: PurchaseAttachment[] })?.results;
      return results ?? [];
    },
    staleTime: 30_000,
  });
}

export function useUploadPurchaseAttachment() {
  const qc = useQueryClient();
  return useMutation<
    PurchaseAttachment,
    ApiError,
    { purchaseId: string; file: File; description?: string }
  >({
    mutationFn: ({ purchaseId, file, description }) => {
      const fd = new FormData();
      fd.append('purchase', purchaseId);
      fd.append('file', file);
      if (description) fd.append('description', description);
      return apiFetch<PurchaseAttachment>('/api/purchases/attachments/', {
        method: 'POST',
        body: fd,
      });
    },
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({
        queryKey: ['purchases', 'attachments', vars.purchaseId],
      });
    },
  });
}

export function useDeletePurchaseAttachment() {
  const qc = useQueryClient();
  return useMutation<void, ApiError, { id: string; purchaseId: string }>({
    mutationFn: ({ id }) =>
      apiFetch<void>(`/api/purchases/attachments/${id}/`, { method: 'DELETE' }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({
        queryKey: ['purchases', 'attachments', vars.purchaseId],
      });
    },
  });
}

// ── Детальная страница: /api/purchases/orders/{id}/summary/ ────────────

export interface PurchaseOrderSummary {
  order: {
    id: string;
    doc_number: string;
    date: string;
    due_date: string | null;
    status: string;
    payment_status: string | null;
    amount_uzs: string;
    paid_amount_uzs: string;
    outstanding_uzs: string;
    currency_code: string | null;
    amount_foreign: string | null;
    exchange_rate: string | null;
    notes: string;
    counterparty_id: string | null;
    counterparty_name: string | null;
    counterparty_code: string | null;
    warehouse_name: string | null;
    module_code: string | null;
  };
  items: Array<{
    id: string;
    nomenclature_id: string | null;
    nomenclature_name: string | null;
    quantity: string;
    unit_price_uzs: string | null;
    line_total_uzs: string;
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
  attachments: Array<{
    id: string;
    file: string | null;
    name: string;
    uploaded_at: string | null;
  }>;
  timeline: Array<{
    at: string;
    kind: string;
    title: string;
    description?: string;
    actor?: string | null;
  }>;
}

export function usePurchaseOrderSummary(id: string | null | undefined) {
  return useQuery<PurchaseOrderSummary, ApiError>({
    queryKey: ['purchases', 'summary', id ?? ''],
    enabled: Boolean(id),
    queryFn: () => apiFetch<PurchaseOrderSummary>(`/api/purchases/orders/${id}/summary/`),
    staleTime: 15_000,
  });
}
