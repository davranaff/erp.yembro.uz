import { type ZodType, z } from 'zod';

import { env } from '@/shared/config/env';
import {
  clearAuthSession,
  hydrateSession,
  loadAuthSession,
  parseAuthHeaders,
  saveAuthSession,
} from '@/shared/auth';

import { ApiError, normalizeError } from './error-handler';

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

type ApiEnvelope<T = unknown> = {
  ok: boolean;
  data: T;
  error: {
    code?: string;
    message: string;
    details?: unknown;
  } | null;
};

export type ApiRequestOptions<TResponse, TBody = unknown> = Omit<RequestInit, 'body' | 'method'> & {
  body?: TBody;
  responseSchema?: ZodType<TResponse>;
  timeoutMs?: number;
  skipAuth?: boolean;
  _retryAfterRefresh?: boolean;
};

const defaultHeaders: HeadersInit = {
  'Content-Type': 'application/json',
};

const authRefreshResponseSchema = z.object({
  employeeId: z.string().trim().min(1),
  organizationId: z.string().trim().min(1),
  departmentId: z.string().trim().nullable().optional(),
  departmentModuleKey: z.string().trim().nullable().optional(),
  headsAnyDepartment: z.boolean(),
  username: z.string().trim().min(1),
  roles: z.array(z.string().trim()),
  permissions: z.array(z.string().trim()),
  accessToken: z.string().trim().min(1),
  refreshToken: z.string().trim().optional(),
  expiresAt: z.string().trim().nullable().optional(),
});

type AuthRefreshResponse = z.infer<typeof authRefreshResponseSchema>;

export class ApiClient {
  private readonly baseUrl: string;
  private refreshPromise: Promise<boolean> | null = null;

  constructor(baseUrl: string = env.VITE_API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private buildUrl(path: string): string {
    if (/^https?:\/\//i.test(path)) {
      return path;
    }

    const normalizedBase = this.baseUrl.endsWith('/') ? this.baseUrl.slice(0, -1) : this.baseUrl;
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;

    return `${normalizedBase}${normalizedPath}`;
  }

  private extractPayload<T>(body: T): T | unknown {
    if (
      typeof body === 'object' &&
      body !== null &&
      'ok' in body &&
      'data' in body &&
      'error' in body
    ) {
      const envelope = body as ApiEnvelope<T>;
      if (envelope.ok) {
        return envelope.data;
      }

      const message = envelope.error?.message ?? 'Request failed';
      throw new ApiError(message, 400, envelope.error);
    }

    return body;
  }

  private async refreshSession(timeoutMs?: number): Promise<boolean> {
    if (this.refreshPromise) {
      return this.refreshPromise;
    }

    this.refreshPromise = this.performRefresh(timeoutMs).finally(() => {
      this.refreshPromise = null;
    });

    return this.refreshPromise;
  }

  private async performRefresh(timeoutMs?: number): Promise<boolean> {
    const currentSession = loadAuthSession();
    const refreshToken = currentSession?.refreshToken?.trim();

    if (!currentSession || !refreshToken) {
      clearAuthSession();
      return false;
    }

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs ?? env.VITE_REQUEST_TIMEOUT_MS);

    try {
      const response = await fetch(this.buildUrl('/auth/refresh'), {
        method: 'POST',
        headers: defaultHeaders,
        body: JSON.stringify({ refreshToken }),
        signal: controller.signal,
      });

      const responseText = await response.text();
      const parsedBody = this.parseBody(responseText);
      if (!response.ok) {
        clearAuthSession();
        return false;
      }

      const responsePayload = this.extractPayload(parsedBody);
      const refreshed = authRefreshResponseSchema.parse(responsePayload as AuthRefreshResponse);

      saveAuthSession(
        hydrateSession({
          employeeId: refreshed.employeeId,
          organizationId: refreshed.organizationId,
          departmentId: refreshed.departmentId,
          departmentModuleKey: refreshed.departmentModuleKey,
          headsAnyDepartment: refreshed.headsAnyDepartment,
          username: refreshed.username,
          roles: refreshed.roles,
          permissions: refreshed.permissions,
          accessToken: refreshed.accessToken,
          refreshToken: refreshed.refreshToken ?? currentSession.refreshToken,
          expiresAt: refreshed.expiresAt,
        }),
      );
      return true;
    } catch {
      clearAuthSession();
      return false;
    } finally {
      clearTimeout(timeout);
    }
  }

  async request<T>(
    method: HttpMethod,
    path: string,
    options: ApiRequestOptions<T, unknown> = {},
  ): Promise<T> {
    const { body, responseSchema, timeoutMs, skipAuth, _retryAfterRefresh, ...requestInit } = options;

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs ?? env.VITE_REQUEST_TIMEOUT_MS);

    try {
      const headers = new Headers(defaultHeaders);

      if (!skipAuth) {
        const authHeaders = parseAuthHeaders();
        new Headers(authHeaders).forEach((value, key) => headers.set(key, value));
      }

      if (requestInit.headers) {
        new Headers(requestInit.headers).forEach((value, key) => headers.set(key, value));
      }

      const isFormDataPayload = body instanceof FormData;
      const isBinaryPayload = body instanceof Blob;
      if (isFormDataPayload || isBinaryPayload) {
        headers.delete('Content-Type');
      }

      const requestPayload =
        isFormDataPayload || isBinaryPayload
          ? body
          : body !== undefined
            ? JSON.stringify(body)
            : undefined;

      const response = await fetch(this.buildUrl(path), {
        ...requestInit,
        method,
        headers,
        body: requestPayload,
        signal: controller.signal,
      });

      const responseText = await response.text();
      const parsedBody = this.parseBody(responseText);

      if (!response.ok) {
        const canRetryWithRefresh =
          response.status === 401 &&
          !skipAuth &&
          !_retryAfterRefresh &&
          !path.endsWith('/auth/login') &&
          !path.endsWith('/auth/refresh');

        if (canRetryWithRefresh) {
          const refreshed = await this.refreshSession(timeoutMs);
          if (refreshed) {
            return this.request<T>(method, path, {
              ...options,
              _retryAfterRefresh: true,
            });
          }
        }

        const message = normalizeError(response.status, parsedBody);
        throw new ApiError(message, response.status, parsedBody);
      }

      const responsePayload = this.extractPayload(parsedBody);

      if (response.status === 204) {
        return z.any().parse(null) as T;
      }

      if (!responseSchema) {
        return responsePayload as T;
      }

      return responseSchema.parse(responsePayload);
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        throw new ApiError('Request timeout', 408, { cause: 'timeout' });
      }
      throw error;
    } finally {
      clearTimeout(timeout);
    }
  }

  get<T>(path: string, schema?: ZodType<T>, init: Omit<ApiRequestOptions<T>, 'body'> = {}) {
    return this.request<T>('GET', path, {
      ...init,
      responseSchema: schema,
    } as ApiRequestOptions<T>);
  }

  post<T, TBody>(
    path: string,
    body: TBody,
    schema?: ZodType<T>,
    init: Omit<ApiRequestOptions<T, TBody>, 'body'> = {},
  ) {
    return this.request<T>('POST', path, {
      ...init,
      body,
      responseSchema: schema,
    } as ApiRequestOptions<T, TBody>);
  }

  put<T, TBody>(
    path: string,
    body: TBody,
    schema?: ZodType<T>,
    init: Omit<ApiRequestOptions<T, TBody>, 'body'> = {},
  ) {
    return this.request<T>('PUT', path, {
      ...init,
      body,
      responseSchema: schema,
    } as ApiRequestOptions<T, TBody>);
  }

  patch<T, TBody>(
    path: string,
    body: TBody,
    schema?: ZodType<T>,
    init: Omit<ApiRequestOptions<T, TBody>, 'body'> = {},
  ) {
    return this.request<T>('PATCH', path, {
      ...init,
      body,
      responseSchema: schema,
    } as ApiRequestOptions<T, TBody>);
  }

  delete<T>(path: string, schema?: ZodType<T>, init: Omit<ApiRequestOptions<T>, 'body'> = {}) {
    return this.request<T>('DELETE', path, {
      ...init,
      responseSchema: schema,
    } as ApiRequestOptions<T>);
  }

  private parseBody(text: string): unknown {
    if (!text) {
      return null;
    }

    try {
      return JSON.parse(text);
    } catch {
      return text;
    }
  }
}

export const apiClient = new ApiClient();
