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
