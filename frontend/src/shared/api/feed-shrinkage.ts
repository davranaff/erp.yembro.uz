import { z } from 'zod';

import { apiClient } from './api-client';

export const feedShrinkageOverviewItemSchema = z.object({
  state_id: z.string(),
  lot_id: z.string(),
  lot_label: z.string().nullable().optional(),
  name: z.string().nullable().optional(),
  code: z.string().nullable().optional(),
  warehouse_name: z.string().nullable().optional(),
  started_on: z.string().nullable().optional(),
  initial_quantity: z.string(),
  current_quantity: z.string(),
  loss_quantity: z.string(),
  loss_percent: z.string(),
  last_applied_on: z.string().nullable().optional(),
  is_frozen: z.boolean(),
});

export const feedShrinkageOverviewSchema = z.object({
  ingredients: z.array(feedShrinkageOverviewItemSchema),
  feed_products: z.array(feedShrinkageOverviewItemSchema),
});

export type FeedShrinkageOverviewItem = z.infer<typeof feedShrinkageOverviewItemSchema>;
export type FeedShrinkageOverview = z.infer<typeof feedShrinkageOverviewSchema>;

export const getFeedShrinkageOverview = () =>
  apiClient.get<FeedShrinkageOverview>('/feed/shrinkage/overview', feedShrinkageOverviewSchema);
