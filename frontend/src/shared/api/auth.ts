import { z } from 'zod';

import { env } from '@/shared/config/env';
import type { TranslateFn } from '@/shared/i18n';

import { apiClient } from './api-client';

const fallbackTranslate: TranslateFn = (key, params, fallback) => {
  if (!fallback) {
    return key;
  }

  if (!params) {
    return fallback;
  }

  return Object.entries(params).reduce((result, [paramKey, value]) => {
    return result.replaceAll(`{${paramKey}}`, String(value));
  }, fallback);
};

export const authLoginRequestSchema = z.object({
  username: z.string().trim().min(1),
  password: z.string().trim().min(1),
});

export const authLoginResponseSchema = z.object({
  employeeId: z.string().trim().min(1),
  organizationId: z.string().trim().min(1),
  departmentId: z.string().trim().nullable().optional(),
  departmentModuleKey: z.string().trim().nullable().optional(),
  headsAnyDepartment: z.boolean(),
  username: z.string().trim().min(1),
  roles: z.array(z.string().trim()),
  permissions: z.array(z.string().trim()),
  accessToken: z.string().trim().optional(),
  refreshToken: z.string().trim().optional(),
  expiresAt: z.string().trim().nullable().optional(),
});

export type AuthLoginRequest = z.infer<typeof authLoginRequestSchema>;
export type AuthLoginResponse = z.infer<typeof authLoginResponseSchema>;

export const authProfileSchema = z.object({
  employeeId: z.string().trim().min(1),
  organizationId: z.string().trim().min(1),
  departmentId: z.string().trim().nullable().optional(),
  departmentModuleKey: z.string().trim().nullable().optional(),
  headsAnyDepartment: z.boolean(),
  username: z.string().trim().min(1),
  firstName: z.string().trim(),
  lastName: z.string().trim(),
  email: z.string().trim().nullable().optional(),
  phone: z.string().trim().nullable().optional(),
  roles: z.array(z.string().trim()),
  permissions: z.array(z.string().trim()),
});

export const createAuthProfileUpdateSchema = (t: TranslateFn) =>
  z
    .object({
      firstName: z.string().trim().min(1, t('settings.validation.firstNameRequired')),
      lastName: z.string().trim().min(1, t('settings.validation.lastNameRequired')),
      email: z
        .string()
        .trim()
        .optional()
        .or(z.literal(''))
        .refine(
          (value) => !value || z.string().email().safeParse(value).success,
          t('settings.validation.invalidEmail'),
        ),
      phone: z.string().trim().optional().or(z.literal('')),
      currentPassword: z.string().optional().or(z.literal('')),
      newPassword: z.string().optional().or(z.literal('')),
      confirmNewPassword: z.string().optional().or(z.literal('')),
    })
    .superRefine((value, context) => {
      const wantsPasswordChange =
        Boolean(value.currentPassword) ||
        Boolean(value.newPassword) ||
        Boolean(value.confirmNewPassword);

      if (!wantsPasswordChange) {
        return;
      }

      if (!value.currentPassword) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          message: t('settings.validation.currentPasswordRequired'),
          path: ['currentPassword'],
        });
      }

      if (!value.newPassword) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          message: t('settings.validation.newPasswordRequired'),
          path: ['newPassword'],
        });
      }

      if (value.newPassword && value.newPassword.length < 8) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          message: t('settings.validation.newPasswordShort'),
          path: ['newPassword'],
        });
      }

      if ((value.confirmNewPassword ?? '') !== (value.newPassword ?? '')) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          message: t('settings.validation.confirmPasswordMismatch'),
          path: ['confirmNewPassword'],
        });
      }
    });

export const authProfileUpdateSchema = createAuthProfileUpdateSchema(fallbackTranslate);

export type AuthProfile = z.infer<typeof authProfileSchema>;
export type AuthProfileUpdate = z.infer<typeof authProfileUpdateSchema>;

export const loginWithCredentials = (payload: AuthLoginRequest) =>
  apiClient.post<AuthLoginResponse, AuthLoginRequest>(
    env.VITE_AUTH_LOGIN_ENDPOINT,
    payload,
    authLoginResponseSchema,
    { skipAuth: true },
  );

export const getMyProfile = () => apiClient.get<AuthProfile>('/auth/me', authProfileSchema);

export const updateMyProfile = (payload: Omit<AuthProfileUpdate, 'confirmNewPassword'>) =>
  apiClient.patch<AuthProfile, Omit<AuthProfileUpdate, 'confirmNewPassword'>>(
    '/auth/me',
    payload,
    authProfileSchema,
  );
