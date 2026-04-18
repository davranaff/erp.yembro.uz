import { z } from 'zod';

import { env } from '@/env';

import { api } from './client';

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

export type AuthLoginRequest = z.infer<typeof authLoginRequestSchema>;
export type AuthLoginResponse = z.infer<typeof authLoginResponseSchema>;
export type AuthProfile = z.infer<typeof authProfileSchema>;

export async function loginWithCredentials(payload: AuthLoginRequest): Promise<AuthLoginResponse> {
  const data = await api.post<unknown>(env.authLoginEndpoint, payload, { skipAuth: true });
  return authLoginResponseSchema.parse(data);
}

export async function getMyProfile(): Promise<AuthProfile> {
  const data = await api.get<unknown>(env.authProfileEndpoint);
  return authProfileSchema.parse(data);
}
