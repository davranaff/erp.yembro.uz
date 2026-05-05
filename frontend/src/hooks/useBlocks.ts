'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import { asList } from '@/lib/paginated';
import type { Paginated, ProductionBlock } from '@/types/auth';

const KEY = ['production-blocks'] as const;

export interface BlocksFilter {
  module?: string;        // uuid модуля
  module_code?: string;   // код модуля (удобнее в формах)
  kind?: string;
  is_active?: string;
  search?: string;
}

function buildBlocksParams(filter: BlocksFilter): URLSearchParams {
  const params = new URLSearchParams();
  if (filter.module) params.set('module', filter.module);
  if (filter.module_code) params.set('module_code', filter.module_code);
  if (filter.kind) params.set('kind', filter.kind);
  if (filter.is_active) params.set('is_active', filter.is_active);
  if (filter.search) params.set('search', filter.search);
  return params;
}

export function useProductionBlocks(filter: BlocksFilter = {}) {
  const params = buildBlocksParams(filter);
  params.set('ordering', 'code');
  params.set('page_size', '2000');
  const qs = params.toString();

  return useQuery<ProductionBlock[], ApiError>({
    queryKey: [...KEY, qs],
    queryFn: async () => {
      const data = await apiFetch<Paginated<ProductionBlock> | ProductionBlock[]>(
        `/api/warehouses/blocks/?${qs}`,
      );
      return asList(data);
    },
    staleTime: 30_000,
  });
}

export function useProductionBlocksPaginated(
  filter: BlocksFilter = {},
  page = 1,
  pageSize = 50,
) {
  const params = buildBlocksParams(filter);
  params.set('ordering', 'code');
  params.set('page', String(page));
  params.set('page_size', String(pageSize));
  const qs = params.toString();
  return useQuery<Paginated<ProductionBlock>, ApiError>({
    queryKey: [...KEY, 'page', qs],
    queryFn: () => apiFetch<Paginated<ProductionBlock>>(
      `/api/warehouses/blocks/?${qs}`,
    ),
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  });
}

type BlockInput = {
  code: string;
  name: string;
  module: string;
  kind: string;
  area_m2?: string | null;
  capacity?: string | null;
  capacity_unit?: string | null;
  is_active?: boolean;
};

export function useCreateBlock() {
  const qc = useQueryClient();
  return useMutation<ProductionBlock, ApiError, BlockInput>({
    mutationFn: (body) =>
      apiFetch<ProductionBlock>('/api/warehouses/blocks/', { method: 'POST', body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useUpdateBlock() {
  const qc = useQueryClient();
  return useMutation<ProductionBlock, ApiError, { id: string; patch: Partial<BlockInput> }>({
    mutationFn: ({ id, patch }) =>
      apiFetch<ProductionBlock>(`/api/warehouses/blocks/${id}/`, {
        method: 'PATCH',
        body: patch,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useDeleteBlock() {
  const qc = useQueryClient();
  return useMutation<void, ApiError, string>({
    mutationFn: (id) =>
      apiFetch<void>(`/api/warehouses/blocks/${id}/`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}
