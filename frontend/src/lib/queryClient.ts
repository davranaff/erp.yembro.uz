import { QueryClient } from '@tanstack/react-query';

import { ApiError } from './api';

/**
 * Создаёт новый QueryClient на каждый запрос (для App Router / RSC безопасности).
 * Не реитраить 401/403/404 — они означают «фронт виноват, ретрай не поможет».
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        gcTime: 5 * 60_000,
        refetchOnWindowFocus: false,
        retry: (failureCount, error) => {
          if (error instanceof ApiError) {
            if ([400, 401, 403, 404].includes(error.status)) return false;
          }
          return failureCount < 1;
        },
      },
      mutations: {
        retry: false,
      },
    },
  });
}
