'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import { User } from '@/types/auth';

import { ME_QUERY_KEY } from './useUser';

interface UpdateVars {
  full_name?: string;
  phone?: string;
}

/**
 * PATCH /api/users/me/ — частичное обновление профиля.
 * После успеха обновляет кэш ['me'].
 */
export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation<User, ApiError, UpdateVars>({
    mutationFn: (vars) =>
      apiFetch<User>('/api/users/me/', {
        method: 'PATCH',
        body: vars,
        skipOrg: true,
      }),
    onSuccess: (data) => {
      queryClient.setQueryData(ME_QUERY_KEY, data);
    },
  });
}
