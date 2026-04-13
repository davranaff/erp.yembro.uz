import { QueryClientProvider } from '@tanstack/react-query';
import { type PropsWithChildren } from 'react';

import { I18nProvider } from '@/shared/i18n';

import { AuthProvider } from './auth-provider';
import { queryClient } from './query-client';

export function AppProviders({ children }: PropsWithChildren) {
  return (
    <QueryClientProvider client={queryClient}>
      <I18nProvider>
        <AuthProvider>{children}</AuthProvider>
      </I18nProvider>
    </QueryClientProvider>
  );
}
