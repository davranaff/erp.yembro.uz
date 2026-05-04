/**
 * HTTP-клиент для DRF backend.
 *
 * Особенности:
 *  - Bearer access-token из localStorage в каждом запросе (если не skipAuth).
 *  - X-Organization-Code из cookie `erp.org` (если не skipOrg).
 *  - 401 → попытка refresh токена через POST /api/auth/token/refresh/, ретрай оригинального запроса.
 *  - При фейле refresh — clearAllAuth() и редирект на /login.
 *  - Ошибки бросаются как ApiError со статусом и распарсенным телом.
 */

import {
  clearAllAuth,
  getAccessToken,
  getRefreshToken,
  readOrgCookie,
  setAccessToken,
  setTokens,
} from './tokens';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(status: number, data: unknown, message?: string) {
    super(message ?? `API error ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

export interface ApiInit extends Omit<RequestInit, 'body'> {
  /** Не прикреплять Authorization header. */
  skipAuth?: boolean;
  /** Не прикреплять X-Organization-Code header. */
  skipOrg?: boolean;
  /** Тело запроса (объект автоматически сериализуется в JSON). */
  body?: BodyInit | object | null;
}

// ─── refresh-flow с одной concurrent-попыткой ────────────────────────────

let refreshPromise: Promise<string | null> | null = null;

async function performRefresh(): Promise<string | null> {
  const refresh = getRefreshToken();
  if (!refresh) return null;

  try {
    const res = await fetch(`${API_URL}/api/auth/token/refresh/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh }),
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { access?: string; refresh?: string };
    if (!data.access) return null;
    if (data.refresh) {
      setTokens(data.access, data.refresh);
    } else {
      setAccessToken(data.access);
    }
    return data.access;
  } catch {
    return null;
  }
}

function refreshAccessToken(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = performRefresh().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

// ─── helpers ─────────────────────────────────────────────────────────────

function buildHeaders(init: ApiInit | undefined, accessOverride?: string | null): HeadersInit {
  const headers = new Headers(init?.headers as HeadersInit | undefined);
  if (!headers.has('Content-Type') && typeof init?.body === 'object' && init?.body !== null && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }
  if (!init?.skipAuth) {
    const access = accessOverride ?? getAccessToken();
    if (access) headers.set('Authorization', `Bearer ${access}`);
  }
  if (!init?.skipOrg) {
    const org = readOrgCookie();
    if (org) headers.set('X-Organization-Code', org.code);
  }
  return headers;
}

function serializeBody(body: ApiInit['body']): BodyInit | null | undefined {
  if (body === null || body === undefined) return body as null | undefined;
  if (typeof body === 'string') return body;
  if (body instanceof FormData) return body;
  if (body instanceof Blob) return body;
  if (body instanceof ArrayBuffer) return body;
  if (body instanceof URLSearchParams) return body;
  return JSON.stringify(body);
}

async function parseBody(res: Response): Promise<unknown> {
  if (res.status === 204) return null;
  const ct = res.headers.get('content-type') ?? '';
  if (ct.includes('application/json')) {
    try {
      return await res.json();
    } catch {
      return null;
    }
  }
  try {
    return await res.text();
  } catch {
    return null;
  }
}

function redirectToLogin(): void {
  if (typeof window === 'undefined') return;
  if (window.location.pathname === '/login') return;
  window.location.assign('/login');
}

// ─── public API ──────────────────────────────────────────────────────────

export async function apiFetch<T = unknown>(path: string, init?: ApiInit): Promise<T> {
  const url = `${API_URL}${path}`;
  const body = serializeBody(init?.body);

  const doFetch = async (accessOverride?: string | null): Promise<Response> => {
    return fetch(url, {
      ...init,
      headers: buildHeaders(init, accessOverride),
      body: body ?? undefined,
    });
  };

  let res = await doFetch();

  // 401 → попытка обновить access и повторить
  if (res.status === 401 && !init?.skipAuth) {
    const newAccess = await refreshAccessToken();
    if (newAccess) {
      res = await doFetch(newAccess);
    }
    if (res.status === 401) {
      clearAllAuth();
      redirectToLogin();
      const data = await parseBody(res);
      throw new ApiError(401, data, 'Не авторизован');
    }
  }

  if (!res.ok) {
    const data = await parseBody(res);
    throw new ApiError(res.status, data);
  }

  if (res.status === 204) return null as T;
  const data = await parseBody(res);
  return data as T;
}
