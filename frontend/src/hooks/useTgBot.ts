'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';

export interface TgLink {
  id: string;
  chat_id: number;
  tg_username: string;
  is_active: boolean;
  user: string | null;
  user_email: string | null;
  counterparty: string | null;
  counterparty_name: string | null;
  created_at: string;
}

export interface TgLinkToken {
  id: string;
  token: string;
  expires_at: string;
  used: boolean;
  bot_url: string;
}

export function useTgMyLink() {
  return useQuery<TgLink | null>({
    queryKey: ['tg', 'link', 'me'],
    queryFn: () => apiFetch<TgLink | null>('/api/tg/links/me/'),
    staleTime: 30_000,
  });
}

export function useCreateTgLinkToken(counterpartyId?: string) {
  return useMutation<TgLinkToken, Error>({
    mutationFn: () =>
      apiFetch<TgLinkToken>('/api/tg/link-token/', {
        method: 'POST',
        body: counterpartyId ? { counterparty: counterpartyId } : {},
      }),
  });
}

export function useDisconnectTgLink() {
  const qc = useQueryClient();
  return useMutation<void, Error>({
    mutationFn: () =>
      apiFetch<void>('/api/tg/links/me/', { method: 'DELETE' }) as Promise<void>,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tg', 'link', 'me'] });
    },
  });
}

export function useTgCounterpartyLink(counterpartyId: string | undefined) {
  return useQuery<TgLink | null>({
    queryKey: ['tg', 'link', 'counterparty', counterpartyId],
    queryFn: () => apiFetch<TgLink | null>(`/api/tg/links/counterparty/${counterpartyId}/`),
    enabled: Boolean(counterpartyId),
    staleTime: 30_000,
  });
}

export function useDisconnectCounterpartyTg(counterpartyId: string) {
  const qc = useQueryClient();
  return useMutation<void, Error>({
    mutationFn: () =>
      apiFetch<void>(`/api/tg/links/counterparty/${counterpartyId}/`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tg', 'link', 'counterparty', counterpartyId] });
    },
  });
}

export function useSendDebtReminder() {
  return useMutation<{ queued: boolean }, Error, { sale_order_id: string }>({
    mutationFn: (body) =>
      apiFetch('/api/tg/send-debt-reminder/', {
        method: 'POST',
        body,
      }),
  });
}
