'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import { asList } from '@/lib/paginated';
import type { Paginated, StockMovement, StockMovementKind, WarehouseRef } from '@/types/auth';

export interface MovementsFilter {
  kind?: string;
  /**
   * Единый «склад» — ищет движения где склад в warehouse_from ИЛИ
   * warehouse_to (бэкенд-фильтр с Q-OR). Раньше использовали отдельные
   * warehouse_from/warehouse_to, и фильтр пропускал INCOMING-движения
   * (например, расфасовка корма приходовала в SKLD-MESH, а юзер фильтровал
   * по этому складу и не видел приход).
   */
  warehouse?: string;
  warehouse_from?: string;
  warehouse_to?: string;
  nomenclature?: string;
  module_code?: string;
  batch_doc?: string;
  date_after?: string;
  date_before?: string;
  search?: string;
  limit?: number;
}

function buildMovementParams(filter: MovementsFilter): URLSearchParams {
  const params = new URLSearchParams();
  if (filter.kind) params.set('kind', filter.kind);
  if (filter.warehouse) params.set('warehouse', filter.warehouse);
  if (filter.warehouse_from) params.set('warehouse_from', filter.warehouse_from);
  if (filter.warehouse_to) params.set('warehouse_to', filter.warehouse_to);
  if (filter.nomenclature) params.set('nomenclature', filter.nomenclature);
  if (filter.module_code) params.set('module_code', filter.module_code);
  if (filter.batch_doc) params.set('batch_doc', filter.batch_doc);
  if (filter.date_after) params.set('date_after', filter.date_after);
  if (filter.date_before) params.set('date_before', filter.date_before);
  if (filter.search) params.set('search', filter.search);
  return params;
}

export function useStockMovements(filter: MovementsFilter) {
  const params = buildMovementParams(filter);
  params.set('ordering', '-date');
  params.set('page_size', '2000');
  const qs = params.toString();

  return useQuery<StockMovement[], ApiError>({
    queryKey: ['stock-movements', qs],
    queryFn: async () => {
      const data = await apiFetch<Paginated<StockMovement> | StockMovement[]>(
        `/api/warehouses/movements/?${qs}`,
      );
      const rows = asList(data);
      return filter.limit ? rows.slice(0, filter.limit) : rows;
    },
    staleTime: 15_000,
  });
}

export function useStockMovementsPaginated(
  filter: MovementsFilter,
  page = 1,
  pageSize = 25,
) {
  const params = buildMovementParams(filter);
  params.set('ordering', '-date');
  params.set('page', String(page));
  params.set('page_size', String(pageSize));
  const qs = params.toString();
  return useQuery<Paginated<StockMovement>, ApiError>({
    queryKey: ['stock-movements', 'page', qs],
    queryFn: () => apiFetch<Paginated<StockMovement>>(
      `/api/warehouses/movements/?${qs}`,
    ),
    staleTime: 15_000,
    placeholderData: (prev) => prev,
  });
}

export interface StockMovementsStats {
  total_count: number;
  total_amount_uzs: string;
  by_kind: {
    incoming: { count: number; amount_uzs: string };
    outgoing: { count: number; amount_uzs: string };
    transfer: { count: number; amount_uzs: string };
    write_off: { count: number; amount_uzs: string };
  };
}

export function useStockMovementsStats(filter: MovementsFilter) {
  const params = buildMovementParams(filter);
  const qs = params.toString();
  return useQuery<StockMovementsStats, ApiError>({
    queryKey: ['stock-movements', 'stats', qs],
    queryFn: () => apiFetch<StockMovementsStats>(
      `/api/warehouses/movements/stats/?${qs}`,
    ),
    staleTime: 15_000,
  });
}

/**
 * Список складов. Опционально фильтрует по коду модуля
 * (например `useWarehouses({ module_code: 'feedlot' })` вернёт только склады
 * модуля «Откорм»).
 */
export function useWarehouses(filter: { module_code?: string; is_active?: string } = {}) {
  const params = new URLSearchParams();
  // По умолчанию (если is_active не передан) — только активные.
  // Передайте is_active: '' чтобы получить все склады, включая отключённые.
  if (filter.is_active === undefined) {
    params.set('is_active', 'true');
  } else if (filter.is_active !== '') {
    params.set('is_active', filter.is_active);
  }
  if (filter.module_code) params.set('module_code', filter.module_code);
  const qs = params.toString();
  return useQuery<WarehouseRef[], ApiError>({
    queryKey: ['warehouses', qs],
    queryFn: async () => {
      const data = await apiFetch<Paginated<WarehouseRef> | WarehouseRef[]>(
        `/api/warehouses/warehouses/?${qs}`,
      );
      return asList(data);
    },
    staleTime: 5 * 60_000,
  });
}

// ─── Warehouse mutations ─────────────────────────────────────────────────

export type WarehousePayload = {
  code: string;
  name: string;
  module: string;
  production_block?: string | null;
  default_gl_subaccount?: string | null;
  is_active?: boolean;
};

export function useCreateWarehouse() {
  const qc = useQueryClient();
  return useMutation<WarehouseRef, ApiError, WarehousePayload>({
    mutationFn: (body) =>
      apiFetch<WarehouseRef>('/api/warehouses/warehouses/', { method: 'POST', body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['warehouses'] });
    },
  });
}

export function useUpdateWarehouse() {
  const qc = useQueryClient();
  return useMutation<WarehouseRef, ApiError, { id: string; patch: Partial<WarehousePayload> }>({
    mutationFn: ({ id, patch }) =>
      apiFetch<WarehouseRef>(`/api/warehouses/warehouses/${id}/`, {
        method: 'PATCH',
        body: patch,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['warehouses'] });
    },
  });
}

export interface WarehouseBalanceLot {
  id: string;
  doc_number: string;
  lot_number: string;
  current_quantity: string;
  expiration_date: string | null;
  status: string;
}

export interface WarehouseBalanceRow {
  nomenclature_id: string;
  sku: string;
  name: string;
  unit: string;
  incoming_qty: string;
  incoming_amount_uzs: string;
  outgoing_qty: string;
  outgoing_amount_uzs: string;
  balance_qty: string;
  /** Только для vet-складов: активные лоты этого SKU на этом складе. */
  lots?: WarehouseBalanceLot[];
}

export interface WarehouseBalanceResponse {
  warehouse: {
    id: string;
    code: string;
    name: string;
    module_code: string | null;
  };
  rows: WarehouseBalanceRow[];
  summary: {
    sku_count: number;
    with_balance: number;
  };
}

export function useWarehouseBalance(warehouseId: string | null | undefined) {
  return useQuery<WarehouseBalanceResponse, ApiError>({
    queryKey: ['warehouses', 'balance', warehouseId ?? ''],
    enabled: Boolean(warehouseId),
    queryFn: () => apiFetch<WarehouseBalanceResponse>(
      `/api/warehouses/warehouses/${warehouseId}/balance/`,
    ),
    staleTime: 30_000,
  });
}

export function useDeleteWarehouse() {
  const qc = useQueryClient();
  return useMutation<void, ApiError, string>({
    mutationFn: (id) =>
      apiFetch<void>(`/api/warehouses/warehouses/${id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['warehouses'] });
    },
  });
}

// ─── Manual StockMovement mutations ──────────────────────────────────────

export type ManualMovementPayload = {
  module: string;
  kind: StockMovementKind;
  date?: string;
  nomenclature: string;
  quantity: string;
  unit_price_uzs: string;
  warehouse_from?: string | null;
  warehouse_to?: string | null;
  counterparty?: string | null;
  batch?: string | null;
};

export function useCreateManualMovement() {
  const qc = useQueryClient();
  return useMutation<StockMovement, ApiError, ManualMovementPayload>({
    mutationFn: (body) =>
      apiFetch<StockMovement>('/api/warehouses/movements/manual/', {
        method: 'POST',
        body,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['stock-movements'] });
    },
  });
}

/**
 * Частичный PATCH manual-движения. Разрешены только метаданные
 * (date / counterparty / batch) — суммы и склады иммутабельны.
 * Передайте `null` чтобы очистить FK.
 */
export type ManualMovementPatch = {
  date?: string;
  counterparty?: string | null;
  batch?: string | null;
};

/**
 * Превратить ручной INCOMING-movement в RawMaterialBatch (модуль «Корма»).
 * Существующее движение перепривязывается к новой партии — без дублей.
 */
export type PromoteToRawBatchPayload = {
  moisture_pct_actual?: string | null;
  dockage_pct_actual?: string | null;
  shrinkage_pct?: string | null;
  quarantine_until?: string | null; // YYYY-MM-DD
  supplier?: string | null;
  storage_bin?: string;
  notes?: string;
};

export function usePromoteToRawBatch() {
  const qc = useQueryClient();
  return useMutation<
    { movement: StockMovement; raw_batch: { id: string; doc_number: string; status: string; quantity: string } },
    ApiError,
    { id: string; body: PromoteToRawBatchPayload }
  >({
    mutationFn: ({ id, body }) =>
      apiFetch(`/api/warehouses/movements/${id}/promote-to-raw-batch/`, {
        method: 'POST',
        body,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['stock-movements'] });
      qc.invalidateQueries({ queryKey: ['feed', 'raw-batches'] });
    },
  });
}

export function useUpdateManualMovement() {
  const qc = useQueryClient();
  return useMutation<
    StockMovement, ApiError,
    { id: string; patch: ManualMovementPatch }
  >({
    mutationFn: ({ id, patch }) =>
      apiFetch<StockMovement>(`/api/warehouses/movements/${id}/manual/`, {
        method: 'PATCH',
        body: patch,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['stock-movements'] });
    },
  });
}

export function useDeleteManualMovement() {
  const qc = useQueryClient();
  return useMutation<void, ApiError, string>({
    mutationFn: (id) =>
      apiFetch<void>(`/api/warehouses/movements/${id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['stock-movements'] });
    },
  });
}
