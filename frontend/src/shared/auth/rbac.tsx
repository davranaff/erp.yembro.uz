import { type ReactNode } from 'react';

import { useAuthStore } from './auth-store';

import type { AuthSession } from './types';

type OptionalStringList = readonly string[] | undefined;

export type RbacContext = {
  isAuthenticated: boolean;
  roles: readonly string[];
  permissions: readonly string[];
  session: AuthSession | null;
};

export type RbacAccessCheck = {
  role?: string;
  anyRole?: readonly string[];
  allRoles?: readonly string[];
  permission?: string;
  anyPermission?: readonly string[];
  allPermissions?: readonly string[];
  requireAuthenticated?: boolean;
  predicate?: (context: RbacContext) => boolean;
};

const normalizeValue = (value: string): string => value.trim().toLowerCase();

const normalizeList = (values: OptionalStringList): string[] => {
  if (!values) {
    return [];
  }

  return values.map(normalizeValue).filter((value) => value.length > 0);
};

const hasAnyValue = (
  actualValues: readonly string[],
  requiredValues: OptionalStringList,
): boolean => {
  const normalizedRequired = normalizeList(requiredValues);
  if (normalizedRequired.length === 0) {
    return false;
  }

  const normalizedActual = new Set(normalizeList(actualValues));
  return normalizedRequired.some((requiredValue) => normalizedActual.has(requiredValue));
};

const hasAllValues = (
  actualValues: readonly string[],
  requiredValues: OptionalStringList,
): boolean => {
  const normalizedRequired = normalizeList(requiredValues);
  if (normalizedRequired.length === 0) {
    return true;
  }

  const normalizedActual = new Set(normalizeList(actualValues));
  return normalizedRequired.every((requiredValue) => normalizedActual.has(requiredValue));
};

export const evaluateRbacAccess = (context: RbacContext, check?: RbacAccessCheck): boolean => {
  const requireAuthenticated = check?.requireAuthenticated !== false;
  if (requireAuthenticated && !context.isAuthenticated) {
    return false;
  }

  if (!check) {
    return true;
  }

  if (check.role && !hasAnyValue(context.roles, [check.role])) {
    return false;
  }

  if (check.anyRole && !hasAnyValue(context.roles, check.anyRole)) {
    return false;
  }

  if (check.allRoles && !hasAllValues(context.roles, check.allRoles)) {
    return false;
  }

  if (check.permission && !hasAnyValue(context.permissions, [check.permission])) {
    return false;
  }

  if (check.anyPermission && !hasAnyValue(context.permissions, check.anyPermission)) {
    return false;
  }

  if (check.allPermissions && !hasAllValues(context.permissions, check.allPermissions)) {
    return false;
  }

  if (check.predicate && !check.predicate(context)) {
    return false;
  }

  return true;
};

export const useRbac = () => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const session = useAuthStore((state) => state.session);
  const roles = session?.roles ?? [];
  const permissions = session?.permissions ?? [];
  const context: RbacContext = {
    isAuthenticated,
    roles,
    permissions,
    session,
  };

  return {
    ...context,
    canAccess: (check?: RbacAccessCheck) => evaluateRbacAccess(context, check),
  };
};

type AccessGateProps = {
  access?: RbacAccessCheck;
  fallback?: ReactNode;
  children?: ReactNode;
};

export function AccessGate({ access, fallback = null, children }: AccessGateProps) {
  const { canAccess } = useRbac();
  return canAccess(access) ? <>{children}</> : <>{fallback}</>;
}

type RoleGateProps = {
  role?: string;
  anyOf?: readonly string[];
  allOf?: readonly string[];
  fallback?: ReactNode;
  children?: ReactNode;
};

export function RoleGate({ role, anyOf, allOf, fallback = null, children }: RoleGateProps) {
  return (
    <AccessGate
      access={{
        role,
        anyRole: anyOf,
        allRoles: allOf,
      }}
      fallback={fallback}
    >
      {children}
    </AccessGate>
  );
}

type PermissionGateProps = {
  permission?: string;
  anyOf?: readonly string[];
  allOf?: readonly string[];
  fallback?: ReactNode;
  children?: ReactNode;
};

export function PermissionGate({
  permission,
  anyOf,
  allOf,
  fallback = null,
  children,
}: PermissionGateProps) {
  return (
    <AccessGate
      access={{
        permission,
        anyPermission: anyOf,
        allPermissions: allOf,
      }}
      fallback={fallback}
    >
      {children}
    </AccessGate>
  );
}
