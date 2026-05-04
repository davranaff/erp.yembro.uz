'use client';

import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import { asList } from '@/lib/paginated';
import type {
  MembershipRow,
  ModuleLevel,
  Paginated,
  RoleFull,
  UserRoleAssignment,
} from '@/types/auth';

// ─── Roles ────────────────────────────────────────────────────────────────

const ROLES_KEY = ['rbac', 'roles'] as const;

export function useRolesCrud() {
  return useQuery<RoleFull[], ApiError>({
    queryKey: ROLES_KEY,
    queryFn: async () => {
      const data = await apiFetch<Paginated<RoleFull> | RoleFull[]>(
        '/api/rbac/roles/',
      );
      return asList(data);
    },
    staleTime: 30_000,
  });
}

interface CreateRoleVars {
  code: string;
  name: string;
  description?: string;
  is_active?: boolean;
}

export function useCreateRole() {
  const qc = useQueryClient();
  return useMutation<RoleFull, ApiError, CreateRoleVars>({
    mutationFn: (vars) =>
      apiFetch<RoleFull>('/api/rbac/roles/', {
        method: 'POST',
        body: vars,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ROLES_KEY });
    },
  });
}

interface UpdateRoleVars {
  id: string;
  patch: Partial<Pick<RoleFull, 'name' | 'description' | 'is_active'>>;
}

export function useUpdateRole() {
  const qc = useQueryClient();
  return useMutation<RoleFull, ApiError, UpdateRoleVars>({
    mutationFn: ({ id, patch }) =>
      apiFetch<RoleFull>(`/api/rbac/roles/${id}/`, {
        method: 'PATCH',
        body: patch,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ROLES_KEY });
    },
  });
}

export function useDeleteRole() {
  const qc = useQueryClient();
  return useMutation<void, ApiError, string>({
    mutationFn: (id) =>
      apiFetch<void>(`/api/rbac/roles/${id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ROLES_KEY });
    },
  });
}

// ─── RolePermission (матрица role × module) ──────────────────────────────

interface UpsertPermissionVars {
  role: string;
  module: string;
  level: ModuleLevel;
  existing_id?: string | null;
}

export function useUpsertRolePermission() {
  const qc = useQueryClient();
  return useMutation<unknown, ApiError, UpsertPermissionVars>({
    mutationFn: async ({ role, module, level, existing_id }) => {
      if (existing_id) {
        return apiFetch(`/api/rbac/role-permissions/${existing_id}/`, {
          method: 'PATCH',
          body: { level },
        });
      }
      return apiFetch('/api/rbac/role-permissions/', {
        method: 'POST',
        body: { role, module, level },
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ROLES_KEY });
    },
  });
}

// ─── UserRole (назначение роли membership-у) ─────────────────────────────

const USER_ROLES_KEY = ['rbac', 'user-roles'] as const;

export function useUserRoles(membershipId?: string) {
  return useQuery<UserRoleAssignment[], ApiError>({
    queryKey: [...USER_ROLES_KEY, membershipId ?? 'all'],
    queryFn: async () => {
      const path = membershipId
        ? `/api/rbac/user-roles/?membership=${membershipId}`
        : '/api/rbac/user-roles/';
      const data = await apiFetch<Paginated<UserRoleAssignment> | UserRoleAssignment[]>(path);
      return asList(data);
    },
    staleTime: 30_000,
  });
}

interface AssignRoleVars {
  membership: string;
  role: string;
}

export function useAssignUserRole() {
  const qc = useQueryClient();
  return useMutation<UserRoleAssignment, ApiError, AssignRoleVars>({
    mutationFn: (vars) =>
      apiFetch<UserRoleAssignment>('/api/rbac/user-roles/', {
        method: 'POST',
        body: vars,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: USER_ROLES_KEY });
      qc.invalidateQueries({ queryKey: ['me'] });
    },
  });
}

export function useRemoveUserRole() {
  const qc = useQueryClient();
  return useMutation<void, ApiError, string>({
    mutationFn: (id) =>
      apiFetch<void>(`/api/rbac/user-roles/${id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: USER_ROLES_KEY });
      qc.invalidateQueries({ queryKey: ['me'] });
    },
  });
}

// ─── User Module Access Override (per-user исключения из ролей) ──────────

const OVERRIDES_KEY = ['rbac', 'overrides'] as const;

export interface UserModuleAccessOverride {
  id: string;
  membership: string;
  module: string;
  module_code: string | null;
  level: ModuleLevel;
  reason: string;
  user_email: string | null;
  created_at: string;
  updated_at: string;
}

export function useUserOverrides(membershipId?: string) {
  return useQuery<UserModuleAccessOverride[], ApiError>({
    queryKey: [...OVERRIDES_KEY, membershipId ?? 'all'],
    queryFn: async () => {
      const path = membershipId
        ? `/api/rbac/overrides/?membership=${membershipId}`
        : '/api/rbac/overrides/';
      const data = await apiFetch<
        Paginated<UserModuleAccessOverride> | UserModuleAccessOverride[]
      >(path);
      return asList(data);
    },
    staleTime: 30_000,
  });
}

interface CreateOverrideVars {
  membership: string;
  module: string;
  level: ModuleLevel;
  reason?: string;
}

export function useCreateOverride() {
  const qc = useQueryClient();
  return useMutation<UserModuleAccessOverride, ApiError, CreateOverrideVars>({
    mutationFn: (vars) =>
      apiFetch<UserModuleAccessOverride>('/api/rbac/overrides/', {
        method: 'POST',
        body: vars,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: OVERRIDES_KEY });
    },
  });
}

export function useUpdateOverride() {
  const qc = useQueryClient();
  return useMutation<
    UserModuleAccessOverride,
    ApiError,
    { id: string; patch: Partial<CreateOverrideVars> }
  >({
    mutationFn: ({ id, patch }) =>
      apiFetch<UserModuleAccessOverride>(`/api/rbac/overrides/${id}/`, {
        method: 'PATCH',
        body: patch,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: OVERRIDES_KEY });
    },
  });
}

export function useDeleteOverride() {
  const qc = useQueryClient();
  return useMutation<void, ApiError, string>({
    mutationFn: (id) =>
      apiFetch<void>(`/api/rbac/overrides/${id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: OVERRIDES_KEY });
    },
  });
}

// ─── Memberships (для селектора пользователя) ────────────────────────────

export function useMemberships() {
  return useQuery<MembershipRow[], ApiError>({
    queryKey: ['memberships'],
    queryFn: async () => {
      const data = await apiFetch<Paginated<MembershipRow> | MembershipRow[]>(
        '/api/memberships/?is_active=true',
      );
      return asList(data);
    },
    staleTime: 60_000,
  });
}
