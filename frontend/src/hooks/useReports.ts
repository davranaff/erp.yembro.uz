'use client';

import { useQuery } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';


// ─── Types ───────────────────────────────────────────────────


export interface TrialBalanceRow {
  subaccount_id: string;
  subaccount_code: string;
  subaccount_name: string;
  account_code: string;
  account_name: string;
  account_type: 'asset' | 'liability' | 'equity' | 'income' | 'expense' | 'service';
  module_code: string | null;
  opening_balance: string;
  debit_turnover: string;
  credit_turnover: string;
  closing_balance: string;
}

export interface TrialBalanceResponse {
  date_from: string;
  date_to: string;
  module_code: string | null;
  rows: TrialBalanceRow[];
}

export interface GlLedgerEntry {
  entry_id: string;
  doc_number: string;
  entry_date: string;
  description: string;
  debit_amount: string | null;
  credit_amount: string | null;
  running_balance: string;
  counterparty_name: string | null;
  module_code: string | null;
}

export interface GlLedgerResponse {
  subaccount_id: string;
  subaccount_code: string;
  subaccount_name: string;
  account_code: string;
  account_name: string;
  account_type: string;
  date_from: string;
  date_to: string;
  opening_balance: string;
  closing_balance: string;
  total_debit: string;
  total_credit: string;
  entries: GlLedgerEntry[];
}

export interface PlRow {
  subaccount_id: string;
  subaccount_code: string;
  subaccount_name: string;
  amount: string;
  by_module: Record<string, string>;
}

export interface PlReportResponse {
  date_from: string;
  date_to: string;
  revenue: PlRow[];
  expense: PlRow[];
  total_revenue: string;
  total_expense: string;
  profit: string;
}


// ─── Hooks ───────────────────────────────────────────────────


export function useTrialBalance(params: {
  date_from: string;
  date_to: string;
  module_code?: string;
  enabled?: boolean;
}) {
  const { date_from, date_to, module_code, enabled = true } = params;
  const qs = new URLSearchParams();
  qs.set('date_from', date_from);
  qs.set('date_to', date_to);
  if (module_code) qs.set('module_code', module_code);
  return useQuery<TrialBalanceResponse, ApiError>({
    queryKey: ['reports', 'trial-balance', qs.toString()],
    enabled: enabled && Boolean(date_from && date_to),
    queryFn: () => apiFetch<TrialBalanceResponse>(
      `/api/accounting/reports/trial-balance/?${qs.toString()}`,
    ),
    staleTime: 60_000,
  });
}


export function useGlLedger(params: {
  subaccount: string;
  date_from: string;
  date_to: string;
  enabled?: boolean;
}) {
  const { subaccount, date_from, date_to, enabled = true } = params;
  const qs = new URLSearchParams();
  qs.set('subaccount', subaccount);
  qs.set('date_from', date_from);
  qs.set('date_to', date_to);
  return useQuery<GlLedgerResponse, ApiError>({
    queryKey: ['reports', 'gl-ledger', qs.toString()],
    enabled: enabled && Boolean(subaccount && date_from && date_to),
    queryFn: () => apiFetch<GlLedgerResponse>(
      `/api/accounting/reports/gl-ledger/?${qs.toString()}`,
    ),
    staleTime: 60_000,
  });
}


export function usePlReport(params: {
  date_from: string;
  date_to: string;
  enabled?: boolean;
}) {
  const { date_from, date_to, enabled = true } = params;
  const qs = new URLSearchParams();
  qs.set('date_from', date_from);
  qs.set('date_to', date_to);
  return useQuery<PlReportResponse, ApiError>({
    queryKey: ['reports', 'pl', qs.toString()],
    enabled: enabled && Boolean(date_from && date_to),
    queryFn: () => apiFetch<PlReportResponse>(
      `/api/accounting/reports/pl/?${qs.toString()}`,
    ),
    staleTime: 60_000,
  });
}


// ─── P&L по модулям ─────────────────────────────────────────────


export interface PlModuleRow {
  module_code: string;
  module_name: string;
  revenue: string;
  expense: string;
  profit: string;
}

export interface PlByModuleResponse {
  date_from: string;
  date_to: string;
  rows: PlModuleRow[];
  total_revenue: string;
  total_expense: string;
  total_profit: string;
}

export function usePlByModule(params: {
  date_from: string;
  date_to: string;
  enabled?: boolean;
}) {
  const { date_from, date_to, enabled = true } = params;
  const qs = new URLSearchParams();
  qs.set('date_from', date_from);
  qs.set('date_to', date_to);
  return useQuery<PlByModuleResponse, ApiError>({
    queryKey: ['reports', 'pl-by-module', qs.toString()],
    enabled: enabled && Boolean(date_from && date_to),
    queryFn: () => apiFetch<PlByModuleResponse>(
      `/api/accounting/reports/pl-by-module/?${qs.toString()}`,
    ),
    staleTime: 60_000,
  });
}


// ─── AR Aging report ─────────────────────────────────────────


export interface AgingRow {
  counterparty_id: string;
  code: string;
  name: string;
  current: string;
  b_0_30: string;
  b_31_60: string;
  b_61_90: string;
  b_90_plus: string;
  total: string;
  oldest_overdue_days: number;
  orders_count: number;
  has_overdue: boolean;
}

export interface AgingSummary {
  current: string;
  b_0_30: string;
  b_31_60: string;
  b_61_90: string;
  b_90_plus: string;
  total: string;
  customers_count: number;
  overdue_customers_count: number;
}

export interface AgingResponse {
  rows: AgingRow[];
  summary: AgingSummary;
  as_of: string;
}

/**
 * GET /api/sales/orders/aging/[?customer=<uuid>]
 *
 * Если `customerId` задан — отчёт по одному клиенту (используется в
 * карточке должника).
 */
export function useAgingReport(customerId?: string | null) {
  const qs = customerId ? `?customer=${encodeURIComponent(customerId)}` : '';
  return useQuery<AgingResponse, ApiError>({
    queryKey: ['reports', 'aging', customerId ?? 'all'],
    queryFn: () => apiFetch<AgingResponse>(`/api/sales/orders/aging/${qs}`),
    staleTime: 30_000,
  });
}
