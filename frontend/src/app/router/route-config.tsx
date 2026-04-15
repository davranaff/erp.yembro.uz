import { Navigate, type RouteObject } from 'react-router-dom';

import { AppLayout } from '@/app/layouts/app-layout';
import { PublicLayout } from '@/app/layouts/public-layout';
import { RootLayout } from '@/app/layouts/root-layout';
import { AuthenticatedRoute, GuestRoute } from '@/app/router/guards';
import {
  AuditLogPage,
  DashboardPage,
  LoginPage,
  NotFoundPage,
  PublicMedicineBatchPage,
  RoleManagementPage,
  RootRedirect,
} from '@/app/router/pages';
import { ModuleCrudPage } from '@/app/router/pages/module-crud-page';
import { SettingsPage } from '@/app/router/pages/settings-page';
import { ROUTES } from '@/shared/config/routes';

export const routeConfig: RouteObject[] = [
  {
    path: ROUTES.home,
    element: <RootLayout />,
    children: [
      { index: true, element: <RootRedirect /> },
      {
        path: ROUTES.login.slice(1),
        element: (
          <GuestRoute
            element={
              <PublicLayout>
                <LoginPage />
              </PublicLayout>
            }
          />
        ),
      },
      {
        path: ROUTES.publicMedicineBatch().slice(1),
        element: (
          <PublicLayout>
            <PublicMedicineBatchPage />
          </PublicLayout>
        ),
      },
      {
        path: ROUTES.dashboard.slice(1),
        element: (
          <AuthenticatedRoute
            element={
              <AppLayout>
                <DashboardPage />
              </AppLayout>
            }
          />
        ),
      },
      {
        path: ROUTES.dashboardModule(':moduleKey').slice(1),
        element: (
          <AuthenticatedRoute
            element={
              <AppLayout>
                <ModuleCrudPage />
              </AppLayout>
            }
          />
        ),
      },
      {
        path: ROUTES.settings.slice(1),
        element: (
          <AuthenticatedRoute
            element={
              <AppLayout>
                <SettingsPage />
              </AppLayout>
            }
          />
        ),
      },
      {
        path: ROUTES.roleManagement.slice(1),
        element: (
          <AuthenticatedRoute
            element={
              <AppLayout>
                <RoleManagementPage />
              </AppLayout>
            }
          />
        ),
      },
      {
        path: ROUTES.audit.slice(1),
        element: (
          <AuthenticatedRoute
            element={
              <AppLayout>
                <AuditLogPage />
              </AppLayout>
            }
          />
        ),
      },
      {
        path: ROUTES.app.slice(1),
        element: <AuthenticatedRoute element={<Navigate to={ROUTES.dashboard} replace />} />,
      },
      {
        path: ROUTES.notFound,
        element: <NotFoundPage />,
      },
    ],
  },
];
