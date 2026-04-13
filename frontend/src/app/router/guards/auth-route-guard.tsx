import { type ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import { RouteStatusScreen } from '@/app/router/ui/route-status-screen';
import { useAuthStore } from '@/shared/auth';
import { ROUTES } from '@/shared/config/routes';
import { useI18n } from '@/shared/i18n';

type RouteGuardProps = {
  element: ReactNode;
  redirectTo?: string;
};

type PermissionGuardProps = {
  permission: string;
  redirectTo?: string;
  element: ReactNode;
};

type RoleGuardProps = {
  role: string;
  redirectTo?: string;
  element: ReactNode;
};

export function AuthenticatedRoute({ element, redirectTo }: RouteGuardProps) {
  const location = useLocation();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const isInitialized = useAuthStore((state) => state.isInitialized);
  const { t } = useI18n();

  if (!isInitialized) {
    return (
      <RouteStatusScreen
        label={t('route.sessionLabel')}
        title={t('route.sessionTitle')}
        description={t('route.sessionDescription')}
      />
    );
  }

  if (!isAuthenticated) {
    return (
      <Navigate
        to={redirectTo ?? ROUTES.login}
        replace
        state={{
          from: location.pathname + location.search,
        }}
      />
    );
  }

  return <>{element}</>;
}

export function AuthGuard({ element, redirectTo = ROUTES.login }: RouteGuardProps) {
  return <AuthenticatedRoute redirectTo={redirectTo} element={element} />;
}

export function GuestRoute({ element, redirectTo = ROUTES.dashboard }: RouteGuardProps) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const isInitialized = useAuthStore((state) => state.isInitialized);
  const { t } = useI18n();

  if (!isInitialized) {
    return (
      <RouteStatusScreen
        label={t('route.sessionLabel')}
        title={t('route.sessionTitle')}
        description={t('route.sessionDescription')}
      />
    );
  }

  if (isAuthenticated) {
    return <Navigate to={redirectTo} replace />;
  }

  return <>{element}</>;
}

export function PermissionRoute({
  element,
  permission,
  redirectTo = ROUTES.login,
}: PermissionGuardProps) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const hasPermission = useAuthStore((state) => state.hasPermission);

  if (!isAuthenticated) {
    return <Navigate to={ROUTES.login} replace />;
  }

  if (!hasPermission(permission)) {
    return <Navigate to={redirectTo} replace />;
  }

  return <>{element}</>;
}

export function RoleRoute({ element, role, redirectTo = ROUTES.login }: RoleGuardProps) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const hasRole = useAuthStore((state) => state.hasRole);

  if (!isAuthenticated) {
    return <Navigate to={ROUTES.login} replace />;
  }

  if (!hasRole(role)) {
    return <Navigate to={redirectTo} replace />;
  }

  return <>{element}</>;
}
