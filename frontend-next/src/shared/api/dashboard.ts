import { z } from 'zod';

import { api } from './client';

const metricSchema = z.object({
  key: z.string(),
  title: z.string(),
  value: z.number(),
  unit: z.string().nullable().optional(),
  caption: z.string().nullable().optional(),
  status: z.enum(['neutral', 'good', 'warning', 'bad']).nullable().optional(),
  previous_value: z.number().nullable().optional(),
  change_percent: z.number().nullable().optional(),
});

const chartPointSchema = z.object({
  label: z.string(),
  value: z.number(),
});

const chartSeriesSchema = z.object({
  key: z.string(),
  label: z.string(),
  unit: z.string().nullable().optional(),
  points: z.array(chartPointSchema),
});

const chartSchema = z.object({
  key: z.string(),
  title: z.string(),
  description: z.string().nullable().optional(),
  type: z.enum(['line', 'bar', 'stacked-bar']),
  series: z.array(chartSeriesSchema),
});

const breakdownItemSchema = z.object({
  key: z.string(),
  label: z.string(),
  value: z.number(),
  unit: z.string().nullable().optional(),
  caption: z.string().nullable().optional(),
});

const breakdownSchema = z.object({
  key: z.string(),
  title: z.string(),
  description: z.string().nullable().optional(),
  items: z.array(breakdownItemSchema),
});

const alertSchema = z.object({
  key: z.string(),
  title: z.string(),
  message: z.string(),
  tone: z.enum(['info', 'warning', 'danger']).nullable().optional(),
  value: z.number().nullable().optional(),
  unit: z.string().nullable().optional(),
});

const moduleSchema = z.object({
  key: z.string(),
  title: z.string(),
  description: z.string().nullable().optional(),
  kpis: z.array(metricSchema),
  charts: z.array(chartSchema),
  tables: z.array(breakdownSchema),
  alerts: z.array(alertSchema).nullable().optional(),
});

const dashboardResponseSchema = z.object({
  generated_at: z.string(),
  period: z.object({
    start_date: z.string().nullable().optional(),
    end_date: z.string().nullable().optional(),
  }),
  department_dashboard: z
    .object({
      modules: z.array(moduleSchema),
    })
    .nullable()
    .optional(),
});

export type DashboardResponse = z.infer<typeof dashboardResponseSchema>;
export type DashboardModule = z.infer<typeof moduleSchema>;

export async function getDashboardAnalytics(params: {
  startDate?: string;
  endDate?: string;
  departmentId?: string;
}): Promise<DashboardResponse> {
  const data = await api.get<unknown>('/dashboard/analytics', {
    query: {
      start_date: params.startDate,
      end_date: params.endDate,
      department_id: params.departmentId,
    },
  });
  return dashboardResponseSchema.parse(data);
}
