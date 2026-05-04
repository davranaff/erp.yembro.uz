'use client';

import { useQuery } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import { asList } from '@/lib/paginated';
import type { Paginated } from '@/types/auth';

export interface RolePermission {
  id: string;
  role: string;
  module: string;
  level: 'none' | 'r' | 'rw' | 'admin';
  module_code: string;
  module_name: string;
}

export interface Role {
  id: string;
  code: string;
  name: string;
  description: string;
  is_system: boolean;
  is_active: boolean;
  permissions: RolePermission[];
}

export function useRoles() {
  return useQuery<Role[], ApiError>({
    queryKey: ['rbac', 'roles'],
    queryFn: async () => {
      const data = await apiFetch<Paginated<Role> | Role[]>(
        '/api/rbac/roles/?is_active=true',
      );
      return asList(data);
    },
    staleTime: 60_000,
  });
}
