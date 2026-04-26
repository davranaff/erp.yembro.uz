'use client';

import { useQuery } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import type { HoldingPayload } from '@/types/auth';

export interface HoldingFilter {
  period_from?: string;
  period_to?: string;
}

export function useHolding(filter: HoldingFilter = {}) {
  const params = new URLSearchParams();
  if (filter.period_from) params.set('period_from', filter.period_from);
  if (filter.period_to) params.set('period_to', filter.period_to);
  const qs = params.toString();

  return useQuery<HoldingPayload, ApiError>({
    queryKey: ['holding-companies', qs],
    queryFn: () =>
      apiFetch<HoldingPayload>(`/api/holding/companies/${qs ? `?${qs}` : ''}`, {
        skipOrg: true,
      }),
    staleTime: 60_000,
  });
}
