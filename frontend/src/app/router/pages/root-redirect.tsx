import { Navigate } from 'react-router-dom';

import { RouteStatusScreen } from '@/app/router/ui/route-status-screen';
import {
  canAccessDashboard,
  canAccessRoleManagement,
  canReadAuditLogs,
  getFirstAccessibleModuleKey,
  useAuthStore,
} from '@/shared/auth';
import { ROUTES } from '@/shared/config/routes';
import { useI18n } from '@/shared/i18n';
import { isValidUuid } from '@/shared/lib/uuid';
import { useWorkspaceStore } from '@/shared/workspace';

export function RootRedirect() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const isInitialized = useAuthStore((state) => state.isInitialized);
  const session = useAuthStore((state) => state.session);
  const workspaceStatus = useWorkspaceStore((state) => state.status);
  const workspaceError = useWorkspaceStore((state) => state.error);
  const workspaceLoaded = useWorkspaceStore((state) => state.isLoaded);
  const requestWorkspaceReload = useWorkspaceStore((state) => state.requestReload);
  const { t } = useI18n();

  if (!isInitialized) {
    return (
      <RouteStatusScreen
        label={t('route.initLabel')}
        title={t('route.initTitle')}
        description={t('route.initDescription')}
      />
    );
  }

  if (!isAuthenticated) {
    return <Navigate to={ROUTES.login} replace />;
  }

  if (!workspaceLoaded && workspaceStatus === 'error') {
    return (
      <RouteStatusScreen
        label={t('route.sessionLabel')}
        title={t(
          'route.workspaceErrorTitle',
          undefined,
          'Не удалось подготовить рабочее пространство',
        )}
        description={
          workspaceError ||
          t(
            'route.workspaceErrorDescription',
            undefined,
            'Не удалось загрузить конфигурацию модулей и прав. Повторите попытку.',
          )
        }
        status="error"
        actionLabel={t('common.retry')}
        onAction={requestWorkspaceReload}
      />
    );
  }

  if (!workspaceLoaded) {
    return (
      <RouteStatusScreen
        label={t('route.sessionLabel')}
        title={t('route.sessionTitle')}
        description={t('route.sessionDescription')}
      />
    );
  }

  const sessionRoles = session?.roles ?? [];
  const sessionPermissions = session?.permissions ?? [];
  const sessionDepartmentModuleKey = session?.departmentModuleKey ?? null;
  const sessionDepartmentId = isValidUuid(session?.departmentId)
    ? (session?.departmentId ?? null)
    : null;
  const firstAccessibleModuleKey = getFirstAccessibleModuleKey(
    sessionRoles,
    sessionPermissions,
    sessionDepartmentModuleKey,
  );
  const authenticatedTarget = canAccessDashboard(sessionRoles, sessionPermissions)
    ? ROUTES.dashboard
    : firstAccessibleModuleKey
      ? ROUTES.dashboardModuleForDepartment(
          firstAccessibleModuleKey,
          sessionDepartmentModuleKey === firstAccessibleModuleKey ? sessionDepartmentId : null,
        )
      : canAccessRoleManagement(sessionRoles, sessionPermissions)
        ? ROUTES.roleManagement
        : canReadAuditLogs(sessionRoles, sessionPermissions)
          ? ROUTES.audit
          : ROUTES.settings;

  return <Navigate to={authenticatedTarget} replace />;
}
