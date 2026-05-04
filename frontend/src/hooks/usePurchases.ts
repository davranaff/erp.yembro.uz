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
