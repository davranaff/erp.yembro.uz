import { z } from 'zod';

import { apiClient } from './api-client';

export const factoryFlockKpiSchema = z.object({
  flock_id: z.string(),
  status: z.string().nullable().optional(),
  arrived_on: z.string().nullable().optional(),
  last_log_date: z.string().nullable().optional(),
  initial_count: z.number(),
  current_count: z.number(),
  mortality_total: z.number(),
  mortality_pct: z.number().nullable().optional(),
  birds_shipped: z.number(),
  feed_kg_total: z.number(),
  feed_cost_total: z.number(),
  medicine_cost_total: z.number(),
  total_cost: z.number(),
  latest_avg_weight_kg: z.number(),
  live_weight_total_kg: z.number(),
  fcr: z.number().nullable().optional(),
  cost_per_chick_alive: z.number().nullable().optional(),
  cost_per_chick_shipped: z.number().nullable().optional(),
});

export type FactoryFlockKpi = z.infer<typeof factoryFlockKpiSchema>;

export const getFactoryFlockKpi = (flockId: string) =>
  apiClient.get<FactoryFlockKpi>(`/factory/flocks/${flockId}/kpi`, factoryFlockKpiSchema);
