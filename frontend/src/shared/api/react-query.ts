import {
  useMutation,
  useQuery,
  type MutationFunction,
  type MutationKey,
  type QueryKey,
  type UseMutationOptions,
  type UseMutationResult,
  type UseQueryOptions,
  type UseQueryResult,
} from '@tanstack/react-query';

import { getUnknownErrorLabel } from '@/shared/i18n/fallbacks';

import { isApiError, type ApiError } from './error-handler';

export const queryDefaultConfig = {
  staleTime: 30_000,
  gcTime: 5 * 60_000,
  refetchOnWindowFocus: false,
  refetchOnReconnect: true,
  networkMode: 'online' as const,
} as const;

export const mutationDefaultConfig = {
  retryDelay: 1_000,
  networkMode: 'online' as const,
} as const;

export type MutationErrorContext = unknown;

type RetryableError = Error | ApiError;

const isRetryableStatus = (status: number): boolean => {
  return status === 408 || status === 429 || status === 502 || status >= 500;
};

export const getErrorRetryable = (failureCount: number, error: MutationErrorContext): boolean => {
  if (failureCount > 2) {
    return false;
  }

  if (!(error instanceof Error)) {
    return false;
  }

  if (isApiError(error)) {
    return isRetryableStatus(error.status);
  }

  return true;
};

export const getErrorMessage = (error: unknown): string => {
  return getErrorMessages(error)[0] ?? getUnknownErrorLabel();
};

const stringifyUnknown = (value: unknown): string => {
  if (typeof value === 'string') {
    return value;
  }

  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }

  if (value === null || value === undefined) {
    return '';
  }

  try {
    return JSON.stringify(value);
  } catch {
    return '';
  }
};

const collectDetailMessages = (detail: unknown, visited = new WeakSet<object>()): string[] => {
  if (typeof detail === 'string') {
    const normalized = detail.trim();
    return normalized ? [normalized] : [];
  }

  if (typeof detail === 'number' || typeof detail === 'boolean') {
    return [String(detail)];
  }

  if (Array.isArray(detail)) {
    return detail.flatMap((item) => collectDetailMessages(item, visited));
  }

  if (typeof detail === 'object' && detail !== null) {
    if (visited.has(detail)) {
      return [];
    }

    visited.add(detail);

    const candidate = detail as {
      msg?: unknown;
      message?: unknown;
      detail?: unknown;
      details?: unknown;
      error?: unknown;
      errors?: unknown;
      body?: unknown;
      loc?: unknown;
    };

    if (typeof candidate.msg === 'string') {
      const location = Array.isArray(candidate.loc)
        ? candidate.loc
            .map((part) => stringifyUnknown(part).trim())
            .filter((part) => part.length > 0)
            .join('.')
        : '';
      const prefix = location ? `${location}: ` : '';
      return [`${prefix}${candidate.msg.trim()}`];
    }

    const directMessages =
      typeof candidate.message === 'string' && candidate.message.trim().length > 0
        ? [candidate.message.trim()]
        : [];

    const nestedDetails = [
      ...collectDetailMessages(candidate.error, visited),
      ...collectDetailMessages(candidate.detail, visited),
      ...collectDetailMessages(candidate.details, visited),
      ...collectDetailMessages(candidate.errors, visited),
      ...collectDetailMessages(candidate.body, visited),
    ];
    if (directMessages.length > 0 || nestedDetails.length > 0) {
      return [...directMessages, ...nestedDetails];
    }
  }

  const fallback = stringifyUnknown(detail).trim();
  return fallback ? [fallback] : [];
};

export const getErrorMessages = (error: unknown): string[] => {
  if (error instanceof Error) {
    if (isApiError(error)) {
      const lines = [error.message, ...collectDetailMessages(error.body)].filter(
        (line): line is string => typeof line === 'string' && line.trim().length > 0,
      );

      return [...new Set(lines)];
    }

    return [error.message || getUnknownErrorLabel()];
  }

  const fallbackMessages = collectDetailMessages(error);
  return fallbackMessages.length > 0 ? [...new Set(fallbackMessages)] : [getUnknownErrorLabel()];
};

type ApiQueryOptions<TData, TError extends RetryableError = ApiError> = Omit<
  UseQueryOptions<TData, TError, TData, QueryKey>,
  'queryKey' | 'queryFn'
> & {
  queryKey: QueryKey;
  queryFn: () => Promise<TData>;
};

type ApiMutationOptions<
  TData,
  TError extends RetryableError,
  TVariables,
  TContext = unknown,
> = Omit<
  UseMutationOptions<TData, TError, TVariables, TContext>,
  'mutationKey' | 'mutationFn'
> & {
  mutationKey: MutationKey;
  mutationFn: MutationFunction<TData, TVariables>;
};

export function useApiQuery<TData, TError extends RetryableError = ApiError>(
  options: ApiQueryOptions<TData, TError>,
): UseQueryResult<TData, TError> {
  return useQuery<TData, TError, TData, QueryKey>({
    ...queryDefaultConfig,
    retry: getErrorRetryable,
    ...options,
  });
}

export function useApiMutation<
  TData,
  TError extends RetryableError,
  TVariables = void,
  TContext = unknown,
>(
  options: ApiMutationOptions<TData, TError, TVariables, TContext>,
): UseMutationResult<TData, TError, TVariables, TContext> {
  return useMutation<TData, TError, TVariables, TContext>({
    ...mutationDefaultConfig,
    retry: getErrorRetryable,
    ...options,
  });
}
