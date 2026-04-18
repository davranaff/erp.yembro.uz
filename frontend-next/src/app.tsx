import { QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';

import { AppRoutes } from '@/app/routes';
import { AuthProvider } from '@/shared/auth/auth-provider';
import { I18nProvider } from '@/shared/i18n/i18n';
import { queryClient } from '@/shared/query/query-client';
import { ToastProvider } from '@/shared/ui/toast';

export function App() {
  return (
    <I18nProvider>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <ToastProvider>
            <BrowserRouter>
              <AppRoutes />
            </BrowserRouter>
          </ToastProvider>
        </AuthProvider>
      </QueryClientProvider>
    </I18nProvider>
  );
}
