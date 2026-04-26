'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import { clearAllAuth, setTokens } from '@/lib/tokens';
import { TokenPair } from '@/types/auth';

import { ME_QUERY_KEY } from './useUser';

interface LoginVars {
  email: string;
  password: string;
}

/**
 * POST /api/auth/token/ — обмен email/password на JWT-пару.
 * При успехе токены кладутся в localStorage и инвалидируется кэш ['me'].
 */
export function useLogin() {
  const queryClient = useQueryClient();

  return useMutation<TokenPair, ApiError, LoginVars>({
    mutationFn: async ({ email, password }) => {
      const tokens = await apiFetch<TokenPair>('/api/auth/token/', {
        method: 'POST',
        body: { email, password },
        skipAuth: true,
        skipOrg: true,
      });
      setTokens(tokens.access, tokens.refresh);
      return tokens;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ME_QUERY_KEY });
    },
  });
}

/**
 * Локальный logout: чистим токены + cookie + кэш React Query, редирект на /login.
 * (Backend blacklist не используется — refresh-tokens живут до TTL.)
 */
export function useLogout() {
  const queryClient = useQueryClient();
  return () => {
    clearAllAuth();
    queryClient.clear();
    if (typeof window !== 'undefined') {
      window.location.assign('/login');
    }
  };
}
