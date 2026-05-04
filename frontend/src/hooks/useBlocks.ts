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

export function useProductionBlocks(filter: BlocksFilter = {}) {
  const params = new URLSearchParams();
  if (filter.module) params.set('module', filter.module);
  if (filter.module_code) params.set('module_code', filter.module_code);
  if (filter.kind) params.set('kind', filter.kind);
  if (filter.is_active) params.set('is_active', filter.is_active);
  if (filter.search) params.set('search', filter.search);
  params.set('ordering', 'code');
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
