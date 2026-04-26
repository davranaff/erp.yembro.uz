'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react';
import { usePathname } from 'next/navigation';

interface LayoutContextValue {
  /** Открыт ли мобильный сайдбар (off-canvas drawer). На десктопе всегда false. */
  sidebarOpen: boolean;
  toggleSidebar: () => void;
  closeSidebar: () => void;
}

const LayoutContext = createContext<LayoutContextValue | null>(null);

/**
 * Контекст shell-уровня. Сейчас содержит только состояние мобильного
 * сайдбара. На десктопе сайдбар фиксирован в layout grid и `sidebarOpen`
 * не используется — только на мобиле он работает как drawer.
 *
 * Закрывается автоматически при смене pathname (юзер кликнул пункт меню).
 */
export function LayoutProvider({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const pathname = usePathname();

  // Закрытие при навигации
  useEffect(() => {
    setSidebarOpen(false);
  }, [pathname]);

  // Lock body scroll когда drawer открыт на мобиле
  useEffect(() => {
    if (typeof document === 'undefined') return;
    if (sidebarOpen) {
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = '';
      };
    }
  }, [sidebarOpen]);

  const toggleSidebar = useCallback(() => setSidebarOpen((v) => !v), []);
  const closeSidebar = useCallback(() => setSidebarOpen(false), []);

  return (
    <LayoutContext.Provider value={{ sidebarOpen, toggleSidebar, closeSidebar }}>
      {children}
    </LayoutContext.Provider>
  );
}

export function useLayout(): LayoutContextValue {
  const ctx = useContext(LayoutContext);
  if (!ctx) {
    return { sidebarOpen: false, toggleSidebar: () => {}, closeSidebar: () => {} };
  }
  return ctx;
}
