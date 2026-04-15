import { z } from 'zod';

const baseUrlSchema = z
  .string()
  .min(1)
  .refine(
    (value) => {
      if (value.startsWith('/')) {
        return true;
      }

      return z.string().url().safeParse(value).success;
    },
    { message: 'VITE_API_BASE_URL must be an absolute url or a relative path' },
  );

const envSchema = z.object({
  VITE_API_BASE_URL: baseUrlSchema.default('/api/v1'),
  VITE_AUTH_LOGIN_ENDPOINT: z.string().default('/auth/login'),
  VITE_REQUEST_TIMEOUT_MS: z.coerce.number().int().positive().default(15000),
  VITE_APP_NAME: z.string().default('Frontend Foundation'),
});

const normalizeApiBaseUrl = (value: string): string => {
  try {
    const parsedUrl = new URL(value);

    if (parsedUrl.hostname === 'api') {
      return parsedUrl.pathname || '/api/v1';
    }
  } catch {
    return value;
  }

  return value;
};

const parsed = envSchema.safeParse({
  VITE_API_BASE_URL: import.meta.env.VITE_API_BASE_URL,
  VITE_AUTH_LOGIN_ENDPOINT: import.meta.env.VITE_AUTH_LOGIN_ENDPOINT,
  VITE_REQUEST_TIMEOUT_MS: import.meta.env.VITE_REQUEST_TIMEOUT_MS,
  VITE_APP_NAME: import.meta.env.VITE_APP_NAME,
});

if (!parsed.success) {
  throw new Error(`Invalid Vite env: ${parsed.error.message}`);
}

export const env = {
  ...parsed.data,
  VITE_API_BASE_URL: normalizeApiBaseUrl(parsed.data.VITE_API_BASE_URL),
};

export type Env = z.infer<typeof envSchema>;
