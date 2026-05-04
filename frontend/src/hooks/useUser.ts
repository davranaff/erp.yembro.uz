'use client';

import { useQuery } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import { getAccessToken } from '@/lib/tokens';
import { User } from '@/types/auth';

export const ME_QUERY_KEY = ['me'] as const;

/**
 * GET /api/users/me/ — текущий пользователь с memberships и module_permissions.
 *
 * Запрос отправляется только если в localStorage есть access-токен.
 * При 401 апи-клиент сам редиректит на /login, поэтому здесь дополнительной
 * логики не требуется.
 */
export function useUser() {
  return useQuery<User, ApiError>({
    queryKey: ME_QUERY_KEY,
    queryFn: () => apiFetch<User>('/api/users/me/', { skipOrg: true }),
    enabled: typeof window !== 'undefined' && !!getAccessToken(),
    staleTime: 60_000,
  });
}
