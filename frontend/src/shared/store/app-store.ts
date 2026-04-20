import { create } from 'zustand';

export type ThemePreference = 'light' | 'dark' | 'system';

export type AppStoreState = {
  isSidebarOpen: boolean;
  isGlobalLoading: boolean;
  theme: ThemePreference;
  currentRoute: string | null;
};

export type AppStoreActions = {
  setSidebarOpen: (value: boolean) => void;
  toggleSidebar: () => void;
  setGlobalLoading: (value: boolean) => void;
  setTheme: (value: ThemePreference) => void;
  setCurrentRoute: (route: string | null) => void;
  reset: () => void;
};

export type AppStore = AppStoreState & AppStoreActions;

const THEME_STORAGE_KEY = 'yembro.theme';

const readStoredTheme = (): ThemePreference => {
  if (typeof window === 'undefined') {
    return 'light';
  }
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === 'light' || stored === 'dark' || stored === 'system') {
      return stored;
    }
  } catch {
    // ignore access errors (private mode, SSR, etc.)
  }
  return 'light';
};

const writeStoredTheme = (value: ThemePreference) => {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, value);
  } catch {
    // ignore write errors
  }
};

const initialState: AppStoreState = {
  isSidebarOpen: false,
  isGlobalLoading: false,
  theme: readStoredTheme(),
  currentRoute: null,
};

export const useAppStore = create<AppStore>((set) => ({
  ...initialState,
  setSidebarOpen: (value) => set({ isSidebarOpen: value }),
  toggleSidebar: () =>
    set((state) => ({
      isSidebarOpen: !state.isSidebarOpen,
    })),
  setGlobalLoading: (value) => set({ isGlobalLoading: value }),
  setTheme: (value) => {
    writeStoredTheme(value);
    set({ theme: value });
  },
  setCurrentRoute: (route) => set({ currentRoute: route }),
  reset: () => set({ ...initialState, theme: readStoredTheme() }),
}));
