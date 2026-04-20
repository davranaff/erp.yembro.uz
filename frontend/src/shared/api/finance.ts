import { z } from 'zod';

import { apiClient } from './api-client';

const debtsAgingBucketsSchema = z.object({
  not_due: z.number(),
  bucket_0_30: z.number(),
  bucket_31_60: z.number(),
  bucket_61_90: z.number(),
  bucket_90_plus: z.number(),
  total: z.number(),
});

export const debtsAgingResponseSchema = z.object({
  as_of: z.string(),
  receivables: debtsAgingBucketsSchema,
  payables: debtsAgingBucketsSchema,
});

export type DebtsAgingBuckets = z.infer<typeof debtsAgingBucketsSchema>;
export type DebtsAgingResponse = z.infer<typeof debtsAgingResponseSchema>;

export const getDebtsAging = (params?: {
  asOf?: string;
  departmentId?: string;
  departmentIds?: string[];
}) => {
  const search = new URLSearchParams();
  if (params?.asOf) {
    search.set('as_of', params.asOf);
  }
  const ids =
    params?.departmentIds && params.departmentIds.length > 0
      ? params.departmentIds
      : params?.departmentId
        ? [params.departmentId]
        : [];
  ids
    .map((id) => id.trim())
    .filter((id) => id.length > 0)
    .forEach((id) => search.append('department_id', id));
  const qs = search.toString();
  const path = qs ? `/finance/debts/aging?${qs}` : `/finance/debts/aging`;
  return apiClient.get<DebtsAgingResponse>(path, debtsAgingResponseSchema);
};
