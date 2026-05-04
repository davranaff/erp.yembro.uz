'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import { makeCrud } from '@/lib/crudFactory';
import type {
  DailyWeighing,
  FeedlotBatch,
  FeedlotFeedConsumption,
  FeedlotMortality,
  FeedlotStats,
  FeedlotTimelineEvent,
} from '@/types/auth';

export const feedlotCrud = makeCrud<FeedlotBatch>({
  key: ['feedlot', 'batches'],
  path: '/api/feedlot/batches/',
  ordering: '-placed_date',
});

export const weighingsCrud = makeCrud<DailyWeighing>({
  key: ['feedlot', 'weighings'],
  path: '/api/feedlot/weighings/',
  ordering: 'day_of_age',
});

export const feedlotMortalityCrud = makeCrud<FeedlotMortality>({
  key: ['feedlot', 'mortality'],
  path: '/api/feedlot/mortality/',
  ordering: '-date',
});

// POST /api/feedlot/batches/place/ (detail=False)
export function usePlaceFeedlotBatch() {
  const qc = useQueryClient();
  return useMutation<FeedlotBatch, ApiError, {
    batch: string;
    house_block: string;
    placed_date: string;
    technologist: string;
    initial_heads?: number;
    target_weight_kg?: string;
    target_slaughter_date?: string;
    doc_number?: string;
    notes?: string;
  }>({
    mutationFn: (body) =>
      apiFetch<FeedlotBatch>('/api/feedlot/batches/place/', {
        method: 'POST',
        body,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['feedlot', 'batches'] }),
  });
}

export const useShipFeedlot = feedlotCrud.makeAction<
  {
    slaughter_line: string;
    slaughter_warehouse: string;
    source_warehouse: string;
    quantity?: string;
  },
  unknown
>((id) => `/api/feedlot/batches/${id}/ship/`);

export const useApplyMortality = feedlotCrud.makeAction<
  {
    date: string;
    day_of_age: number;
    dead_count: number;
    cause?: string;
    notes?: string;
  },
  unknown
>((id) => `/api/feedlot/batches/${id}/mortality/`);

// ── Кормление ──────────────────────────────────────────────────────────

export const feedConsumptionCrud = makeCrud<FeedlotFeedConsumption>({
  key: ['feedlot', 'feed-consumption'],
  path: '/api/feedlot/feed-consumption/',
  ordering: 'period_from_day',
});

export const usePostFeedConsumption = feedlotCrud.makeAction<
  {
    feed_batch: string;
    total_kg: string;
    period_from_day: number;
    period_to_day: number;
    feed_type: 'start' | 'growth' | 'finish';
    notes?: string;
  },
  unknown
>((id) => `/api/feedlot/batches/${id}/feed_consumption/`);

// ── Взвешивания ────────────────────────────────────────────────────────

export const useRecordWeighing = feedlotCrud.makeAction<
  {
    date: string;
    day_of_age: number;
    sample_size: number;
    avg_weight_kg: string;
    notes?: string;
  },
  unknown
>((id) => `/api/feedlot/batches/${id}/weighing/`);

// ── KPI Stats / Timeline ───────────────────────────────────────────────

export function useFeedlotStats(batchId: string | null | undefined) {
  return useQuery<FeedlotStats, ApiError>({
    queryKey: ['feedlot', 'stats', batchId],
    enabled: Boolean(batchId),
    queryFn: () => apiFetch<FeedlotStats>(`/api/feedlot/batches/${batchId}/stats/`),
    staleTime: 30_000,
  });
}

interface TimelineResponse {
  batch_id: string;
  events: FeedlotTimelineEvent[];
  counts: Record<string, number>;
}

export function useFeedlotTimeline(batchId: string | null | undefined) {
  return useQuery<TimelineResponse, ApiError>({
    queryKey: ['feedlot', 'timeline', batchId],
    enabled: Boolean(batchId),
    queryFn: () => apiFetch<TimelineResponse>(`/api/feedlot/batches/${batchId}/timeline/`),
    staleTime: 30_000,
  });
}
