'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import { asList } from '@/lib/paginated';
import { makeCrud } from '@/lib/crudFactory';
import type {
  Batch,
  IncubationRegimeDay,
  IncubationRun,
  IncubationStats,
  IncubationTimelineEvent,
  MirageInspection,
  Paginated,
} from '@/types/auth';

export const runsCrud = makeCrud<IncubationRun>({
  key: ['incubation', 'runs'],
  path: '/api/incubation/runs/',
  ordering: '-loaded_date',
});

export const regimeDaysCrud = makeCrud<IncubationRegimeDay>({
  key: ['incubation', 'regime-days'],
  path: '/api/incubation/regime-days/',
  ordering: 'day',
});

export const mirageCrud = makeCrud<MirageInspection>({
  key: ['incubation', 'mirage'],
  path: '/api/incubation/mirage/',
  ordering: '-inspection_date',
});

export const useHatch = runsCrud.makeAction<
  {
    chick_nomenclature: string;
    hatched_count: number;
    discarded_count?: number;
    actual_hatch_date?: string;
  },
  unknown
>((id) => `/api/incubation/runs/${id}/hatch/`);

export const useTransferToHatcher = runsCrud.makeAction<
  { hatcher_block: string },
  unknown
>((id) => `/api/incubation/runs/${id}/transfer-to-hatcher/`);

export const useCancelRun = runsCrud.makeAction<
  { reason?: string },
  unknown
>((id) => `/api/incubation/runs/${id}/cancel/`);

/** GET /api/incubation/runs/{id}/stats/ */
export function useIncubationStats(runId: string | null | undefined) {
  return useQuery<IncubationStats, ApiError>({
    queryKey: ['incubation', 'stats', runId],
    enabled: Boolean(runId),
    queryFn: () =>
      apiFetch<IncubationStats>(`/api/incubation/runs/${runId}/stats/`),
    staleTime: 30_000,
  });
}

interface TimelineResponse {
  run_id: string;
  events: IncubationTimelineEvent[];
  counts: Record<string, number>;
}

/** GET /api/incubation/runs/{id}/timeline/ */
export function useIncubationTimeline(runId: string | null | undefined) {
  return useQuery<TimelineResponse, ApiError>({
    queryKey: ['incubation', 'timeline', runId],
    enabled: Boolean(runId),
    queryFn: () =>
      apiFetch<TimelineResponse>(`/api/incubation/runs/${runId}/timeline/`),
    staleTime: 30_000,
  });
}

/**
 * POST /api/batches/{batchId}/send-to-feedlot/
 *
 * Отправляет суточных цыплят (chick_batch) из инкубации в откорм.
 * Создаёт InterModuleTransfer incubation→feedlot и сразу его проводит.
 */
export function useSendChicksToFeedlot() {
  const qc = useQueryClient();
  return useMutation<unknown, ApiError, { batchId: string }>({
    mutationFn: ({ batchId }) =>
      apiFetch(`/api/batches/${batchId}/send-to-feedlot/`, { method: 'POST' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['incubation'] });
      qc.invalidateQueries({ queryKey: ['batches'] });
    },
  });
}

/**
 * Дочерняя партия цыплят, рождённая из egg-batch этого run-а.
 * Используется для перевода цыплят в откорм после hatch.
 */
export function useChickBatchForRun(run: IncubationRun | null | undefined) {
  const eggBatchId = run?.batch ?? null;
  return useQuery<Batch | null, ApiError>({
    queryKey: ['incubation', 'chick-batch', eggBatchId],
    enabled: Boolean(eggBatchId) && run?.status === 'transferred',
    queryFn: async () => {
      const data = await apiFetch<Paginated<Batch> | Batch[]>(
        `/api/batches/?parent_batch=${eggBatchId}&page_size=10`,
      );
      const list = asList(data);
      return list.length > 0 ? list[0] : null;
    },
    staleTime: 30_000,
  });
}
