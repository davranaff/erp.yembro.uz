'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import { asList } from '@/lib/paginated';
import type { OrganizationModuleRow, Paginated } from '@/types/auth';

const QK = ['organization-modules'] as const;

export function useOrganizationModules() {
  return useQuery<OrganizationModuleRow[], ApiError>({
    queryKey: QK,
    queryFn: async () => {
      const data = await apiFetch<Paginated<OrganizationModuleRow> | OrganizationModuleRow[]>(
        '/api/organization-modules/',
      );
      return asList(data).sort((a, b) => a.module_code.localeCompare(b.module_code));
    },
    staleTime: 60_000,
  });
}

interface ToggleVars {
  id: string;
  is_enabled: boolean;
}

export function useToggleOrganizationModule() {
  const qc = useQueryClient();
  return useMutation<OrganizationModuleRow, ApiError, ToggleVars>({
    mutationFn: ({ id, is_enabled }) =>
      apiFetch<OrganizationModuleRow>(`/api/organization-modules/${id}/`, {
        method: 'PATCH',
        body: { is_enabled },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: QK });
      qc.invalidateQueries({ queryKey: ['me'] });
    },
  });
}
