import { env } from '@/env';
import { loadSession, saveSession, clearSession } from '@/shared/auth/session-storage';

import { ApiError, normalizeError } from './errors';

type Json = Record<string, unknown> | unknown[] | null;

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: Json | FormData;
  signal?: AbortSignal;
  query?: Record<string, string | number | boolean | undefined | null>;
  skipAuth?: boolean;
}

function buildUrl(path: string, query: RequestOptions['query']): string {
  const base = env.apiBaseUrl.endsWith('/') ? env.apiBaseUrl.slice(0, -1) : env.apiBaseUrl;
  const prefix = path.startsWith('/') ? path : `/${path}`;
  const url = `${base}${prefix}`;
  if (!query) return url;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') continue;
    params.set(key, String(value));
  }
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}

async function parseResponse<T>(res: Response): Promise<T> {
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  if (!text) return undefined as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    return text as unknown as T;
  }
}

let refreshInFlight: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight;
  refreshInFlight = (async () => {
    const current = loadSession();
    if (!current?.refreshToken) return null;
    try {
      const res = await fetch(buildUrl(env.authRefreshEndpoint, undefined), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: current.refreshToken }),
      });
      if (!res.ok) {
        clearSession();
        return null;
      }
      const body = (await res.json()) as {
        access_token?: string;
        refresh_token?: string;
        expires_in?: number;
      };
      if (!body.access_token) {
        clearSession();
        return null;
      }
      const expiresAt = body.expires_in
        ? Date.now() + body.expires_in * 1000
        : current.expiresAt;
      saveSession({
        ...current,
        accessToken: body.access_token,
        refreshToken: body.refresh_token ?? current.refreshToken,
        expiresAt,
      });
      return body.access_token;
    } catch {
      clearSession();
      return null;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

async function executeRequest<T>(path: string, opts: RequestOptions, retry = false): Promise<T> {
  const headers: Record<string, string> = {};
  const isForm = opts.body instanceof FormData;
  if (!isForm && opts.body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }

  if (!opts.skipAuth) {
    const session = loadSession();
    if (session?.accessToken) {
      headers.Authorization = `Bearer ${session.accessToken}`;
    }
  }

  const res = await fetch(buildUrl(path, opts.query), {
    method: opts.method ?? 'GET',
    headers,
    signal: opts.signal,
    body:
      opts.body === undefined
        ? undefined
        : isForm
          ? (opts.body as FormData)
          : JSON.stringify(opts.body),
  });

  if (res.status === 401 && !opts.skipAuth && !retry) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      return executeRequest<T>(path, opts, true);
    }
  }

  if (!res.ok) {
    const body = await parseResponse<unknown>(res);
    throw normalizeError(res.status, body);
  }

  return parseResponse<T>(res);
}

export const api = {
  get: <T>(path: string, opts?: Omit<RequestOptions, 'method' | 'body'>) =>
    executeRequest<T>(path, { ...opts, method: 'GET' }),
  post: <T>(path: string, body?: Json | FormData, opts?: Omit<RequestOptions, 'method' | 'body'>) =>
    executeRequest<T>(path, { ...opts, method: 'POST', body }),
  put: <T>(path: string, body?: Json | FormData, opts?: Omit<RequestOptions, 'method' | 'body'>) =>
    executeRequest<T>(path, { ...opts, method: 'PUT', body }),
  patch: <T>(path: string, body?: Json | FormData, opts?: Omit<RequestOptions, 'method' | 'body'>) =>
    executeRequest<T>(path, { ...opts, method: 'PATCH', body }),
  delete: <T>(path: string, opts?: Omit<RequestOptions, 'method' | 'body'>) =>
    executeRequest<T>(path, { ...opts, method: 'DELETE' }),
};

export { ApiError };
