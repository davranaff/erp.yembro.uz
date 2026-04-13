export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(message: string, status: number, body: unknown = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

export const isApiError = (value: unknown): value is ApiError => value instanceof ApiError;

const extractFirstErrorMessage = (body: unknown): string | null => {
  if (typeof body === 'string') {
    const normalized = body.trim();
    return normalized || null;
  }

  if (Array.isArray(body)) {
    for (const item of body) {
      const nested = extractFirstErrorMessage(item);
      if (nested) {
        return nested;
      }
    }
    return null;
  }

  if (typeof body === 'object' && body !== null) {
    const candidate = body as {
      error?: unknown;
      message?: unknown;
      msg?: unknown;
      detail?: unknown;
      details?: unknown;
    };

    if (typeof candidate.message === 'string' && candidate.message.trim()) {
      return candidate.message.trim();
    }

    if (typeof candidate.msg === 'string' && candidate.msg.trim()) {
      return candidate.msg.trim();
    }

    return (
      extractFirstErrorMessage(candidate.error) ??
      extractFirstErrorMessage(candidate.detail) ??
      extractFirstErrorMessage(candidate.details)
    );
  }

  return null;
};

export const normalizeError = (status: number, body: unknown): string => {
  const extractedMessage = extractFirstErrorMessage(body);
  if (extractedMessage) {
    return extractedMessage;
  }

  if (
    typeof body === 'object' &&
    body !== null &&
    'error' in body &&
    typeof (body as { error?: unknown }).error === 'object' &&
    (body as { error?: unknown }).error !== null &&
    typeof ((body as { error: unknown }).error as { message?: unknown }).message === 'string'
  ) {
    return ((body as { error: { message: string } }).error).message;
  }

  if (
    typeof body === 'object' &&
    body !== null &&
    'detail' in body &&
    typeof (body as { detail?: unknown }).detail === 'string'
  ) {
    return (body as { detail: string }).detail;
  }

  if (
    typeof body === 'object' &&
    body !== null &&
    'message' in body &&
    typeof (body as { message?: unknown }).message === 'string'
  ) {
    return (body as { message: string }).message;
  }

  return `Request failed with status ${status}`;
};
