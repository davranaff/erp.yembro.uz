import { Navigate, Route, Routes, useLocation } from 'react-router-dom';

import { LoginPage } from '@/features/auth/login-page';
import { ClientsPage } from '@/features/clients/clients-page';
import { DashboardPage } from '@/features/dashboard/dashboard-page';
import { AppShell } from '@/features/shell/app-shell';
import { PlaceholderPage } from '@/features/shell/placeholder-page';
import { useAuthStore } from '@/shared/auth/auth-store';
import { useI18n } from '@/shared/i18n/i18n';

function Protected({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const isInitialized = useAuthStore((s) => s.isInitialized);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  if (!isInitialized) {
    return (
      <div className="flex h-screen items-center justify-center bg-bg text-xs text-ink-muted">
        …
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return <>{children}</>;
}

function Guest({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  if (isAuthenticated) return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}

function FinancePage() {
  const { t } = useI18n();
  return <PlaceholderPage title={t('nav.finance')} />;
}

function HrPage() {
  const { t } = useI18n();
  return <PlaceholderPage title={t('nav.hr')} />;
}

function InventoryPage() {
  const { t } = useI18n();
  return <PlaceholderPage title={t('nav.inventory')} />;
}

function SettingsPage() {
  const { t } = useI18n();
  return <PlaceholderPage title={t('nav.settings')} />;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <Guest>
            <LoginPage />
          </Guest>
        }
      />
      <Route
        element={
          <Protected>
            <AppShell />
          </Protected>
        }
      >
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/clients" element={<ClientsPage />} />
        <Route path="/finance" element={<FinancePage />} />
        <Route path="/hr" element={<HrPage />} />
        <Route path="/inventory" element={<InventoryPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
