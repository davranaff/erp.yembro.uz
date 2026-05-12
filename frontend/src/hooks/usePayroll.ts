'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import { asList } from '@/lib/paginated';
import type { Paginated } from '@/types/auth';
import type {
  AccrualResult,
  AdjustmentKind,
  AllBalancesResponse,
  CompensationPlan,
  CompensationType,
  EmployeeBalance,
  EmployeeCalendar,
  PayoutType,
  PayrollAdjustment,
  PayrollPayout,
  PayrollRun,
  PayrollRunPreview,
  SalaryRate,
  WorkSchedule,
  WorkScheduleTemplate,
  WorkShift,
  WorkShiftKind,
} from '@/types/payroll';

// ─── compensation plans ───────────────────────────────────────────────────

const COMP_KEY = ['payroll', 'compensation-plans'] as const;

export function useCompensationPlanForEmployee(employeeId?: string | null) {
  return useQuery<CompensationPlan | null, ApiError>({
    queryKey: [...COMP_KEY, 'employee', employeeId],
    enabled: Boolean(employeeId),
    queryFn: async () => {
      const data = await apiFetch<Paginated<CompensationPlan> | CompensationPlan[]>(
        `/api/payroll/compensation-plans/?employee=${employeeId}`,
      );
      const list = asList(data);
      return list[0] ?? null;
    },
    staleTime: 30_000,
  });
}

export type SaveCompensationPlanVars = {
  id?: string;
  employee: string;
  compensation_type: CompensationType;
  currency: string;
  notes?: string;
};

export function useSaveCompensationPlan() {
  const qc = useQueryClient();
  return useMutation<CompensationPlan, ApiError, SaveCompensationPlanVars>({
    mutationFn: ({ id, ...body }) => {
      if (id) {
        return apiFetch<CompensationPlan>(`/api/payroll/compensation-plans/${id}/`, {
          method: 'PATCH',
          body,
        });
      }
      return apiFetch<CompensationPlan>('/api/payroll/compensation-plans/', {
        method: 'POST',
        body,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: COMP_KEY });
      qc.invalidateQueries({ queryKey: ['memberships'] });
    },
  });
}

// ─── salary rates ─────────────────────────────────────────────────────────

const RATES_KEY = ['payroll', 'rates'] as const;

export function useSalaryRates(employeeId?: string | null) {
  return useQuery<SalaryRate[], ApiError>({
    queryKey: [...RATES_KEY, employeeId],
    enabled: Boolean(employeeId),
    queryFn: async () => {
      const data = await apiFetch<Paginated<SalaryRate> | SalaryRate[]>(
        `/api/payroll/rates/?employee=${employeeId}&page_size=200`,
      );
      return asList(data);
    },
    staleTime: 30_000,
  });
}

export type CreateRateVars = {
  employee: string;
  amount: string;
  currency: string;
  effective_from: string;
  reason?: string;
};

export function useCreateRate() {
  const qc = useQueryClient();
  return useMutation<SalaryRate, ApiError, CreateRateVars>({
    mutationFn: (body) =>
      apiFetch<SalaryRate>('/api/payroll/rates/', { method: 'POST', body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: RATES_KEY });
      qc.invalidateQueries({ queryKey: ['memberships'] });
    },
  });
}

export function useDeleteRate() {
  const qc = useQueryClient();
  return useMutation<void, ApiError, string>({
    mutationFn: (id) =>
      apiFetch<void>(`/api/payroll/rates/${id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: RATES_KEY });
      qc.invalidateQueries({ queryKey: ['memberships'] });
    },
  });
}

// ─── schedule templates ───────────────────────────────────────────────────

const TEMPLATES_KEY = ['payroll', 'schedule-templates'] as const;

export function useScheduleTemplates() {
  return useQuery<WorkScheduleTemplate[], ApiError>({
    queryKey: TEMPLATES_KEY,
    queryFn: async () => {
      const data = await apiFetch<Paginated<WorkScheduleTemplate> | WorkScheduleTemplate[]>(
        `/api/payroll/schedule-templates/?page_size=200`,
      );
      return asList(data);
    },
    staleTime: 60_000,
  });
}

export type SaveTemplateVars = {
  id?: string;
  code: string;
  name: string;
  pattern_kind: 'weekday_mask' | 'rotation';
  pattern: Record<string, unknown>;
  is_active?: boolean;
};

export function useSaveTemplate() {
  const qc = useQueryClient();
  return useMutation<WorkScheduleTemplate, ApiError, SaveTemplateVars>({
    mutationFn: ({ id, ...body }) => {
      if (id) {
        return apiFetch<WorkScheduleTemplate>(`/api/payroll/schedule-templates/${id}/`, {
          method: 'PATCH',
          body,
        });
      }
      return apiFetch<WorkScheduleTemplate>('/api/payroll/schedule-templates/', {
        method: 'POST',
        body,
      });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: TEMPLATES_KEY }),
  });
}

export function useDeleteTemplate() {
  const qc = useQueryClient();
  return useMutation<void, ApiError, string>({
    mutationFn: (id) =>
      apiFetch<void>(`/api/payroll/schedule-templates/${id}/`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: TEMPLATES_KEY }),
  });
}

// ─── work schedules ───────────────────────────────────────────────────────

const SCHEDULES_KEY = ['payroll', 'work-schedules'] as const;

export function useWorkSchedules(employeeId?: string | null) {
  return useQuery<WorkSchedule[], ApiError>({
    queryKey: [...SCHEDULES_KEY, employeeId],
    enabled: Boolean(employeeId),
    queryFn: async () => {
      const data = await apiFetch<Paginated<WorkSchedule> | WorkSchedule[]>(
        `/api/payroll/work-schedules/?employee=${employeeId}&page_size=100`,
      );
      return asList(data);
    },
    staleTime: 30_000,
  });
}

export type SaveWorkScheduleVars = {
  employee: string;
  template: string;
  effective_from: string;
  effective_to?: string | null;
};

export function useCreateWorkSchedule() {
  const qc = useQueryClient();
  return useMutation<WorkSchedule, ApiError, SaveWorkScheduleVars>({
    mutationFn: (body) =>
      apiFetch<WorkSchedule>('/api/payroll/work-schedules/', { method: 'POST', body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SCHEDULES_KEY });
      qc.invalidateQueries({ queryKey: ['payroll', 'calendar'] });
    },
  });
}

export function useDeleteWorkSchedule() {
  const qc = useQueryClient();
  return useMutation<void, ApiError, string>({
    mutationFn: (id) =>
      apiFetch<void>(`/api/payroll/work-schedules/${id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SCHEDULES_KEY });
      qc.invalidateQueries({ queryKey: ['payroll', 'calendar'] });
    },
  });
}

// ─── work shifts (табель) ─────────────────────────────────────────────────

const SHIFTS_KEY = ['payroll', 'work-shifts'] as const;

export function useWorkShifts(
  employeeId: string | null | undefined,
  fromDate?: string,
  toDate?: string,
) {
  const params = new URLSearchParams();
  if (employeeId) params.set('employee', employeeId);
  if (fromDate) params.set('shift_date__gte', fromDate);
  if (toDate) params.set('shift_date__lte', toDate);
  params.set('page_size', '500');
  const qs = params.toString();
  return useQuery<WorkShift[], ApiError>({
    queryKey: [...SHIFTS_KEY, qs],
    enabled: Boolean(employeeId),
    queryFn: async () => {
      const data = await apiFetch<Paginated<WorkShift> | WorkShift[]>(
        `/api/payroll/work-shifts/?${qs}`,
      );
      return asList(data);
    },
    staleTime: 30_000,
  });
}

export type SaveWorkShiftVars = {
  id?: string;
  employee?: string;
  shift_date?: string;
  kind: WorkShiftKind;
  hours?: string | null;
  notes?: string;
};

export function useSaveWorkShift() {
  const qc = useQueryClient();
  return useMutation<WorkShift, ApiError, SaveWorkShiftVars>({
    mutationFn: ({ id, ...body }) => {
      if (id) {
        return apiFetch<WorkShift>(`/api/payroll/work-shifts/${id}/`, {
          method: 'PATCH',
          body,
        });
      }
      return apiFetch<WorkShift>('/api/payroll/work-shifts/', {
        method: 'POST',
        body,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SHIFTS_KEY });
      qc.invalidateQueries({ queryKey: ['payroll', 'calendar'] });
      qc.invalidateQueries({ queryKey: ['memberships'] });
    },
  });
}

export function useDeleteWorkShift() {
  const qc = useQueryClient();
  return useMutation<void, ApiError, string>({
    mutationFn: (id) =>
      apiFetch<void>(`/api/payroll/work-shifts/${id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SHIFTS_KEY });
      qc.invalidateQueries({ queryKey: ['payroll', 'calendar'] });
      qc.invalidateQueries({ queryKey: ['memberships'] });
    },
  });
}

export type ApplyTemplateVars = {
  employee: string;
  template: string;
  from_date: string;
  to_date: string;
};

export function useApplyTemplate() {
  const qc = useQueryClient();
  return useMutation<{ created: number }, ApiError, ApplyTemplateVars>({
    mutationFn: (body) =>
      apiFetch<{ created: number }>('/api/payroll/work-shifts/bulk/', {
        method: 'POST',
        body,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SHIFTS_KEY });
      qc.invalidateQueries({ queryKey: ['payroll', 'calendar'] });
      qc.invalidateQueries({ queryKey: ['memberships'] });
    },
  });
}

export type BulkSetKindVars = {
  employee: string;
  dates: string[];
  kind: WorkShiftKind;
  hours?: string | null;
  notes?: string;
};

export function useBulkSetKind() {
  const qc = useQueryClient();
  return useMutation<{ created: number; updated: number }, ApiError, BulkSetKindVars>({
    mutationFn: (body) =>
      apiFetch<{ created: number; updated: number }>(
        '/api/payroll/work-shifts/bulk-set-kind/',
        { method: 'POST', body },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SHIFTS_KEY });
      qc.invalidateQueries({ queryKey: ['payroll', 'calendar'] });
      qc.invalidateQueries({ queryKey: ['memberships'] });
    },
  });
}

// ─── payouts ──────────────────────────────────────────────────────────────

const PAYOUTS_KEY = ['payroll', 'payouts'] as const;

export function useEmployeePayouts(employeeId?: string | null) {
  return useQuery<PayrollPayout[], ApiError>({
    queryKey: [...PAYOUTS_KEY, employeeId],
    enabled: Boolean(employeeId),
    queryFn: async () => {
      const data = await apiFetch<Paginated<PayrollPayout> | PayrollPayout[]>(
        `/api/payroll/payouts/?employee=${employeeId}&page_size=200`,
      );
      return asList(data);
    },
    staleTime: 30_000,
  });
}

export type CreatePayoutVars = {
  employee: string;
  type: PayoutType;
  amount_uzs: string;
  period_from: string;
  period_to: string;
  cash_subaccount: string;
  on_date?: string;
  channel?: string;
  notes?: string;
};

export function useCreatePayout() {
  const qc = useQueryClient();
  return useMutation<PayrollPayout, ApiError, CreatePayoutVars>({
    mutationFn: (body) =>
      apiFetch<PayrollPayout>('/api/payroll/payouts/', { method: 'POST', body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: PAYOUTS_KEY });
      qc.invalidateQueries({ queryKey: ['memberships'] });
    },
  });
}

export function useCancelPayout() {
  const qc = useQueryClient();
  return useMutation<PayrollPayout, ApiError, { id: string; reason?: string }>({
    mutationFn: ({ id, reason }) =>
      apiFetch<PayrollPayout>(`/api/payroll/payouts/${id}/cancel/`, {
        method: 'POST',
        body: reason ? { reason } : {},
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: PAYOUTS_KEY });
      qc.invalidateQueries({ queryKey: ['memberships'] });
      qc.invalidateQueries({ queryKey: ['payroll', 'balance'] });
    },
  });
}

// ─── payroll runs ─────────────────────────────────────────────────────────

const RUNS_KEY = ['payroll', 'runs'] as const;

export function usePayrollRuns() {
  return useQuery<PayrollRun[], ApiError>({
    queryKey: RUNS_KEY,
    queryFn: async () => {
      const data = await apiFetch<Paginated<PayrollRun> | PayrollRun[]>(
        '/api/payroll/runs/?page_size=200',
      );
      return asList(data);
    },
    staleTime: 30_000,
  });
}

export function usePreviewRun() {
  return useMutation<PayrollRunPreview, ApiError, { period_from: string; period_to: string }>({
    mutationFn: (body) =>
      apiFetch<PayrollRunPreview>('/api/payroll/runs/preview/', { method: 'POST', body }),
  });
}

export type ExecuteRunVars = {
  period_from: string;
  period_to: string;
  cash_subaccount: string;
  payout_type?: PayoutType;
  employee_amounts?: Record<string, string>;
  notes?: string;
};

export function useExecuteRun() {
  const qc = useQueryClient();
  return useMutation<PayrollRun, ApiError, ExecuteRunVars>({
    mutationFn: (body) =>
      apiFetch<PayrollRun>('/api/payroll/runs/execute/', { method: 'POST', body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: RUNS_KEY });
      qc.invalidateQueries({ queryKey: ['payroll', 'balance'] });
      qc.invalidateQueries({ queryKey: ['payroll', 'balances-all'] });
      qc.invalidateQueries({ queryKey: ['payroll', 'payouts'] });
      qc.invalidateQueries({ queryKey: ['memberships'] });
    },
  });
}

// ─── adjustments ──────────────────────────────────────────────────────────

const ADJUSTMENTS_KEY = ['payroll', 'adjustments'] as const;

export function useEmployeeAdjustments(employeeId?: string | null) {
  return useQuery<PayrollAdjustment[], ApiError>({
    queryKey: [...ADJUSTMENTS_KEY, employeeId],
    enabled: Boolean(employeeId),
    queryFn: async () => {
      const data = await apiFetch<Paginated<PayrollAdjustment> | PayrollAdjustment[]>(
        `/api/payroll/adjustments/?employee=${employeeId}&page_size=200`,
      );
      return asList(data);
    },
    staleTime: 30_000,
  });
}

export type CreateAdjustmentVars = {
  employee: string;
  kind: AdjustmentKind;
  effective_date: string;
  amount_uzs: string;
  reason?: string;
  notes?: string;
};

export function useCreateAdjustment() {
  const qc = useQueryClient();
  return useMutation<PayrollAdjustment, ApiError, CreateAdjustmentVars>({
    mutationFn: (body) =>
      apiFetch<PayrollAdjustment>('/api/payroll/adjustments/', { method: 'POST', body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ADJUSTMENTS_KEY });
      qc.invalidateQueries({ queryKey: ['payroll', 'balance'] });
      qc.invalidateQueries({ queryKey: ['payroll', 'balances-all'] });
      qc.invalidateQueries({ queryKey: ['memberships'] });
    },
  });
}

export function useDeleteAdjustment() {
  const qc = useQueryClient();
  return useMutation<void, ApiError, string>({
    mutationFn: (id) =>
      apiFetch<void>(`/api/payroll/adjustments/${id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ADJUSTMENTS_KEY });
      qc.invalidateQueries({ queryKey: ['payroll', 'balance'] });
      qc.invalidateQueries({ queryKey: ['memberships'] });
    },
  });
}

// ─── employee aggregates ──────────────────────────────────────────────────

// ─── self-service ─────────────────────────────────────────────────────────

export interface MyPayrollData {
  balance: {
    as_of: string;
    accrued_total: string;
    paid_total: string;
    adjustments_plus: string;
    adjustments_minus: string;
    balance_uzs: string;
  };
  rates: Array<{
    id: string;
    amount: string;
    currency_code: string | null;
    effective_from: string;
    effective_to: string | null;
    reason: string;
  }>;
  payouts: Array<{
    id: string;
    type: string;
    amount_uzs: string;
    period_from: string;
    period_to: string;
    payment_doc_number: string | null;
    payment_status: string | null;
  }>;
  adjustments: Array<{
    id: string;
    kind: string;
    effective_date: string;
    amount_uzs: string;
    reason: string;
  }>;
}

export function useMyPayroll() {
  return useQuery<MyPayrollData, ApiError>({
    queryKey: ['payroll', 'me'],
    queryFn: () => apiFetch<MyPayrollData>('/api/payroll/me/'),
    staleTime: 30_000,
  });
}

export function useAllBalances(asOf?: string, includeInactive = false) {
  const params = new URLSearchParams();
  if (asOf) params.set('as_of', asOf);
  if (includeInactive) params.set('include_inactive', '1');
  const qs = params.toString();
  return useQuery<AllBalancesResponse, ApiError>({
    queryKey: ['payroll', 'balances-all', qs],
    queryFn: () =>
      apiFetch<AllBalancesResponse>(
        `/api/payroll/balances/${qs ? '?' + qs : ''}`,
      ),
    staleTime: 30_000,
  });
}

export function useEmployeeBalance(employeeId?: string | null, asOf?: string) {
  const qs = asOf ? `?as_of=${asOf}` : '';
  return useQuery<EmployeeBalance, ApiError>({
    queryKey: ['payroll', 'balance', employeeId, asOf],
    enabled: Boolean(employeeId),
    queryFn: () =>
      apiFetch<EmployeeBalance>(
        `/api/payroll/employees/${employeeId}/balance/${qs}`,
      ),
    staleTime: 30_000,
  });
}

export function useEmployeeAccrued(
  employeeId: string | null | undefined,
  fromDate?: string,
  toDate?: string,
) {
  const params = new URLSearchParams();
  if (fromDate) params.set('from', fromDate);
  if (toDate) params.set('to', toDate);
  const qs = params.toString();
  return useQuery<AccrualResult, ApiError>({
    queryKey: ['payroll', 'accrued', employeeId, qs],
    enabled: Boolean(employeeId && fromDate && toDate),
    queryFn: () =>
      apiFetch<AccrualResult>(
        `/api/payroll/employees/${employeeId}/accrued/?${qs}`,
      ),
    staleTime: 30_000,
  });
}

export function useEmployeeCalendar(
  employeeId: string | null | undefined,
  fromDate: string,
  toDate: string,
) {
  return useQuery<EmployeeCalendar, ApiError>({
    queryKey: ['payroll', 'calendar', employeeId, fromDate, toDate],
    enabled: Boolean(employeeId && fromDate && toDate),
    queryFn: () =>
      apiFetch<EmployeeCalendar>(
        `/api/payroll/employees/${employeeId}/calendar/?from=${fromDate}&to=${toDate}`,
      ),
    staleTime: 30_000,
  });
}
