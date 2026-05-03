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
  /** Включён ли модуль для текущей организации (org-level toggle в /settings). */
  isModuleEnabled: (module: string) => boolean;
  /** Комбо-проверка для route/nav гейтов: модуль включён И есть RBAC-уровень. */
  hasAccess: (module: string, min?: ModuleLevel) => boolean;
  logout: () => void;
}

// Системные модули, которые backend никогда не блокирует — даже если
// /me не вернул `enabled_modules` (старая сессия), они всё равно считаются
// включёнными. Должны совпадать с SYSTEM_MODULES в backend permissions.py.
const SYSTEM_MODULES: ReadonlySet<string> = new Set(['admin', 'ledger', 'core']);

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

  // Set кодов включённых модулей. Если backend не вернул поле (старая
  // сессия / старый бек) — fallback на «все включены», чтобы не сломать
  // существующих пользователей.
  const enabledModules = useMemo<ReadonlySet<string>>(() => {
    if (!user || !org) return new Set();
    const m = user.memberships.find((x) => x.organization.code === org.code);
    if (!m?.enabled_modules) return new Set();
    return new Set(m.enabled_modules);
  }, [user, org]);

  const hasLevel = useCallback(
    (module: string, min: ModuleLevel = 'r'): boolean => {
      const actual = permissions[module] ?? 'none';
      return LEVEL_ORDER[actual] >= LEVEL_ORDER[min];
    },
    [permissions],
  );

  const isModuleEnabled = useCallback(
    (module: string): boolean => {
      // Системные модули — всегда включены (см. SYSTEM_MODULES в backend).
      if (SYSTEM_MODULES.has(module)) return true;
      // Back-compat: если backend вообще не отдал enabled_modules
      // (пустой Set после загрузки me, но membership найден и valid) —
      // считаем что модуль включён. Это покрывает старые сессии, где
      // `enabled_modules` ещё не было в ответе.
      const m = user?.memberships?.find((x) => x.organization.code === org?.code);
      if (!m || m.enabled_modules === undefined) return true;
      return enabledModules.has(module);
    },
    [enabledModules, user, org],
  );

  const hasAccess = useCallback(
    (module: string, min: ModuleLevel = 'r'): boolean => {
      return isModuleEnabled(module) && hasLevel(module, min);
    },
    [isModuleEnabled, hasLevel],
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
    isModuleEnabled,
    hasAccess,
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
