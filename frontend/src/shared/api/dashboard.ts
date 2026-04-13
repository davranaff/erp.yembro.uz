import { z } from 'zod';

import { apiClient } from './api-client';

export const dashboardMetricSchema = z.object({
  key: z.string(),
  label: z.string(),
  value: z.number(),
  unit: z.string().nullable().optional(),
  previous: z.number().nullable().optional(),
  delta: z.number().nullable().optional(),
  deltaPercent: z.number().nullable().optional(),
  status: z.enum(['good', 'warning', 'bad', 'neutral']).nullable().optional(),
  trend: z.enum(['up', 'down', 'flat']).nullable().optional(),
});

export const dashboardSeriesPointSchema = z.object({
  label: z.string(),
  value: z.number(),
});

export const dashboardChartSeriesSchema = z.object({
  key: z.string(),
  label: z.string(),
  points: z.array(dashboardSeriesPointSchema),
});

export const dashboardChartSchema = z.object({
  key: z.string(),
  title: z.string(),
  description: z.string().nullable().optional(),
  type: z.enum(['line', 'bar', 'stacked-bar']),
  unit: z.string().nullable().optional(),
  series: z.array(dashboardChartSeriesSchema),
});

export const dashboardBreakdownItemSchema = z.object({
  key: z.string(),
  label: z.string(),
  value: z.number(),
  unit: z.string().nullable().optional(),
  caption: z.string().nullable().optional(),
});

export const dashboardBreakdownSchema = z.object({
  key: z.string(),
  title: z.string(),
  description: z.string().nullable().optional(),
  items: z.array(dashboardBreakdownItemSchema),
});

export const dashboardSectionSchema = z.object({
  key: z.string(),
  title: z.string(),
  description: z.string().nullable().optional(),
  metrics: z.array(dashboardMetricSchema),
  charts: z.array(dashboardChartSchema),
  breakdowns: z.array(dashboardBreakdownSchema),
});

export const dashboardAlertSchema = z.object({
  key: z.string(),
  level: z.enum(['info', 'warning', 'critical']),
  title: z.string(),
  message: z.string(),
  value: z.number().nullable().optional(),
  unit: z.string().nullable().optional(),
});

export const dashboardModuleSchema = z.object({
  key: z.string(),
  title: z.string(),
  description: z.string().nullable().optional(),
  kpis: z.array(dashboardMetricSchema),
  charts: z.array(dashboardChartSchema),
  tables: z.array(dashboardBreakdownSchema),
  alerts: z.array(dashboardAlertSchema).optional(),
  healthScore: z.number().nullable().optional(),
  healthStatus: z.enum(['good', 'warning', 'bad', 'neutral']).nullable().optional(),
});

export const dashboardDepartmentDashboardSchema = z.object({
  modules: z.array(dashboardModuleSchema),
});

export const dashboardExecutiveDashboardSchema = z.object({
  kpis: z.array(dashboardMetricSchema),
  charts: z.array(dashboardChartSchema),
  tables: z.array(dashboardBreakdownSchema),
  alerts: z.array(dashboardAlertSchema).optional(),
});

export const dashboardAnalyticsResponseSchema = z.object({
  generatedAt: z.string(),
  currency: z.string(),
  scope: z.object({
    departmentId: z.string().trim().nullable().optional(),
    departmentLabel: z.string(),
    departmentModuleKey: z.string().trim().nullable().optional(),
    departmentPath: z.array(z.string()),
    startDate: z.string().nullable().optional(),
    endDate: z.string().nullable().optional(),
  }),
  department_dashboard: dashboardDepartmentDashboardSchema.nullable().optional(),
  executive_dashboard: dashboardExecutiveDashboardSchema.nullable().optional(),
});

export const dashboardOverviewScopeSchema = z.object({
  departmentId: z.string().trim().nullable().optional(),
  departmentLabel: z.string(),
  departmentModuleKey: z.string().trim().nullable().optional(),
  departmentPath: z.array(z.string()),
  startDate: z.string().nullable().optional(),
  endDate: z.string().nullable().optional(),
});

export const dashboardOverviewResponseSchema = z.object({
  generatedAt: z.string(),
  currency: z.string(),
  scope: dashboardOverviewScopeSchema,
  department_dashboard: dashboardDepartmentDashboardSchema.nullable().optional(),
  executive_dashboard: dashboardExecutiveDashboardSchema.nullable().optional(),
});

export type DashboardMetric = z.infer<typeof dashboardMetricSchema>;
export type DashboardSeriesPoint = z.infer<typeof dashboardSeriesPointSchema>;
export type DashboardChartSeries = z.infer<typeof dashboardChartSeriesSchema>;
export type DashboardChart = z.infer<typeof dashboardChartSchema>;
export type DashboardBreakdownItem = z.infer<typeof dashboardBreakdownItemSchema>;
export type DashboardBreakdown = z.infer<typeof dashboardBreakdownSchema>;
export type DashboardSection = z.infer<typeof dashboardSectionSchema>;
export type DashboardAlert = z.infer<typeof dashboardAlertSchema>;
export type DashboardModuleDashboard = z.infer<typeof dashboardModuleSchema>;
export type DashboardDepartmentDashboard = z.infer<typeof dashboardDepartmentDashboardSchema>;
export type DashboardExecutiveDashboard = z.infer<typeof dashboardExecutiveDashboardSchema>;
export type DashboardAnalyticsResponse = z.infer<typeof dashboardAnalyticsResponseSchema>;
export type DashboardOverviewScope = z.infer<typeof dashboardOverviewScopeSchema>;
export type DashboardOverviewResponse = z.infer<typeof dashboardOverviewResponseSchema>;

export type DashboardAnalyticsFilters = {
  startDate?: string;
  endDate?: string;
  departmentId?: string;
};

export const getDashboardAnalytics = async (
  filters: DashboardAnalyticsFilters = {},
): Promise<DashboardAnalyticsResponse> => {
  const searchParams = new URLSearchParams();

  if (filters.startDate) {
    searchParams.set('start_date', filters.startDate);
  }

  if (filters.endDate) {
    searchParams.set('end_date', filters.endDate);
  }

  if (filters.departmentId) {
    searchParams.set('department_id', filters.departmentId);
  }

  const search = searchParams.toString();
  const path = search ? `/dashboard/analytics?${search}` : '/dashboard/analytics';

  return apiClient.get(path, dashboardAnalyticsResponseSchema);
};

export const getDashboardOverview = async (
  filters: DashboardAnalyticsFilters = {},
): Promise<DashboardOverviewResponse> => {
  const searchParams = new URLSearchParams();

  if (filters.startDate) {
    searchParams.set('start_date', filters.startDate);
  }

  if (filters.endDate) {
    searchParams.set('end_date', filters.endDate);
  }

  if (filters.departmentId) {
    searchParams.set('department_id', filters.departmentId);
  }

  const search = searchParams.toString();
  const path = search ? `/dashboard/overview?${search}` : '/dashboard/overview';

  return apiClient.get(path, dashboardOverviewResponseSchema);
};
