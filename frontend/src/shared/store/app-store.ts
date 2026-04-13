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

const initialState: AppStoreState = {
  isSidebarOpen: false,
  isGlobalLoading: false,
  theme: 'system',
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
  setTheme: (value) => set({ theme: value }),
  setCurrentRoute: (route) => set({ currentRoute: route }),
  reset: () => set(initialState),
}));
