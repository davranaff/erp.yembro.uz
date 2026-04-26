'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import { asList } from '@/lib/paginated';
import type { MembershipRow, Paginated } from '@/types/auth';

const KEY = ['memberships'] as const;

export interface PeopleFilter {
  is_active?: string;
  work_status?: string;
  search?: string;
}

export function usePeople(filter: PeopleFilter = {}) {
  const params = new URLSearchParams();
  if (filter.is_active) params.set('is_active', filter.is_active);
  if (filter.work_status) params.set('work_status', filter.work_status);
  if (filter.search) params.set('search', filter.search);
  params.set('ordering', 'user__full_name');
  const qs = params.toString();

  return useQuery<MembershipRow[], ApiError>({
    queryKey: [...KEY, qs],
    queryFn: async () => {
      const data = await apiFetch<Paginated<MembershipRow> | MembershipRow[]>(
        `/api/memberships/?${qs}`,
      );
      return asList(data);
    },
    staleTime: 30_000,
  });
}

export type CreatePersonVars = {
  email: string;
  full_name: string;
  phone?: string;
  password?: string;
  position_title?: string;
  work_phone?: string;
  work_status?: string;
};

export function useCreatePerson() {
  const qc = useQueryClient();
  return useMutation<MembershipRow, ApiError, CreatePersonVars>({
    mutationFn: (body) =>
      apiFetch<MembershipRow>('/api/memberships/', { method: 'POST', body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEY });
    },
  });
}

export type UpdatePersonVars = {
  id: string;
  patch: {
    position_title?: string;
    work_phone?: string;
    work_status?: string;
    is_active?: boolean;
  };
};

export function useUpdatePerson() {
  const qc = useQueryClient();
  return useMutation<MembershipRow, ApiError, UpdatePersonVars>({
    mutationFn: ({ id, patch }) =>
      apiFetch<MembershipRow>(`/api/memberships/${id}/`, { method: 'PATCH', body: patch }),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useDeactivatePerson() {
  const qc = useQueryClient();
  return useMutation<MembershipRow, ApiError, string>({
    mutationFn: (id) =>
      apiFetch<MembershipRow>(`/api/memberships/${id}/`, {
        method: 'PATCH',
        body: { is_active: false, work_status: 'terminated' },
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}
