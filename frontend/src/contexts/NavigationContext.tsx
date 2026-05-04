'use client';

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from 'react';

interface NavigationState {
  /** Идёт навигация на новую страницу. */
  isNavigating: boolean;
  /** Куда мы переходим (pathname без origin). */
  targetPath: string | null;
  /** Помечает, что на pathname `path` пошёл переход (вызывается из RouteProgress / Link wrappers). */
  startNavigation: (path: string) => void;
  /** Сбрасывает состояние (вызывается когда usePathname сменился). */
  endNavigation: () => void;
}

const NavigationContext = createContext<NavigationState | null>(null);

export function NavigationProvider({ children }: { children: React.ReactNode }) {
  const [isNavigating, setIsNavigating] = useState(false);
  const [targetPath, setTargetPath] = useState<string | null>(null);

  const startNavigation = useCallback((path: string) => {
    setTargetPath(path);
    setIsNavigating(true);
  }, []);

  const endNavigation = useCallback(() => {
    setIsNavigating(false);
    setTargetPath(null);
  }, []);

  const value = useMemo<NavigationState>(
    () => ({ isNavigating, targetPath, startNavigation, endNavigation }),
    [isNavigating, targetPath, startNavigation, endNavigation],
  );

  return (
    <NavigationContext.Provider value={value}>
      {children}
    </NavigationContext.Provider>
  );
}

export function useNavigationStatus(): NavigationState {
  const ctx = useContext(NavigationContext);
  if (!ctx) {
    // Безопасный фолбэк — если кто-то использует хук вне провайдера,
    // вернём «всегда idle». Это позволяет компонентам не падать.
    return {
      isNavigating: false,
      targetPath: null,
      startNavigation: () => {},
      endNavigation: () => {},
    };
  }
  return ctx;
}
