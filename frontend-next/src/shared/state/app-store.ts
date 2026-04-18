import { create } from 'zustand';

type Theme = 'dark' | 'light';

const THEME_STORAGE_KEY = 'frontend-next:theme';

function loadInitialTheme(): Theme {
  try {
    const raw = localStorage.getItem(THEME_STORAGE_KEY);
    if (raw === 'light' || raw === 'dark') return raw;
  } catch {
    // ignore
  }
  return 'dark';
}

function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  if (theme === 'dark') root.classList.add('dark');
  else root.classList.remove('dark');
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // ignore
  }
}

interface AppState {
  theme: Theme;
  commandOpen: boolean;
  setCommandOpen: (open: boolean) => void;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
}

const initialTheme = typeof window !== 'undefined' ? loadInitialTheme() : 'dark';
if (typeof window !== 'undefined') applyTheme(initialTheme);

export const useAppStore = create<AppState>((set, get) => ({
  theme: initialTheme,
  commandOpen: false,
  setCommandOpen: (open) => set({ commandOpen: open }),
  setTheme: (theme) => {
    applyTheme(theme);
    set({ theme });
  },
  toggleTheme: () => {
    const next: Theme = get().theme === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    set({ theme: next });
  },
}));
