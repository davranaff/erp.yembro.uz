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
  include_compensation?: boolean;
  include_balance?: boolean;
}

function appendFilter(params: URLSearchParams, filter: PeopleFilter) {
  if (filter.is_active) params.set('is_active', filter.is_active);
  if (filter.work_status) params.set('work_status', filter.work_status);
  if (filter.search) params.set('search', filter.search);
  if (filter.include_compensation) params.set('include_compensation', '1');
  if (filter.include_balance) params.set('include_balance', '1');
}

export function usePeople(filter: PeopleFilter = {}) {
  const params = new URLSearchParams();
  appendFilter(params, filter);
  params.set('ordering', 'user__full_name');
  params.set('page_size', '2000');
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

export function usePeoplePaginated(
  filter: PeopleFilter = {},
  page = 1,
  pageSize = 50,
) {
  const params = new URLSearchParams();
  appendFilter(params, filter);
  params.set('ordering', 'user__full_name');
  params.set('page', String(page));
  params.set('page_size', String(pageSize));
  const qs = params.toString();
  return useQuery<Paginated<MembershipRow>, ApiError>({
    queryKey: [...KEY, 'page', qs],
    queryFn: () => apiFetch<Paginated<MembershipRow>>(`/api/memberships/?${qs}`),
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  });
}

export function usePerson(id: string | null | undefined) {
  return useQuery<MembershipRow, ApiError>({
    queryKey: [...KEY, 'one', id],
    enabled: Boolean(id),
    queryFn: () =>
      apiFetch<MembershipRow>(
        `/api/memberships/${id}/?include_compensation=1&include_balance=1`,
      ),
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

export interface TerminateResult {
  membership_id: string;
  terminated_on: string;
  balance_at_termination: string;
  balance_breakdown: { accrued_total: string; paid_total: string };
}

export function useTerminatePerson() {
  const qc = useQueryClient();
  return useMutation<TerminateResult, ApiError, { id: string; date?: string }>({
    mutationFn: ({ id, date }) =>
      apiFetch<TerminateResult>(`/api/memberships/${id}/terminate/`, {
        method: 'POST',
        body: date ? { date } : {},
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEY });
      qc.invalidateQueries({ queryKey: ['payroll'] });
    },
  });
}
