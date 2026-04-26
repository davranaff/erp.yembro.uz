'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import { makeCrud } from '@/lib/crudFactory';
import type {
  VetDrug,
  VetStockBatch,
  VetTreatmentLog,
} from '@/types/auth';

export const drugsCrud = makeCrud<VetDrug>({
  key: ['vet', 'drugs'],
  path: '/api/vet/drugs/',
  ordering: 'nomenclature__sku',
});

export const stockBatchesCrud = makeCrud<VetStockBatch>({
  key: ['vet', 'stock-batches'],
  path: '/api/vet/stock-batches/',
  ordering: '-received_date',
});

export const treatmentsCrud = makeCrud<VetTreatmentLog>({
  key: ['vet', 'treatments'],
  path: '/api/vet/treatments/',
  ordering: '-treatment_date',
});

// POST /api/vet/stock-batches/receive/ (detail=False)
export function useReceiveVetStock() {
  const qc = useQueryClient();
  return useMutation<VetStockBatch, ApiError, {
    drug: string;
    lot_number: string;
    warehouse: string;
    supplier: string;
    purchase: string;  // теперь required
    received_date: string;
    expiration_date: string;
    quantity: string;
    unit: string;
    price_per_unit_uzs: string;
    quarantine_until?: string;
    barcode?: string;
    notes?: string;
  }>({
    mutationFn: (body) =>
      apiFetch<VetStockBatch>('/api/vet/stock-batches/receive/', {
        method: 'POST',
        body,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['vet', 'stock-batches'] }),
  });
}

export const useReleaseQuarantine = stockBatchesCrud.makeAction<void, unknown>(
  (id) => `/api/vet/stock-batches/${id}/release-quarantine/`,
);

/** POST /api/vet/stock-batches/{id}/recall/ — отзыв лота с реверсом всех лечений. */
export function useRecallStockBatch() {
  const qc = useQueryClient();
  return useMutation<VetStockBatch, ApiError, { id: string; reason: string }>({
    mutationFn: ({ id, reason }) =>
      apiFetch<VetStockBatch>(`/api/vet/stock-batches/${id}/recall/`, {
        method: 'POST',
        body: { reason },
      }),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ['vet'], refetchType: 'all' }),
        qc.invalidateQueries({ queryKey: ['batches'], refetchType: 'all' }),
      ]);
    },
  });
}

/** GET /api/vet/stock-batches/by-barcode/?barcode=X. */
export function useStockBatchByBarcode(barcode: string | null | undefined) {
  return useQuery<VetStockBatch | null, ApiError>({
    queryKey: ['vet', 'stock-batches', 'by-barcode', barcode ?? ''],
    enabled: Boolean(barcode),
    queryFn: async () => {
      try {
        return await apiFetch<VetStockBatch>(
          `/api/vet/stock-batches/by-barcode/?barcode=${encodeURIComponent(barcode!)}`,
        );
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return null;
        throw e;
      }
    },
    staleTime: 30_000,
  });
}

export const useApplyTreatment = treatmentsCrud.makeAction<void, unknown>(
  (id) => `/api/vet/treatments/${id}/apply/`,
);

/** POST /api/vet/treatments/{id}/cancel/ — отмена лечения с реверсом JE. */
export function useCancelTreatment() {
  const qc = useQueryClient();
  return useMutation<VetTreatmentLog, ApiError, { id: string; reason: string }>({
    mutationFn: ({ id, reason }) =>
      apiFetch<VetTreatmentLog>(`/api/vet/treatments/${id}/cancel/`, {
        method: 'POST',
        body: { reason },
      }),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ['vet'], refetchType: 'all' }),
        qc.invalidateQueries({ queryKey: ['batches'], refetchType: 'all' }),
      ]);
    },
  });
}

/** GET /api/vet/treatments/timeline/?batch=<uuid>|herd=<uuid>. */
export function useTreatmentsTimeline(opts: { batch?: string; herd?: string }) {
  const qsParts: string[] = [];
  if (opts.batch) qsParts.push(`batch=${encodeURIComponent(opts.batch)}`);
  if (opts.herd) qsParts.push(`herd=${encodeURIComponent(opts.herd)}`);
  const qs = qsParts.join('&');
  return useQuery<VetTreatmentLog[], ApiError>({
    queryKey: ['vet', 'treatments', 'timeline', qs],
    enabled: qsParts.length > 0,
    queryFn: () => apiFetch<VetTreatmentLog[]>(`/api/vet/treatments/timeline/?${qs}`),
    staleTime: 30_000,
  });
}
