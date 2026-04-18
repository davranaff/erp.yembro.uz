export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

export function normalizeError(status: number, body: unknown): ApiError {
  if (body && typeof body === 'object') {
    const detail = (body as { detail?: unknown }).detail;
    if (typeof detail === 'string' && detail.length > 0) {
      return new ApiError(detail, status, body);
    }
    if (Array.isArray(detail)) {
      const first = detail[0] as { msg?: string } | undefined;
      if (first?.msg) return new ApiError(first.msg, status, body);
    }
    const message = (body as { message?: unknown }).message;
    if (typeof message === 'string' && message.length > 0) {
      return new ApiError(message, status, body);
    }
  }
  return new ApiError(`Request failed (${status})`, status, body);
}
