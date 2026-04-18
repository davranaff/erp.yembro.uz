import { z } from 'zod';

import { api } from './client';

const clientSchema = z
  .object({
    id: z.string(),
    name: z.string().nullable().optional(),
    phone: z.string().nullable().optional(),
    email: z.string().nullable().optional(),
    client_type: z.string().nullable().optional(),
    inn: z.string().nullable().optional(),
    address: z.string().nullable().optional(),
    notes: z.string().nullable().optional(),
    is_active: z.boolean().nullable().optional(),
    created_at: z.string().nullable().optional(),
    updated_at: z.string().nullable().optional(),
  })
  .passthrough();

const clientListResponseSchema = z.object({
  items: z.array(clientSchema),
  total: z.number(),
  limit: z.number().optional(),
  offset: z.number().optional(),
});

export type Client = z.infer<typeof clientSchema>;
export type ClientListResponse = z.infer<typeof clientListResponseSchema>;

export async function listClients(params: {
  search?: string;
  limit?: number;
  offset?: number;
}): Promise<ClientListResponse> {
  const data = await api.get<unknown>('/core/clients', {
    query: {
      search: params.search,
      limit: params.limit ?? 50,
      offset: params.offset ?? 0,
      order_by: '-created_at',
    },
  });
  return clientListResponseSchema.parse(data);
}

export async function getClient(id: string): Promise<Client> {
  const data = await api.get<unknown>(`/core/clients/${id}`);
  return clientSchema.parse(data);
}

export async function updateClient(id: string, payload: Partial<Client>): Promise<Client> {
  const data = await api.put<unknown>(`/core/clients/${id}`, payload as Record<string, unknown>);
  return clientSchema.parse(data);
}
