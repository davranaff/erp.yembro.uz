import { useQuery } from '@tanstack/react-query';

import { apiFetch, ApiError } from '@/lib/api';

export type NotificationChannel = 'sms' | 'tg';

export interface NotificationItem {
  channel: NotificationChannel;
  id: string;
  created_at: string;
  phone: string | null;
  chat_id: number | null;
  counterparty_id: string | null;
  counterparty_name: string | null;
  source: string;
  purpose: string;
  text: string;
  status: string;
  error_msg: string;
  provider_message_id: string;
  sent_at: string | null;
  delivered_at: string | null;
}

export interface NotificationsResponse {
  results: NotificationItem[];
  count: number;
  limit: number;
  offset: number;
}

export interface NotificationsFilter {
  channel?: 'sms' | 'tg' | '';
  counterparty?: string;
  source?: string;
  status?: string;
  phone?: string;
  from?: string;
  to?: string;
  limit?: number;
  offset?: number;
}

export function useNotifications(filter: NotificationsFilter = {}) {
  const qs = new URLSearchParams();
  if (filter.channel) qs.set('channel', filter.channel);
  if (filter.counterparty) qs.set('counterparty', filter.counterparty);
  if (filter.source) qs.set('source', filter.source);
  if (filter.status) qs.set('status', filter.status);
  if (filter.phone) qs.set('phone', filter.phone);
  if (filter.from) qs.set('from', filter.from);
  if (filter.to) qs.set('to', filter.to);
  if (filter.limit != null) qs.set('limit', String(filter.limit));
  if (filter.offset != null) qs.set('offset', String(filter.offset));

  const query = qs.toString();
  const url = `/api/notifications/${query ? `?${query}` : ''}`;

  return useQuery<NotificationsResponse, ApiError>({
    queryKey: ['notifications', filter],
    queryFn: () => apiFetch<NotificationsResponse>(url),
    staleTime: 10_000,
  });
}
