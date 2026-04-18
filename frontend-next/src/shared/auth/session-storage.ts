export interface AuthSession {
  employeeId: string;
  email: string | null;
  fullName: string | null;
  organizationId: string | null;
  roles: string[];
  permissions: string[];
  accessToken: string;
  refreshToken: string | null;
  expiresAt: number | null;
}

const STORAGE_KEY = 'frontend-next:auth-session';

export function loadSession(): AuthSession | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as AuthSession;
    if (typeof parsed.accessToken !== 'string' || parsed.accessToken.length === 0) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function saveSession(session: AuthSession): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

export function clearSession(): void {
  localStorage.removeItem(STORAGE_KEY);
}
