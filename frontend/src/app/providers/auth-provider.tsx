import { type PropsWithChildren, useEffect } from 'react';

import { getMyProfile } from '@/shared/api/auth';
import { listWorkspaceModules, type WorkspaceModuleConfig } from '@/shared/api/backend-crud';
import { getErrorMessage } from '@/shared/api/react-query';
import { useAuthStore } from '@/shared/auth';
import { useWorkspaceStore } from '@/shared/workspace';

export function AuthProvider({ children }: PropsWithChildren) {
  const initializeAuth = useAuthStore((state) => state.initializeAuth);
  const clearSession = useAuthStore((state) => state.clearSession);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const isInitialized = useAuthStore((state) => state.isInitialized);
  const session = useAuthStore((state) => state.session);
  const sessionAccessToken = session?.accessToken ?? '';
  const sessionEmployeeId = session?.employeeId ?? '';
  const setSession = useAuthStore((state) => state.setSession);
  const workspaceReloadToken = useWorkspaceStore((state) => state.reloadToken);
  const startWorkspaceLoading = useWorkspaceStore((state) => state.startLoading);
  const setWorkspaceModules = useWorkspaceStore((state) => state.setModules);
  const setWorkspaceError = useWorkspaceStore((state) => state.setError);
  const clearWorkspaceModules = useWorkspaceStore((state) => state.clearModules);

  useEffect(() => {
    initializeAuth();
  }, [initializeAuth]);

  useEffect(() => {
    if (isInitialized && isAuthenticated && !session?.accessToken) {
      clearSession();
    }
  }, [clearSession, isAuthenticated, isInitialized, session?.accessToken]);

  useEffect(() => {
    if (!isAuthenticated) {
      clearWorkspaceModules();
    }
  }, [clearWorkspaceModules, isAuthenticated]);

  useEffect(() => {
    if (!isInitialized) {
      return;
    }

    if (!isAuthenticated || !sessionAccessToken || !sessionEmployeeId) {
      clearWorkspaceModules();
      return;
    }

    let isActive = true;
    startWorkspaceLoading();

    void (async () => {
      try {
        const [profile, workspaceResponse] = await Promise.all([
          getMyProfile(),
          listWorkspaceModules(),
        ]);

        if (!isActive) {
          return;
        }

        const currentSession = useAuthStore.getState().session;
        if (
          !currentSession ||
          currentSession.accessToken !== sessionAccessToken ||
          currentSession.employeeId !== sessionEmployeeId
        ) {
          return;
        }

        const nextRoles = [...profile.roles].sort();
        const nextPermissions = [...profile.permissions].sort();
        const currentRoles = [...currentSession.roles].sort();
        const currentPermissions = [...currentSession.permissions].sort();
        const isSameSession =
          currentSession.employeeId === profile.employeeId &&
          (currentSession.organizationId ?? '') === profile.organizationId &&
          (currentSession.departmentId ?? null) === (profile.departmentId ?? null) &&
          (currentSession.departmentModuleKey ?? null) === (profile.departmentModuleKey ?? null) &&
          (currentSession.headsAnyDepartment ?? false) === (profile.headsAnyDepartment ?? false) &&
          (currentSession.username ?? '') === profile.username &&
          currentRoles.join(',') === nextRoles.join(',') &&
          currentPermissions.join(',') === nextPermissions.join(',');

        if (!isSameSession) {
          setSession({
            employeeId: profile.employeeId,
            organizationId: profile.organizationId,
            departmentId: profile.departmentId,
            departmentModuleKey: profile.departmentModuleKey,
            headsAnyDepartment: profile.headsAnyDepartment,
            username: profile.username,
            roles: nextRoles,
            permissions: nextPermissions,
            accessToken: currentSession.accessToken,
            refreshToken: currentSession.refreshToken,
            expiresAt: currentSession.expiresAt,
          });
        }

        const items = (workspaceResponse.items ?? []) as WorkspaceModuleConfig[];
        setWorkspaceModules(items);
      } catch (error) {
        if (!isActive) {
          return;
        }
        setWorkspaceError(getErrorMessage(error));
      }
    })();

    return () => {
      isActive = false;
    };
  }, [
    clearWorkspaceModules,
    isAuthenticated,
    isInitialized,
    sessionAccessToken,
    sessionEmployeeId,
    setSession,
    setWorkspaceError,
    setWorkspaceModules,
    startWorkspaceLoading,
    workspaceReloadToken,
  ]);

  return children;
}
