'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import { makeCrud } from '@/lib/crudFactory';
import type {
  SlaughterLabTest,
  SlaughterQualityCheck,
  SlaughterShift,
  SlaughterStats,
  SlaughterTimelineEvent,
  SlaughterYield,
} from '@/types/auth';

export const shiftsCrud = makeCrud<SlaughterShift>({
  key: ['slaughter', 'shifts'],
  path: '/api/slaughter/shifts/',
  ordering: '-shift_date',
});

export const yieldsCrud = makeCrud<SlaughterYield>({
  key: ['slaughter', 'yields'],
  path: '/api/slaughter/yields/',
});

export const qualityChecksCrud = makeCrud<SlaughterQualityCheck>({
  key: ['slaughter', 'quality-checks'],
  path: '/api/slaughter/quality-checks/',
});

export const labTestsCrud = makeCrud<SlaughterLabTest>({
  key: ['slaughter', 'lab-tests'],
  path: '/api/slaughter/lab-tests/',
});

export const usePostShift = shiftsCrud.makeAction<
  { output_warehouse: string; source_warehouse: string },
  unknown
>((id) => `/api/slaughter/shifts/${id}/post_shift/`);

export const useReverseShift = shiftsCrud.makeAction<
  { reason?: string },
  unknown
>((id) => `/api/slaughter/shifts/${id}/reverse/`);

export interface BulkYieldRow {
  nomenclature: string;
  quantity: string;
  share_percent?: string | null;
  notes?: string;
}

export function useBulkYields() {
  const qc = useQueryClient();
  return useMutation<
    SlaughterShift,
    ApiError,
    { shiftId: string; yields: BulkYieldRow[]; replaceExisting?: boolean }
  >({
    mutationFn: ({ shiftId, yields, replaceExisting }) =>
      apiFetch<SlaughterShift>(
        `/api/slaughter/shifts/${shiftId}/bulk-yields/`,
        {
          method: 'POST',
          body: { yields, replace_existing: replaceExisting ?? false },
        },
      ),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ['slaughter'], refetchType: 'all' }),
      ]);
    },
  });
}

// ── KPI Stats / Timeline ───────────────────────────────────────────────

export function useSlaughterStats(shiftId: string | null | undefined) {
  return useQuery<SlaughterStats, ApiError>({
    queryKey: ['slaughter', 'stats', shiftId],
    enabled: Boolean(shiftId),
    queryFn: () =>
      apiFetch<SlaughterStats>(`/api/slaughter/shifts/${shiftId}/stats/`),
    staleTime: 30_000,
  });
}

interface TimelineResponse {
  events: SlaughterTimelineEvent[];
  counts: Record<string, number>;
}

export function useSlaughterTimeline(shiftId: string | null | undefined) {
  return useQuery<TimelineResponse, ApiError>({
    queryKey: ['slaughter', 'timeline', shiftId],
    enabled: Boolean(shiftId),
    queryFn: () =>
      apiFetch<TimelineResponse>(`/api/slaughter/shifts/${shiftId}/timeline/`),
    staleTime: 30_000,
  });
}

// ── Incoming transfers (legacy) ────────────────────────────────────────
//
// Раньше slaughter имел свой endpoint `/api/slaughter/shifts/incoming/`
// и локальную IncomingTransfersPanel. Теперь страница использует общий
// компонент `@/components/IncomingTransfersPanel` с универсальным
// endpoint `/api/transfers/incoming/?to_module=slaughter`. Хуки удалены.
