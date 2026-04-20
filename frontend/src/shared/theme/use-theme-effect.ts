import { useEffect } from 'react';

import { useAppStore, type ThemePreference } from '@/shared/store';

const applyTheme = (theme: ThemePreference) => {
  if (typeof document === 'undefined') {
    return;
  }
  const root = document.documentElement;
  const shouldBeDark =
    theme === 'dark' ||
    (theme === 'system' &&
      typeof window !== 'undefined' &&
      window.matchMedia('(prefers-color-scheme: dark)').matches);
  root.classList.toggle('dark', shouldBeDark);
  root.style.colorScheme = shouldBeDark ? 'dark' : 'light';
};

export function useThemeEffect() {
  const theme = useAppStore((state) => state.theme);

  useEffect(() => {
    applyTheme(theme);

    if (theme !== 'system' || typeof window === 'undefined') {
      return;
    }
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const listener = () => applyTheme('system');
    media.addEventListener('change', listener);
    return () => media.removeEventListener('change', listener);
  }, [theme]);
}
