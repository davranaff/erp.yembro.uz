import { create } from 'zustand';

export type CrudShellMode = 'drawer' | 'modal';

const STORAGE_KEY = 'yembro:crud-shell-mode';
const DEFAULT_MODE: CrudShellMode = 'drawer';

const isCrudShellMode = (value: unknown): value is CrudShellMode =>
  value === 'drawer' || value === 'modal';

const loadInitialMode = (): CrudShellMode => {
  if (typeof window === 'undefined') {
    return DEFAULT_MODE;
  }
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return isCrudShellMode(stored) ? stored : DEFAULT_MODE;
  } catch {
    return DEFAULT_MODE;
  }
};

const persistMode = (mode: CrudShellMode): void => {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    window.localStorage.setItem(STORAGE_KEY, mode);
  } catch {
    /* ignore */
  }
};

type CrudShellModeStore = {
  mode: CrudShellMode;
  setMode: (mode: CrudShellMode) => void;
  toggleMode: () => void;
};

export const useCrudShellModeStore = create<CrudShellModeStore>((set, get) => ({
  mode: loadInitialMode(),
  setMode: (mode) => {
    persistMode(mode);
    set({ mode });
  },
  toggleMode: () => {
    const next: CrudShellMode = get().mode === 'drawer' ? 'modal' : 'drawer';
    persistMode(next);
    set({ mode: next });
  },
}));
