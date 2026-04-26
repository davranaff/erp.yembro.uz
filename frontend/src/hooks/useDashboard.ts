'use client';

import { useQuery } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import type { CashflowPayload, DashboardSummary } from '@/types/auth';

export function useDashboardSummary() {
  return useQuery<DashboardSummary, ApiError>({
    queryKey: ['dashboard', 'summary'],
    queryFn: () => apiFetch<DashboardSummary>('/api/dashboard/summary/'),
    staleTime: 30_000,
  });
}

export function useDashboardCashflow(days = 30) {
  return useQuery<CashflowPayload, ApiError>({
    queryKey: ['dashboard', 'cashflow', days],
    queryFn: () => apiFetch<CashflowPayload>(`/api/dashboard/cashflow/?days=${days}`),
    staleTime: 30_000,
  });
}
