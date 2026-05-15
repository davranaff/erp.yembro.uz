'use client';

import { useQuery } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import type {
  CashflowPayload,
  DashboardArSummary,
  DashboardSummary,
  ModuleKpiPayload,
} from '@/types/auth';

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

export function useModuleKpi(moduleCode: string, from: string, to: string) {
  return useQuery<ModuleKpiPayload, ApiError>({
    queryKey: ['dashboard', 'module', moduleCode, from, to],
    queryFn: () =>
      apiFetch<ModuleKpiPayload>(
        `/api/dashboard/module/${moduleCode}/?from=${from}&to=${to}`,
      ),
    staleTime: 30_000,
  });
}

/** Standalone AR snapshot (для /reports). На /dashboard ar уже в summary. */
export function useDashboardArSummary(dsoWindow = 90) {
  return useQuery<DashboardArSummary, ApiError>({
    queryKey: ['dashboard', 'ar-summary', dsoWindow],
    queryFn: () => apiFetch<DashboardArSummary>(
      `/api/dashboard/ar-summary/?dso_window=${dsoWindow}`,
    ),
    staleTime: 30_000,
  });
}
