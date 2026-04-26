/**
 * Хранение auth-токенов и активной организации.
 *
 * accessToken/refreshToken — в localStorage (вызывается только в браузере).
 * Активная организация — в cookie `erp.org` (JSON {code, name}, max-age 30 дней).
 *
 * Все геттеры возвращают null если код выполняется на сервере (typeof window === 'undefined').
 */

export const TOKEN_KEYS = {
  access: 'erp.access',
  refresh: 'erp.refresh',
} as const;

export const ORG_COOKIE = 'erp.org';

export interface ActiveOrg {
  code: string;
  name: string;
}

// ─── tokens ──────────────────────────────────────────────────────────────

export function getAccessToken(): string | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(TOKEN_KEYS.access);
}

export function getRefreshToken(): string | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(TOKEN_KEYS.refresh);
}

export function setTokens(access: string, refresh: string): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(TOKEN_KEYS.access, access);
  window.localStorage.setItem(TOKEN_KEYS.refresh, refresh);
}

export function setAccessToken(access: string): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(TOKEN_KEYS.access, access);
}

export function clearTokens(): void {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(TOKEN_KEYS.access);
  window.localStorage.removeItem(TOKEN_KEYS.refresh);
}

// ─── active organization ─────────────────────────────────────────────────

const ORG_MAX_AGE_S = 60 * 60 * 24 * 30; // 30 дней

export function readOrgCookie(): ActiveOrg | null {
  if (typeof document === 'undefined') return null;
  const m = document.cookie.match(new RegExp(`(?:^|;\\s*)${ORG_COOKIE}=([^;]+)`));
  if (!m) return null;
  try {
    const raw = decodeURIComponent(m[1]);
    const obj = JSON.parse(raw);
    if (typeof obj?.code === 'string' && typeof obj?.name === 'string') {
      return { code: obj.code, name: obj.name };
    }
    return null;
  } catch {
    return null;
  }
}

export function writeOrgCookie(org: ActiveOrg): void {
  if (typeof document === 'undefined') return;
  const value = encodeURIComponent(JSON.stringify(org));
  document.cookie = `${ORG_COOKIE}=${value}; path=/; max-age=${ORG_MAX_AGE_S}; SameSite=Lax`;
}

export function clearOrgCookie(): void {
  if (typeof document === 'undefined') return;
  document.cookie = `${ORG_COOKIE}=; path=/; max-age=0; SameSite=Lax`;
}

// ─── helpers ─────────────────────────────────────────────────────────────

export function clearAllAuth(): void {
  clearTokens();
  clearOrgCookie();
}
