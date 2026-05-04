'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';
import type { Organization } from '@/types/auth';

export function useOrganizationDetails() {
  const { org } = useAuth();
  return useQuery<Organization, ApiError>({
    queryKey: ['organization', org?.code],
    queryFn: () =>
      apiFetch<Organization>(`/api/organizations/${org!.code}/`, { skipOrg: true }),
    enabled: !!org?.code,
    staleTime: 60_000,
  });
}

export function useUpdateOrganization() {
  const { org } = useAuth();
  const qc = useQueryClient();

  return useMutation<Organization, ApiError, Partial<Organization>>({
    mutationFn: (patch) =>
      apiFetch<Organization>(`/api/organizations/${org!.code}/`, {
        method: 'PATCH',
        body: patch,
        skipOrg: true,
      }),
    onSuccess: (data) => {
      qc.setQueryData(['organization', org?.code], data);
      qc.invalidateQueries({ queryKey: ['me'] });
    },
  });
}
