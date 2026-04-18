import { Outlet } from 'react-router-dom';

import { CommandPalette } from '@/shared/ui/command-palette';

import { LeftRail } from './left-rail';

export function AppShell() {
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-bg text-ink">
      <LeftRail />
      <main className="flex min-w-0 flex-1 flex-col">
        <Outlet />
      </main>
      <CommandPalette />
    </div>
  );
}
