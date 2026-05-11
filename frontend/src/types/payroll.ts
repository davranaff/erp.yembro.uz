// ─── payroll ──────────────────────────────────────────────────────────────

export type CompensationType = 'monthly_salary' | 'per_shift' | 'per_hour';

export interface CompensationPlan {
  id: string;
  organization: string;
  employee: string;
  employee_full_name: string | null;
  compensation_type: CompensationType;
  currency: string;
  currency_code: string | null;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface SalaryRate {
  id: string;
  organization: string;
  employee: string;
  employee_full_name: string | null;
  amount: string;
  currency: string;
  currency_code: string | null;
  effective_from: string;
  effective_to: string | null;
  reason: string;
  created_at: string;
  updated_at: string;
}

export type WorkSchedulePatternKind = 'weekday_mask' | 'rotation';

export interface WeekdayMaskPattern {
  weekdays: number[]; // 0..6 Mon..Sun
  start: string; // HH:MM
  end: string;
  duration_hours: number;
}

export interface RotationPattern {
  work_days: number;
  rest_days: number;
  anchor_date: string; // YYYY-MM-DD
  start: string;
  end: string;
  duration_hours: number;
}

export type SchedulePattern = WeekdayMaskPattern | RotationPattern;

export interface WorkScheduleTemplate {
  id: string;
  organization: string;
  code: string;
  name: string;
  pattern_kind: WorkSchedulePatternKind;
  pattern: SchedulePattern;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface WorkSchedule {
  id: string;
  organization: string;
  employee: string;
  employee_full_name: string | null;
  template: string;
  template_code: string | null;
  effective_from: string;
  effective_to: string | null;
  created_at: string;
  updated_at: string;
}

export type WorkShiftKind =
  | 'work'
  | 'overtime'
  | 'vacation'
  | 'sick_leave'
  | 'absence'
  | 'day_off'
  | 'holiday';

export type WorkShiftSource = 'template' | 'manual' | 'import';

export interface WorkShift {
  id: string;
  organization: string;
  employee: string;
  employee_full_name: string | null;
  shift_date: string;
  kind: WorkShiftKind;
  source: WorkShiftSource;
  start_at: string | null;
  end_at: string | null;
  hours: string | null;
  source_template: string | null;
  template_code: string | null;
  notes: string;
  created_at: string;
  updated_at: string;
}

export type PayoutType = 'advance' | 'salary' | 'bonus' | 'correction';

export interface PayrollPayout {
  id: string;
  organization: string;
  employee: string;
  employee_full_name: string | null;
  type: PayoutType;
  period_from: string;
  period_to: string;
  payment: string;
  payment_doc_number: string | null;
  payment_status: string | null;
  amount_uzs: string;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface EmployeeBalance {
  employee_id: string;
  as_of: string;
  accrued_total: string;
  paid_total: string;
  adjustments_plus: string;
  adjustments_minus: string;
  balance_uzs: string;
}

export type AdjustmentKind =
  | 'bonus'
  | 'deduction'
  | 'correction_plus'
  | 'correction_minus';

export interface PayrollAdjustment {
  id: string;
  organization: string;
  employee: string;
  employee_full_name: string | null;
  kind: AdjustmentKind;
  effective_date: string;
  amount_uzs: string;
  reason: string;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface AccrualLine {
  date: string;
  rate_amount: string;            // native rate per unit
  rate_currency: string;          // валюта ставки
  accrued_native: string;         // в native валюте
  accrued: string;                // в UZS (после конвертации)
  exchange_rate: string;          // UZS за единицу currency (1 для UZS)
  note: string;
}

export interface AccrualResult {
  employee_id: string;
  period_from: string;
  period_to: string;
  compensation_type: string;
  currency_code: string | null;
  accrued_uzs: string;
  breakdown: AccrualLine[];
}

export interface CalendarExpectedItem {
  date: string;
  start_time: string | null;
  end_time: string | null;
  duration_hours: string;
  kind: WorkShiftKind;
}

export interface CalendarActualItem {
  id: string;
  date: string;
  kind: WorkShiftKind;
  source: WorkShiftSource;
  start_at: string | null;
  end_at: string | null;
  hours: string | null;
  notes: string;
}

export interface EmployeeCalendar {
  employee_id: string;
  from: string;
  to: string;
  template_code: string | null;
  expected: CalendarExpectedItem[];
  actual: CalendarActualItem[];
}

export interface AttendanceMonth {
  work: number;
  overtime: number;
  vacation: number;
  sick_leave: number;
  absence: number;
  day_off: number;
  holiday: number;
}

export interface AllBalancesRow {
  employee_id: string;
  full_name: string | null;
  position_title: string;
  compensation_type: string | null;
  accrued_total: string;
  paid_total: string;
  adjustments_plus: string;
  adjustments_minus: string;
  balance_uzs: string;
  is_active: boolean;
  work_status: string;
  attendance_month: AttendanceMonth;
}

export interface MonthlyFundPoint {
  month: string;       // "YYYY-MM"
  accrued_uzs: string;
  paid_uzs: string;
}

export interface AllBalancesResponse {
  as_of: string;
  totals: {
    employees: number;
    total_balance_uzs: number;
    total_paid_uzs: number;
    total_accrued_uzs: number;
    attendance_month: AttendanceMonth;
    month_label: string;
  };
  rows: AllBalancesRow[];
  monthly_fund: MonthlyFundPoint[];
}

export interface PayrollRunPreviewRow {
  employee_id: string;
  full_name: string;
  balance_uzs: string;
  due_uzs: string;
}

export interface PayrollRunPreview {
  period_from: string;
  period_to: string;
  rows: PayrollRunPreviewRow[];
  total_uzs: string;
}

export interface PayrollRun {
  id: string;
  organization: string;
  period_from: string;
  period_to: string;
  payout_type: PayoutType;
  cash_subaccount: string;
  status: 'draft' | 'executed' | 'cancelled';
  employees_count: number;
  total_amount_uzs: string;
  notes: string;
  executed_at: string | null;
  created_at: string;
}
