import { type ReactNode, useEffect } from 'react';
import { Outlet, useLocation } from 'react-router-dom';

import { ToastProvider } from '@/components/ui/toast';
import { TopProgressBar } from '@/components/ui/top-progress-bar';
import { useAppStore } from '@/shared/store';
import { useThemeEffect } from '@/shared/theme';
import { TourProvider } from '@/shared/tour';

import { CommandPaletteProvider } from '../ui/command-palette';

type RootLayoutProps = {
  children?: ReactNode;
};

export function RootLayout({ children }: RootLayoutProps) {
  const setCurrentRoute = useAppStore((state) => state.setCurrentRoute);
  const location = useLocation();
  useThemeEffect();

  useEffect(() => {
    setCurrentRoute(location.pathname);
  }, [location.pathname, setCurrentRoute]);

  return (
    <div className="relative min-h-screen overflow-hidden bg-[hsl(var(--canvas))] text-foreground">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
        style={{
          background: `
            radial-gradient(circle at 12% 6%, hsl(var(--primary) / 0.16), transparent 18%),
            radial-gradient(circle at 88% 8%, hsl(var(--accent) / 0.14), transparent 20%),
            radial-gradient(circle at 50% 26%, hsl(0 0% 100% / 0.64), transparent 24%),
            radial-gradient(circle at 72% 78%, hsl(var(--secondary) / 0.2), transparent 26%),
            linear-gradient(180deg, hsl(var(--canvas) / 0.82), hsl(var(--background) / 0.95))
          `,
        }}
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-40"
        style={{
          backgroundImage:
            'linear-gradient(to right, hsl(var(--border) / 0.3) 1px, transparent 1px), linear-gradient(to bottom, hsl(var(--border) / 0.3) 1px, transparent 1px)',
          backgroundSize: '88px 88px',
          maskImage: 'radial-gradient(circle at center, black 30%, transparent 82%)',
          WebkitMaskImage: 'radial-gradient(circle at center, black 30%, transparent 82%)',
        }}
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-56"
        style={{
          background: 'linear-gradient(180deg, hsl(0 0% 100% / 0.52), hsl(0 0% 100% / 0))',
        }}
      />
      <main className="relative min-h-screen w-full">
        <ToastProvider>
          <TopProgressBar />
          <CommandPaletteProvider>
            <TourProvider>{children ?? <Outlet />}</TourProvider>
          </CommandPaletteProvider>
        </ToastProvider>
      </main>
    </div>
  );
}
