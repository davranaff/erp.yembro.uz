import { z } from 'zod';

import { apiClient } from './api-client';

export const telegramDeepLinkSchema = z.object({
  url: z.string(),
  expires_at: z.string(),
});

export type TelegramDeepLink = z.infer<typeof telegramDeepLinkSchema>;

export const telegramBindingStatusSchema = z.object({
  employees: z.record(z.string(), z.boolean()),
  clients: z.record(z.string(), z.boolean()),
});

export type TelegramBindingStatus = z.infer<typeof telegramBindingStatusSchema>;

export type TelegramDeepLinkTarget = 'self' | 'employee' | 'client';

export const createTelegramDeepLink = (payload: {
  target: TelegramDeepLinkTarget;
  employee_id?: string;
  client_id?: string;
}) =>
  apiClient.post<
    TelegramDeepLink,
    {
      target: TelegramDeepLinkTarget;
      employee_id?: string;
      client_id?: string;
    }
  >('/system/telegram/deep-link', payload, telegramDeepLinkSchema);

export const getTelegramBindingStatus = (params: {
  employeeIds?: string[];
  clientIds?: string[];
}) => {
  const search = new URLSearchParams();
  for (const id of params.employeeIds ?? []) {
    if (id) {
      search.append('employee_ids', id);
    }
  }
  for (const id of params.clientIds ?? []) {
    if (id) {
      search.append('client_ids', id);
    }
  }
  const qs = search.toString();
  return apiClient.get<TelegramBindingStatus>(
    qs ? `/system/telegram/binding-status?${qs}` : '/system/telegram/binding-status',
    telegramBindingStatusSchema,
  );
};
