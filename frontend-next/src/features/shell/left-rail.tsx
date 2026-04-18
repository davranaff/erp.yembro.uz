import {
  LayoutDashboard,
  Search,
  Settings,
  Users,
  UserSquare,
  Wallet,
  Warehouse,
} from 'lucide-react';
import { NavLink } from 'react-router-dom';

import { cn } from '@/lib/cn';
import { useI18n } from '@/shared/i18n/i18n';
import { useAppStore } from '@/shared/state/app-store';
import { Kbd } from '@/shared/ui/kbd';

interface RailItem {
  to: string;
  icon: React.ComponentType<{ className?: string }>;
  labelKey: string;
}

const ITEMS: RailItem[] = [
  { to: '/dashboard', icon: LayoutDashboard, labelKey: 'nav.dashboard' },
  { to: '/clients', icon: Users, labelKey: 'nav.clients' },
  { to: '/finance', icon: Wallet, labelKey: 'nav.finance' },
  { to: '/hr', icon: UserSquare, labelKey: 'nav.hr' },
  { to: '/inventory', icon: Warehouse, labelKey: 'nav.inventory' },
];

export function LeftRail() {
  const { t } = useI18n();
  const setCommandOpen = useAppStore((s) => s.setCommandOpen);

  return (
    <aside className="flex h-full w-12 shrink-0 flex-col items-center border-r border-line bg-bg-surface py-2">
      <button
        type="button"
        onClick={() => setCommandOpen(true)}
        className="mb-2 flex h-8 w-8 items-center justify-center rounded border border-line bg-bg-subtle text-ink-muted hover:border-line-strong hover:text-ink"
        title={t('shell.commandPalette')}
      >
        <Search className="h-3.5 w-3.5" />
      </button>
      <nav className="flex flex-1 flex-col items-center gap-1">
        {ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              title={t(item.labelKey)}
              className={({ isActive }) =>
                cn(
                  'group relative flex h-8 w-8 items-center justify-center rounded',
                  isActive
                    ? 'bg-bg-inset text-ink'
                    : 'text-ink-muted hover:bg-bg-inset hover:text-ink',
                )
              }
            >
              <Icon className="h-3.5 w-3.5" />
            </NavLink>
          );
        })}
      </nav>
      <NavLink
        to="/settings"
        title={t('nav.settings')}
        className={({ isActive }) =>
          cn(
            'flex h-8 w-8 items-center justify-center rounded',
            isActive ? 'bg-bg-inset text-ink' : 'text-ink-muted hover:bg-bg-inset hover:text-ink',
          )
        }
      >
        <Settings className="h-3.5 w-3.5" />
      </NavLink>
      <div className="mt-2 hidden lg:flex">
        <Kbd className="h-4">⌘K</Kbd>
      </div>
    </aside>
  );
}
