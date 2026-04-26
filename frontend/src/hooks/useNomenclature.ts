'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import { asList } from '@/lib/paginated';
import type { Category, NomenclatureItem, Paginated, Unit } from '@/types/auth';

// ─── Units ────────────────────────────────────────────────────────────────

const UNITS_KEY = ['nomenclature', 'units'] as const;

export function useUnits() {
  return useQuery<Unit[], ApiError>({
    queryKey: UNITS_KEY,
    queryFn: async () => {
      const data = await apiFetch<Paginated<Unit> | Unit[]>(
        '/api/nomenclature/units/?ordering=code',
      );
      return asList(data);
    },
    staleTime: 5 * 60_000,
  });
}

export function useCreateUnit() {
  const qc = useQueryClient();
  return useMutation<Unit, ApiError, { code: string; name: string }>({
    mutationFn: (body) =>
      apiFetch<Unit>('/api/nomenclature/units/', { method: 'POST', body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: UNITS_KEY }),
  });
}

// ─── Categories ───────────────────────────────────────────────────────────

const CATS_KEY = ['nomenclature', 'categories'] as const;

export function useCategories(filter: { module_code?: string } = {}) {
  const params = new URLSearchParams();
  params.set('ordering', 'name');
  if (filter.module_code) params.set('module_code', filter.module_code);
  const qs = params.toString();
  return useQuery<Category[], ApiError>({
    queryKey: [...CATS_KEY, qs],
    queryFn: async () => {
      const data = await apiFetch<Paginated<Category> | Category[]>(
        `/api/nomenclature/categories/?${qs}`,
      );
      return asList(data);
    },
    staleTime: 5 * 60_000,
  });
}

type CategoryInput = {
  name: string;
  parent?: string | null;
  module?: string | null;
  default_gl_subaccount?: string | null;
};

export function useCreateCategory() {
  const qc = useQueryClient();
  return useMutation<Category, ApiError, CategoryInput>({
    mutationFn: (body) =>
      apiFetch<Category>('/api/nomenclature/categories/', { method: 'POST', body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: CATS_KEY }),
  });
}

// ─── Items ────────────────────────────────────────────────────────────────

const ITEMS_KEY = ['nomenclature', 'items'] as const;

export interface NomenclatureFilter {
  category?: string;
  /** Скоупит по category.module — например `module_code: 'feedlot'` */
  module_code?: string;
  is_active?: string;
  search?: string;
}

export function useNomenclatureItems(filter: NomenclatureFilter = {}) {
  const params = new URLSearchParams();
  if (filter.category) params.set('category', filter.category);
  if (filter.module_code) params.set('module_code', filter.module_code);
  if (filter.is_active) params.set('is_active', filter.is_active);
  if (filter.search) params.set('search', filter.search);
  params.set('ordering', 'sku');
  const qs = params.toString();

  return useQuery<NomenclatureItem[], ApiError>({
    queryKey: [...ITEMS_KEY, qs],
    queryFn: async () => {
      const data = await apiFetch<Paginated<NomenclatureItem> | NomenclatureItem[]>(
        `/api/nomenclature/items/?${qs}`,
      );
      return asList(data);
    },
    staleTime: 30_000,
  });
}

type ItemInput = {
  sku: string;
  name: string;
  category: string;
  unit: string;
  barcode?: string;
  is_active?: boolean;
  notes?: string;
  default_gl_subaccount?: string | null;
};

export function useCreateItem() {
  const qc = useQueryClient();
  return useMutation<NomenclatureItem, ApiError, ItemInput>({
    mutationFn: (body) =>
      apiFetch<NomenclatureItem>('/api/nomenclature/items/', { method: 'POST', body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ITEMS_KEY }),
  });
}

export function useUpdateItem() {
  const qc = useQueryClient();
  return useMutation<NomenclatureItem, ApiError, { id: string; patch: Partial<ItemInput> }>({
    mutationFn: ({ id, patch }) =>
      apiFetch<NomenclatureItem>(`/api/nomenclature/items/${id}/`, {
        method: 'PATCH',
        body: patch,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ITEMS_KEY }),
  });
}

export function useDeleteItem() {
  const qc = useQueryClient();
  return useMutation<void, ApiError, string>({
    mutationFn: (id) =>
      apiFetch<void>(`/api/nomenclature/items/${id}/`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ITEMS_KEY }),
  });
}
