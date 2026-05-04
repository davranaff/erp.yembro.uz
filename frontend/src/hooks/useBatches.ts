'use client';

import { useQuery } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import { asList } from '@/lib/paginated';
import type {
  Batch,
  BatchCostEntry,
  BatchTrace,
  Paginated,
} from '@/types/auth';

export interface BatchesFilter {
  state?: string;
  current_module?: string;
  origin_module?: string;
  nomenclature?: string;
  parent_batch?: string;
  search?: string;
}

export function useBatches(filter: BatchesFilter = {}) {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(filter)) {
    if (v) params.set(k, v);
  }
  params.set('ordering', '-started_at');
  const qs = params.toString();
  return useQuery<Batch[], ApiError>({
    queryKey: ['batches', qs],
    queryFn: async () => {
      const data = await apiFetch<Paginated<Batch> | Batch[]>(`/api/batches/?${qs}`);
      return asList(data);
    },
    staleTime: 30_000,
  });
}

/**
 * Сквозная трассировка партии:
 *   GET /api/batches/{id}/trace/ → { batch, parent, children, chain_steps,
 *                                    cost_breakdown, totals }
 */
export function useBatchTrace(batchId: string | null | undefined) {
  return useQuery<BatchTrace, ApiError>({
    queryKey: ['batches', 'trace', batchId ?? ''],
    enabled: Boolean(batchId),
    queryFn: () => apiFetch<BatchTrace>(`/api/batches/${batchId}/trace/`),
    staleTime: 30_000,
  });
}

/**
 * Детальный список затрат по партии (с хронологией).
 *   GET /api/batches/{id}/cost-entries/
 */
export function useBatchCostEntries(batchId: string | null | undefined) {
  return useQuery<BatchCostEntry[], ApiError>({
    queryKey: ['batches', 'cost-entries', batchId ?? ''],
    enabled: Boolean(batchId),
    queryFn: async () => {
      const data = await apiFetch<Paginated<BatchCostEntry> | BatchCostEntry[]>(
        `/api/batches/${batchId}/cost-entries/`,
      );
      return asList(data);
    },
    staleTime: 30_000,
  });
}
