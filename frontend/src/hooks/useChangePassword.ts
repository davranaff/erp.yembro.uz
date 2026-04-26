'use client';

import { useMutation } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';

interface ChangePasswordVars {
  old_password: string;
  new_password: string;
}

interface Result {
  ok: true;
}

/**
 * POST /api/users/me/change-password/ — смена пароля.
 * Bekend сам валидирует старый пароль и силу нового; ошибки приходят как 400.
 */
export function useChangePassword() {
  return useMutation<Result, ApiError, ChangePasswordVars>({
    mutationFn: (vars) =>
      apiFetch<Result>('/api/users/me/change-password/', {
        method: 'POST',
        body: vars,
        skipOrg: true,
      }),
  });
}
