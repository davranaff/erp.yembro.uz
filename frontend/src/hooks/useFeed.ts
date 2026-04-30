'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import { makeCrud } from '@/lib/crudFactory';
import type {
  FeedBatch,
  FeedLotShrinkageState,
  FeedShrinkageProfile,
  FeedShrinkageProfileInput,
  ProductionTask,
  RawMaterialBatch,
  Recipe,
  RecipeComponent,
  RecipeVersion,
  ShrinkageApplyResult,
  ShrinkageApplySummary,
  ShrinkageHistory,
  ShrinkageReportResponse,
} from '@/types/auth';

export const recipesCrud = makeCrud<Recipe>({
  key: ['feed', 'recipes'],
  path: '/api/feed/recipes/',
  ordering: 'code',
});

export const recipeVersionsCrud = makeCrud<RecipeVersion>({
  key: ['feed', 'recipe-versions'],
  path: '/api/feed/recipe-versions/',
  ordering: '-version_number',
});

export const recipeComponentsCrud = makeCrud<RecipeComponent>({
  key: ['feed', 'recipe-components'],
  path: '/api/feed/recipe-components/',
});

export const tasksCrud = makeCrud<ProductionTask>({
  key: ['feed', 'production-tasks'],
  path: '/api/feed/production-tasks/',
  ordering: '-scheduled_at',
});

export const useExecuteTask = tasksCrud.makeAction<
  {
    output_warehouse: string;
    storage_bin: string;
    actual_quantity_kg: string;
  },
  unknown
>((id) => `/api/feed/production-tasks/${id}/execute/`);

export const useCancelTask = tasksCrud.makeAction<
  { reason?: string },
  unknown
>((id) => `/api/feed/production-tasks/${id}/cancel/`);

export const feedBatchesCrud = makeCrud<FeedBatch>({
  key: ['feed', 'batches'],
  path: '/api/feed/feed-batches/',
  ordering: '-produced_at',
});

export const useApprovePassport = feedBatchesCrud.makeAction<void, FeedBatch>(
  (id) => `/api/feed/feed-batches/${id}/approve_passport/`,
);

export const useRejectPassport = feedBatchesCrud.makeAction<{ reason: string }, FeedBatch>(
  (id) => `/api/feed/feed-batches/${id}/reject_passport/`,
);

// ─── Raw materials ─────────────────────────────────────────────────────

/**
 * Тело POST на /api/feed/raw-batches/.
 *
 * Сценарии:
 *   1. gross_weight_kg + moisture_pct_actual → бэк рассчитает settlement_weight_kg
 *      и shrinkage_pct по формуле Дюваля (взяв базисную влажность из nomenclature).
 *   2. gross_weight_kg + shrinkage_pct (прямой ввод %) — settlement = gross × (1−sh/100).
 *   3. Только quantity — legacy режим без расчётов.
 */
export interface RawMaterialBatchInput {
  module?: string;
  nomenclature: string;
  supplier?: string | null;
  warehouse: string;
  storage_bin?: string;
  received_date: string;
  unit: string;
  price_per_unit_uzs: string;
  // Сценарии 1–2:
  gross_weight_kg?: string;
  moisture_pct_actual?: string;
  dockage_pct_actual?: string;
  shrinkage_pct?: string;
  // Сценарий 3 (legacy):
  quantity?: string;
  // Карантин
  status?: 'quarantine' | 'available';
  quarantine_until?: string | null;
  notes?: string;
}

export const rawBatchesCrud = makeCrud<
  RawMaterialBatch,
  RawMaterialBatchInput,
  Partial<RawMaterialBatchInput>
>({
  key: ['feed', 'raw-batches'],
  path: '/api/feed/raw-batches/',
  ordering: '-received_date',
});

export const useReleaseQuarantine = rawBatchesCrud.makeAction<void, RawMaterialBatch>(
  (id) => `/api/feed/raw-batches/${id}/release_quarantine/`,
);

export const useRejectQuarantine = rawBatchesCrud.makeAction<
  { reason: string },
  RawMaterialBatch
>((id) => `/api/feed/raw-batches/${id}/reject_quarantine/`);


// ─── Shrinkage profiles ────────────────────────────────────────────────

export const shrinkageProfilesCrud = makeCrud<
  FeedShrinkageProfile,
  FeedShrinkageProfileInput,
  Partial<FeedShrinkageProfileInput>
>({
  key: ['feed', 'shrinkage-profiles'],
  path: '/api/feed/shrinkage-profiles/',
  ordering: 'target_type',
});

// ─── Shrinkage state ───────────────────────────────────────────────────

export const shrinkageStatesCrud = makeCrud<FeedLotShrinkageState>({
  key: ['feed', 'shrinkage-states'],
  path: '/api/feed/shrinkage-state/',
  ordering: '-updated_at',
});

/**
 * Прогон алгоритма усушки. Без аргументов — по всей организации (батч).
 * С `lot_type`+`lot_id` — точечно на одну партию (например после правки профиля).
 * С `on_date` — на конкретную дату (для catch-up при простое воркера).
 */
export function useApplyShrinkage() {
  const qc = useQueryClient();
  return useMutation<
    ShrinkageApplySummary | ShrinkageApplyResult,
    ApiError,
    { on_date?: string; lot_type?: string; lot_id?: string } | undefined
  >({
    mutationFn: (body) =>
      apiFetch('/api/feed/shrinkage-state/apply/', {
        method: 'POST',
        body: body ?? {},
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['feed', 'shrinkage-states'] });
      qc.invalidateQueries({ queryKey: ['feed', 'raw-batches'] });
      qc.invalidateQueries({ queryKey: ['feed', 'batches'] });
    },
  });
}

/**
 * Админский откат: удаляет все StockMovement(kind=shrinkage) этой партии,
 * восстанавливает current_quantity, сбрасывает state.
 */
export function useResetShrinkage() {
  const qc = useQueryClient();
  return useMutation<
    { ok: boolean; reverted_movements: number; restored_kg: string },
    ApiError,
    { id: string }
  >({
    mutationFn: ({ id }) =>
      apiFetch(`/api/feed/shrinkage-state/${id}/reset/`, {
        method: 'POST',
        body: {},
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['feed', 'shrinkage-states'] });
      qc.invalidateQueries({ queryKey: ['feed', 'raw-batches'] });
      qc.invalidateQueries({ queryKey: ['feed', 'batches'] });
    },
  });
}

// ─── Shrinkage report ──────────────────────────────────────────────────

export interface ShrinkageReportFilter {
  date_from?: string;
  date_to?: string;
  group_by?: 'ingredient' | 'warehouse';
}

export function useShrinkageReport(filter: ShrinkageReportFilter = {}) {
  const params = new URLSearchParams();
  if (filter.date_from) params.set('date_from', filter.date_from);
  if (filter.date_to) params.set('date_to', filter.date_to);
  if (filter.group_by) params.set('group_by', filter.group_by);
  const qs = params.toString();

  return useQuery<ShrinkageReportResponse, ApiError>({
    queryKey: ['feed', 'shrinkage-report', qs],
    queryFn: () =>
      apiFetch<ShrinkageReportResponse>(
        `/api/feed/shrinkage-report/${qs ? '?' + qs : ''}`,
      ),
    staleTime: 30_000,
  });
}

/** История списаний усушки по конкретной партии (для sparkline). */
export function useShrinkageHistory(stateId: string | null | undefined) {
  return useQuery<ShrinkageHistory, ApiError>({
    queryKey: ['feed', 'shrinkage-history', stateId ?? ''],
    queryFn: () =>
      apiFetch<ShrinkageHistory>(
        `/api/feed/shrinkage-state/${stateId}/history/`,
      ),
    enabled: Boolean(stateId),
    staleTime: 30_000,
  });
}
