'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import { makeCrud } from '@/lib/crudFactory';
import type { SellerDeviceToken } from '@/types/auth';

export const sellerTokensCrud = makeCrud<SellerDeviceToken>({
  key: ['vet', 'seller-tokens'],
  path: '/api/vet/seller-tokens/',
  ordering: '-created_at',
});

/** POST /api/vet/seller-tokens/ — возвращает raw token ОДИН раз. */
export function useCreateSellerToken() {
  const qc = useQueryClient();
  return useMutation<
    SellerDeviceToken,
    ApiError,
    { user: string; label: string }
  >({
    mutationFn: (body) =>
      apiFetch<SellerDeviceToken>('/api/vet/seller-tokens/', {
        method: 'POST',
        body,
      }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ['vet', 'seller-tokens'] }),
  });
}

/** POST /api/vet/seller-tokens/{id}/revoke/ */
export function useRevokeSellerToken() {
  const qc = useQueryClient();
  return useMutation<SellerDeviceToken, ApiError, string>({
    mutationFn: (id) =>
      apiFetch<SellerDeviceToken>(`/api/vet/seller-tokens/${id}/revoke/`, {
        method: 'POST',
      }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ['vet', 'seller-tokens'] }),
  });
}
