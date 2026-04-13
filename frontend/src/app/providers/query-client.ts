import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query';

import { isApiError } from '@/shared/api/error-handler';
import {
  getErrorRetryable,
  mutationDefaultConfig,
  queryDefaultConfig,
  type MutationErrorContext,
} from '@/shared/api/react-query';
import { clearAuthSession } from '@/shared/auth';
import { ROUTES } from '@/shared/config/routes';

const redirectToLogin = (): void => {
  if (typeof window === 'undefined') {
    return;
  }

  if (window.location.pathname !== ROUTES.login) {
    window.location.replace(ROUTES.login);
  }
};

const handleUnauthorized = (error: unknown): void => {
  if (!isApiError(error) || error.status !== 401) {
    return;
  }

  clearAuthSession();
  redirectToLogin();
};

const queryCache = new QueryCache({
  onError: (error, query) => {
    handleUnauthorized(error);

    if (!import.meta.env.DEV) {
      return;
    }

    const message = isApiError(error)
      ? error.message
      : error instanceof Error
        ? error.message
        : 'Unknown query error';

    console.error('[react-query]', { queryKey: query.queryHash, message, error });
  },
});

const mutationCache = new MutationCache({
  onError: (_error, _variables, _context, mutation) => {
    handleUnauthorized(_error);

    if (!import.meta.env.DEV) {
      return;
    }

    console.error('[react-query:m]', {
      mutationKey: mutation.options.mutationKey,
      message: 'Mutation failed',
    });
  },
});

export const queryClient = new QueryClient({
  queryCache,
  mutationCache,
  defaultOptions: {
    queries: {
      ...queryDefaultConfig,
      retry: getErrorRetryable,
    },
    mutations: {
      ...mutationDefaultConfig,
      retry: (failureCount, error: MutationErrorContext) => getErrorRetryable(failureCount, error),
    },
  },
});
