import { create } from 'zustand';

import type { AuthSession } from './session-storage';
import { clearSession, loadSession, saveSession } from './session-storage';

interface AuthState {
  session: AuthSession | null;
  isInitialized: boolean;
  isAuthenticated: boolean;
  setSession: (session: AuthSession | null) => void;
  hydrate: () => void;
  logout: () => void;
  hasPermission: (permission: string) => boolean;
  hasAnyPermission: (permissions: string[]) => boolean;
  hasRole: (role: string) => boolean;
}

function normalize(list: string[] | undefined | null): string[] {
  return (list ?? []).map((item) => item.trim().toLowerCase()).filter(Boolean);
}

export const useAuthStore = create<AuthState>((set, get) => ({
  session: null,
  isInitialized: false,
  isAuthenticated: false,
  setSession: (session) => {
    if (session) {
      saveSession(session);
    } else {
      clearSession();
    }
    set({ session, isAuthenticated: Boolean(session) });
  },
  hydrate: () => {
    const existing = loadSession();
    set({
      session: existing,
      isAuthenticated: Boolean(existing),
      isInitialized: true,
    });
  },
  logout: () => {
    clearSession();
    set({ session: null, isAuthenticated: false });
  },
  hasPermission: (permission) => {
    const perms = normalize(get().session?.permissions);
    return perms.includes(permission.toLowerCase());
  },
  hasAnyPermission: (permissions) => {
    if (permissions.length === 0) return true;
    const perms = normalize(get().session?.permissions);
    return permissions.some((p) => perms.includes(p.toLowerCase()));
  },
  hasRole: (role) => {
    const roles = normalize(get().session?.roles);
    return roles.includes(role.toLowerCase());
  },
}));
