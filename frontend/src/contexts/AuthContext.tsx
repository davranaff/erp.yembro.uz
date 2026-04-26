'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import {
  ActiveOrg,
  clearAllAuth,
  readOrgCookie,
  writeOrgCookie,
} from '@/lib/tokens';
import { LEVEL_ORDER, ModuleLevel, User } from '@/types/auth';
import { useUser } from '@/hooks/useUser';

interface AuthContextValue {
  user: User | null | undefined;
  isLoading: boolean;
  isError: boolean;
  org: ActiveOrg | null;
  setOrg: (org: ActiveOrg) => void;
  permissions: Record<string, ModuleLevel>;
  hasLevel: (module: string, min?: ModuleLevel) => boolean;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { data: user, isLoading, isError } = useUser();
  const [org, setOrgState] = useState<ActiveOrg | null>(() => readOrgCookie());
  const queryClient = useQueryClient();

  // Сихронизируемся с cookie при монтировании (на случай SSR-mismatch).
  useEffect(() => {
    const stored = readOrgCookie();
    if (stored && (!org || stored.code !== org.code)) {
      setOrgState(stored);
    }
  }, [org]);

  const setOrg = useCallback((next: ActiveOrg) => {
    writeOrgCookie(next);
    setOrgState(next);
    // Невалидируем все запросы, зависящие от X-Organization-Code.
    queryClient.invalidateQueries();
  }, [queryClient]);

  const permissions = useMemo<Record<string, ModuleLevel>>(() => {
    if (!user || !org) return {};
    const m = user.memberships.find((x) => x.organization.code === org.code);
    return m?.module_permissions ?? {};
  }, [user, org]);

  const hasLevel = useCallback(
    (module: string, min: ModuleLevel = 'r'): boolean => {
      const actual = permissions[module] ?? 'none';
      return LEVEL_ORDER[actual] >= LEVEL_ORDER[min];
    },
    [permissions],
  );

  const logout = useCallback(() => {
    clearAllAuth();
    queryClient.clear();
    if (typeof window !== 'undefined') {
      window.location.assign('/login');
    }
  }, [queryClient]);

  const value: AuthContextValue = {
    user: user ?? null,
    isLoading,
    isError,
    org,
    setOrg,
    permissions,
    hasLevel,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used inside <AuthProvider>');
  }
  return ctx;
}
