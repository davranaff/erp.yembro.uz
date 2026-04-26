'use client';

import { useQuery } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import { asList } from '@/lib/paginated';
import type { ModuleRef, Paginated } from '@/types/auth';

export function useModules() {
  return useQuery<ModuleRef[], ApiError>({
    queryKey: ['modules'],
    queryFn: async () => {
      const data = await apiFetch<Paginated<ModuleRef> | ModuleRef[]>(
        '/api/modules/',
        { skipOrg: true },
      );
      return asList(data);
    },
    staleTime: 10 * 60_000,
  });
}
