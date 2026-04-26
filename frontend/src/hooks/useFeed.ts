'use client';

import { makeCrud } from '@/lib/crudFactory';
import type {
  FeedBatch,
  ProductionTask,
  RawMaterialBatch,
  Recipe,
  RecipeComponent,
  RecipeVersion,
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
