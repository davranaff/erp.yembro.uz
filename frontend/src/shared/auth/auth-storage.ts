import { isValidUuid } from '@/shared/lib/uuid';

import { type AuthCredentials, type AuthSession } from './types';

const AUTH_SESSION_STORAGE_KEY = 'frontend:auth-session';

const isBrowser = typeof window !== 'undefined';

const normalizeArray = (value: unknown): string[] =>
  Array.isArray(value)
    ? value
        .map((item) => String(item).trim().toLowerCase())
        .filter((item): item is string => item.length > 0)
        .filter((valueItem, index, list) => list.indexOf(valueItem) === index)
    : [];

const normalizeDepartmentId = (value: unknown): string | null | undefined => {
  if (typeof value === 'string') {
    const next = value.trim();
    return isValidUuid(next) ? next : null;
  }

  return value === null ? null : undefined;
};

const normalizeSession = (value: Record<string, unknown>): AuthSession | null => {
  if (typeof value.employeeId !== 'string' || !value.employeeId.trim()) {
    return null;
  }

  const roles = normalizeArray(value.roles);
  const permissions = normalizeArray(value.permissions);

  return {
    employeeId: value.employeeId.trim(),
    organizationId:
      typeof value.organizationId === 'string' ? value.organizationId.trim() : undefined,
    departmentId: normalizeDepartmentId(value.departmentId),
    departmentModuleKey:
      typeof value.departmentModuleKey === 'string'
        ? value.departmentModuleKey.trim()
        : value.departmentModuleKey === null
          ? null
          : undefined,
    headsAnyDepartment: value.headsAnyDepartment === true,
    username: typeof value.username === 'string' ? value.username.trim() : undefined,
    roles,
    permissions,
    accessToken: typeof value.accessToken === 'string' ? value.accessToken : undefined,
    refreshToken: typeof value.refreshToken === 'string' ? value.refreshToken : undefined,
    expiresAt: typeof value.expiresAt === 'string' ? value.expiresAt : undefined,
  };
};

export const getAuthHeaders = (session: AuthSession | null): Record<string, string> => {
  if (!session) {
    return {};
  }

  const headers: Record<string, string> = {};

  if (typeof session.accessToken === 'string') {
    const token = session.accessToken.trim();

    if (token.length > 0) {
      headers.Authorization = token.startsWith('Bearer ') ? token : `Bearer ${token}`;
    }
  }

  return headers;
};

export const loadAuthSession = (): AuthSession | null => {
  if (!isBrowser) {
    return null;
  }

  const raw = localStorage.getItem(AUTH_SESSION_STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object') {
      return normalizeSession(parsed as Record<string, unknown>);
    }
  } catch {
    localStorage.removeItem(AUTH_SESSION_STORAGE_KEY);
  }

  return null;
};

export const saveAuthSession = (session: AuthSession | null): void => {
  if (!isBrowser) {
    return;
  }

  if (session === null) {
    localStorage.removeItem(AUTH_SESSION_STORAGE_KEY);
    return;
  }

  localStorage.setItem(
    AUTH_SESSION_STORAGE_KEY,
    JSON.stringify({
      employeeId: session.employeeId,
      organizationId: session.organizationId,
      departmentId: session.departmentId,
      departmentModuleKey: session.departmentModuleKey,
      headsAnyDepartment: session.headsAnyDepartment === true,
      username: session.username,
      roles: session.roles,
      permissions: session.permissions,
      accessToken: session.accessToken,
      refreshToken: session.refreshToken,
      expiresAt: session.expiresAt,
    }),
  );
};

export const clearAuthSession = (): void => {
  saveAuthSession(null);
};

export const parseAuthHeaders = (): Record<string, string> => getAuthHeaders(loadAuthSession());

export const hydrateSession = (session: AuthCredentials): AuthSession => ({
  employeeId: session.employeeId.trim(),
  organizationId:
    typeof session.organizationId === 'string' ? session.organizationId.trim() : undefined,
  departmentId: normalizeDepartmentId(session.departmentId),
  departmentModuleKey:
    typeof session.departmentModuleKey === 'string'
      ? session.departmentModuleKey.trim()
      : session.departmentModuleKey === null
        ? null
        : undefined,
  headsAnyDepartment: session.headsAnyDepartment === true,
  username: typeof session.username === 'string' ? session.username.trim() : undefined,
  roles: normalizeArray(session.roles),
  permissions: normalizeArray(session.permissions),
  accessToken: session.accessToken,
  refreshToken: session.refreshToken,
  expiresAt: session.expiresAt,
});
