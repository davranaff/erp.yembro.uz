'use client';

import { useQuery } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import { getAccessToken } from '@/lib/tokens';
import { Organization, Paginated } from '@/types/auth';

export const ORGANIZATIONS_QUERY_KEY = ['organizations'] as const;

/**
 * GET /api/organizations/ — список организаций, в которых юзер активный member.
 */
export function useOrganizations() {
  return useQuery<Organization[], ApiError>({
    queryKey: ORGANIZATIONS_QUERY_KEY,
    queryFn: async () => {
      const data = await apiFetch<Paginated<Organization> | Organization[]>(
        '/api/organizations/',
        { skipOrg: true },
      );
      return Array.isArray(data) ? data : data.results;
    },
    enabled: typeof window !== 'undefined' && !!getAccessToken(),
    staleTime: 5 * 60_000,
  });
}
