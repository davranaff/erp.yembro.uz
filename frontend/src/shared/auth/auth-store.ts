import { create } from 'zustand';

import { clearAuthSession, hydrateSession, loadAuthSession, saveAuthSession } from './auth-storage';
import type { AuthCredentials, AuthState } from './types';

type AuthStore = AuthState & {
  initializeAuth: () => void;
  setSession: (credentials: AuthCredentials) => void;
  clearSession: () => void;
  setLoading: (value: boolean) => void;
  hasPermission: (permission: string) => boolean;
  hasRole: (role: string) => boolean;
};

const baseState: AuthState = {
  isAuthenticated: false,
  isInitialized: false,
  isLoading: false,
  error: null,
  session: null,
};

export const useAuthStore = create<AuthStore>((set, get) => ({
  ...baseState,
  initializeAuth: () => {
    const loaded = loadAuthSession();

    set({
      isAuthenticated: loaded !== null,
      isInitialized: true,
      isLoading: false,
      error: null,
      session: loaded,
    });
  },
  setSession: (credentials: AuthCredentials) => {
    const session = hydrateSession(credentials);
    saveAuthSession(session);

    set({
      isAuthenticated: true,
      isInitialized: true,
      isLoading: false,
      error: null,
      session,
    });
  },
  clearSession: () => {
    clearAuthSession();
    set({
      ...baseState,
      isInitialized: true,
    });
  },
  setLoading: (value: boolean) => {
    set({ isLoading: value });
  },
  hasPermission: (permission: string) => {
    const current = get().session;
    if (!current) {
      return false;
    }

    return current.permissions.includes(permission.toLowerCase());
  },
  hasRole: (role: string) => {
    const current = get().session;
    if (!current) {
      return false;
    }

    return current.roles.includes(role.toLowerCase());
  },
}));
