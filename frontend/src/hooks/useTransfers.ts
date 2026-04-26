'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import { makeCrud } from '@/lib/crudFactory';
import type { InterModuleTransfer } from '@/types/auth';

export const transfersCrud = makeCrud<InterModuleTransfer>({
  key: ['transfers'],
  path: '/api/transfers/',
  ordering: '-transfer_date',
});

export const useSubmitTransfer = transfersCrud.makeAction<void, unknown>(
  (id) => `/api/transfers/${id}/submit/`,
);

export const useReviewTransfer = transfersCrud.makeAction<
  { reason?: string },
  unknown
>((id) => `/api/transfers/${id}/review/`);

/**
 * Принять транзфер. После accept:
 *  - Batch.current_module меняется → список партий в целевом модуле обновляется
 *  - StockMovement пара создаётся → список движений обновляется
 *  - JournalEntry пара создаётся → журнал обновляется
 *  - SlaughterShift incoming меняется → панель «Входящие» в /slaughter обновляется
 * Поэтому инвалидируем все связанные queries, не только ['transfers'].
 */
export function useAcceptTransfer() {
  const qc = useQueryClient();
  return useMutation<unknown, ApiError, { id: string; body?: void }>({
    mutationFn: ({ id }) =>
      apiFetch(`/api/transfers/${id}/accept/`, { method: 'POST' }),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ['transfers'], refetchType: 'all' }),
        qc.invalidateQueries({ queryKey: ['batches'], refetchType: 'all' }),
        qc.invalidateQueries({ queryKey: ['stock-movements'], refetchType: 'all' }),
        qc.invalidateQueries({ queryKey: ['journal-entries'], refetchType: 'all' }),
        qc.invalidateQueries({ queryKey: ['feedlot'], refetchType: 'all' }),
        qc.invalidateQueries({ queryKey: ['slaughter'], refetchType: 'all' }),
        qc.invalidateQueries({ queryKey: ['feed-batches'], refetchType: 'all' }),
      ]);
    },
  });
}

export const useCancelTransfer = transfersCrud.makeAction<
  { reason?: string },
  unknown
>((id) => `/api/transfers/${id}/cancel/`);
