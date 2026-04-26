'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import { makeCrud } from '@/lib/crudFactory';
import { asList } from '@/lib/paginated';
import type {
  Batch,
  BreedingFeedConsumption,
  BreedingHerd,
  BreedingMortality,
  DailyEggProduction,
  Paginated,
} from '@/types/auth';

export const herdsCrud = makeCrud<BreedingHerd>({
  key: ['matochnik', 'herds'],
  path: '/api/matochnik/herds/',
  ordering: '-placed_at',
});

export const dailyEggCrud = makeCrud<DailyEggProduction>({
  key: ['matochnik', 'daily-egg'],
  path: '/api/matochnik/daily-egg/',
  ordering: '-date',
});

export const herdMortalityCrud = makeCrud<BreedingMortality>({
  key: ['matochnik', 'mortality'],
  path: '/api/matochnik/mortality/',
  ordering: '-date',
});

export const feedConsumptionCrud = makeCrud<BreedingFeedConsumption>({
  key: ['matochnik', 'feed-consumption'],
  path: '/api/matochnik/feed-consumption/',
  ordering: '-date',
});

// ─── Actions on herd ─────────────────────────────────────────────────────

export const useCrystallizeEggs = herdsCrud.makeAction<
  { egg_nomenclature: string; date_from: string; date_to: string; doc_number?: string },
  unknown
>((id) => `/api/matochnik/herds/${id}/crystallize-eggs/`);

export const useDepopulateHerd = herdsCrud.makeAction<
  { reduce_by: number; date?: string; reason?: string; mark_as_mortality?: boolean },
  unknown
>((id) => `/api/matochnik/herds/${id}/depopulate/`);

export const useMoveHerd = herdsCrud.makeAction<
  { block: string; reason?: string },
  unknown
>((id) => `/api/matochnik/herds/${id}/move/`);

/**
 * GET /api/matochnik/herds/{id}/egg-batches/
 * Все партии яиц, сформированные из яйцесбора этого стада.
 */
export function useHerdEggBatches(herdId: string | null | undefined) {
  return useQuery<Batch[], ApiError>({
    queryKey: ['matochnik', 'herds', herdId ?? '', 'egg-batches'],
    enabled: Boolean(herdId),
    queryFn: async () => {
      const data = await apiFetch<Paginated<Batch> | Batch[]>(
        `/api/matochnik/herds/${herdId}/egg-batches/`,
      );
      return asList(data);
    },
    staleTime: 15_000,
  });
}

export type HerdTimelineEventType =
  | 'egg' | 'mortality' | 'feed' | 'treatment' | 'crystallize' | 'move';

export interface HerdTimelineEvent {
  type: HerdTimelineEventType;
  date: string;
  id: string;
  title: string;
  subtitle: string;
  notes: string;
  amount?: number | string;
  amount_label?: string;
  cost_uzs?: string | null;
  drug_sku?: string | null;
  lot_number?: string | null;
  withdrawal_period_days?: number;
  indication?: string;
  batch_doc?: string;
  current_module?: string | null;
}

export interface HerdTimeline {
  days: number;
  from: string;
  to: string;
  events: HerdTimelineEvent[];
  counts: Record<HerdTimelineEventType, number>;
}

/**
 * GET /api/matochnik/herds/{id}/timeline/?days=N
 * Единый хронологический таймлайн всех событий стада.
 */
export function useHerdTimeline(
  herdId: string | null | undefined,
  days = 90,
  enabled = true,
) {
  return useQuery<HerdTimeline, ApiError>({
    queryKey: ['matochnik', 'herds', herdId ?? '', 'timeline', days],
    enabled: Boolean(herdId) && enabled,
    queryFn: () => apiFetch<HerdTimeline>(
      `/api/matochnik/herds/${herdId}/timeline/?days=${days}`,
    ),
    staleTime: 15_000,
  });
}

export interface HerdStatsSeriesPoint {
  date: string;
  eggs_clean: number;
  mortality: number;
  feed_kg: string;
}

export interface HerdStats {
  days: number;
  from: string;
  to: string;
  productivity_avg_pct: string;
  productivity_today_pct: string;
  eggs_total_clean: number;
  mortality_total: number;
  feed_total_kg: string;
  feed_cost_total_uzs: string;
  fcr: string | null;
  egg_weight_g: number;
  active_withdrawal_until: string | null;
  series: HerdStatsSeriesPoint[];
}

/**
 * GET /api/matochnik/herds/{id}/stats/?days=N
 * Сводные метрики стада за окно N дней (default 30).
 */
export function useHerdStats(herdId: string | null | undefined, days = 30) {
  return useQuery<HerdStats, ApiError>({
    queryKey: ['matochnik', 'herds', herdId ?? '', 'stats', days],
    enabled: Boolean(herdId),
    queryFn: () => apiFetch<HerdStats>(
      `/api/matochnik/herds/${herdId}/stats/?days=${days}`,
    ),
    staleTime: 30_000,
  });
}

/**
 * POST /api/batches/{id}/send-to-incubation/
 * Отправить партию яиц в инкубацию (создаёт transfer + accept).
 */
export function useSendToIncubation() {
  const qc = useQueryClient();
  return useMutation<Batch, ApiError, { id: string }>({
    mutationFn: ({ id }) =>
      apiFetch<Batch>(`/api/batches/${id}/send-to-incubation/`, {
        method: 'POST',
      }),
    onSuccess: () => {
      // Инвалидируем всё что касается партий и стад — после передачи
      // batch.current_module меняется, список egg-батчей тоже.
      qc.invalidateQueries({ queryKey: ['matochnik'] });
      qc.invalidateQueries({ queryKey: ['batches'] });
    },
  });
}
