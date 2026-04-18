const viteEnv = (import.meta as unknown as { env: Record<string, string | undefined> }).env;

function readEnv(key: string, fallback: string): string {
  const value = viteEnv[key];
  return typeof value === 'string' && value.length > 0 ? value : fallback;
}

export const env = {
  apiBaseUrl: readEnv('VITE_API_BASE_URL', '/api/v1'),
  authLoginEndpoint: readEnv('VITE_AUTH_LOGIN_ENDPOINT', '/auth/login'),
  authRefreshEndpoint: readEnv('VITE_AUTH_REFRESH_ENDPOINT', '/auth/refresh'),
  authProfileEndpoint: readEnv('VITE_AUTH_PROFILE_ENDPOINT', '/auth/me'),
} as const;
