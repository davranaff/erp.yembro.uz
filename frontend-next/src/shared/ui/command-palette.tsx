import * as Dialog from '@radix-ui/react-dialog';
import { Command } from 'cmdk';
import {
  LayoutDashboard,
  LogOut,
  Moon,
  Settings,
  Sun,
  Users,
  Warehouse,
  Wallet,
  UserSquare,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { cn } from '@/lib/cn';
import { useAuthStore } from '@/shared/auth/auth-store';
import { useI18n } from '@/shared/i18n/i18n';
import { useAppStore } from '@/shared/state/app-store';

import { Kbd } from './kbd';

interface CommandItem {
  id: string;
  label: string;
  shortcut?: string;
  icon: React.ComponentType<{ className?: string }>;
  group: 'nav' | 'actions';
  run: () => void;
}

export function CommandPalette() {
  const open = useAppStore((s) => s.commandOpen);
  const setOpen = useAppStore((s) => s.setCommandOpen);
  const theme = useAppStore((s) => s.theme);
  const toggleTheme = useAppStore((s) => s.toggleTheme);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();
  const { t } = useI18n();
  const [query, setQuery] = useState('');

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen(!open);
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, setOpen]);

  useEffect(() => {
    if (!open) setQuery('');
  }, [open]);

  const items = useMemo<CommandItem[]>(() => {
    const close = () => setOpen(false);
    return [
      {
        id: 'nav-dashboard',
        label: t('nav.dashboard'),
        icon: LayoutDashboard,
        group: 'nav',
        shortcut: 'G D',
        run: () => {
          navigate('/dashboard');
          close();
        },
      },
      {
        id: 'nav-clients',
        label: t('nav.clients'),
        icon: Users,
        group: 'nav',
        shortcut: 'G C',
        run: () => {
          navigate('/clients');
          close();
        },
      },
      {
        id: 'nav-finance',
        label: t('nav.finance'),
        icon: Wallet,
        group: 'nav',
        run: () => {
          navigate('/finance');
          close();
        },
      },
      {
        id: 'nav-hr',
        label: t('nav.hr'),
        icon: UserSquare,
        group: 'nav',
        run: () => {
          navigate('/hr');
          close();
        },
      },
      {
        id: 'nav-inventory',
        label: t('nav.inventory'),
        icon: Warehouse,
        group: 'nav',
        run: () => {
          navigate('/inventory');
          close();
        },
      },
      {
        id: 'nav-settings',
        label: t('nav.settings'),
        icon: Settings,
        group: 'nav',
        run: () => {
          navigate('/settings');
          close();
        },
      },
      {
        id: 'action-theme',
        label: theme === 'dark' ? 'Светлая тема' : 'Тёмная тема',
        icon: theme === 'dark' ? Sun : Moon,
        group: 'actions',
        run: () => {
          toggleTheme();
          close();
        },
      },
      {
        id: 'action-logout',
        label: t('nav.logout'),
        icon: LogOut,
        group: 'actions',
        run: () => {
          logout();
          close();
        },
      },
    ];
  }, [logout, navigate, setOpen, t, theme, toggleTheme]);

  const grouped = useMemo(() => {
    const nav = items.filter((i) => i.group === 'nav');
    const actions = items.filter((i) => i.group === 'actions');
    return { nav, actions };
  }, [items]);

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-bg-overlay/70 backdrop-blur-sm data-[state=open]:animate-fade-in" />
        <Dialog.Content
          className={cn(
            'fixed left-1/2 top-[20%] z-50 w-full max-w-[560px] -translate-x-1/2',
            'overflow-hidden rounded-lg border border-line bg-bg-surface shadow-pop',
            'data-[state=open]:animate-scale-in',
          )}
        >
          <Dialog.Title className="sr-only">{t('shell.commandPalette')}</Dialog.Title>
          <Command
            className="flex flex-col"
            loop
            value={undefined}
            filter={(value, search) =>
              value.toLowerCase().includes(search.toLowerCase()) ? 1 : 0
            }
          >
            <div className="flex items-center gap-2 border-b border-line px-3">
              <Command.Input
                value={query}
                onValueChange={setQuery}
                placeholder={t('shell.search')}
                className="h-11 flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-ink-faint"
              />
              <Kbd>Esc</Kbd>
            </div>
            <Command.List className="max-h-80 overflow-y-auto p-1">
              <Command.Empty className="px-3 py-6 text-center text-xs text-ink-muted">
                {t('shell.empty')}
              </Command.Empty>
              <Command.Group
                heading="Навигация"
                className="mb-1 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:pt-2 [&_[cmdk-group-heading]]:text-2xs [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wide [&_[cmdk-group-heading]]:text-ink-muted"
              >
                {grouped.nav.map((item) => (
                  <CommandRow key={item.id} item={item} />
                ))}
              </Command.Group>
              <Command.Group
                heading="Действия"
                className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:pt-2 [&_[cmdk-group-heading]]:text-2xs [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wide [&_[cmdk-group-heading]]:text-ink-muted"
              >
                {grouped.actions.map((item) => (
                  <CommandRow key={item.id} item={item} />
                ))}
              </Command.Group>
            </Command.List>
          </Command>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function CommandRow({ item }: { item: CommandItem }) {
  const Icon = item.icon;
  return (
    <Command.Item
      value={`${item.id} ${item.label}`}
      onSelect={item.run}
      className={cn(
        'flex h-8 cursor-default items-center gap-2 rounded px-2 text-sm text-ink',
        'data-[selected=true]:bg-bg-inset data-[selected=true]:text-ink',
      )}
    >
      <Icon className="h-3.5 w-3.5 text-ink-muted" />
      <span className="flex-1 truncate">{item.label}</span>
      {item.shortcut ? <Kbd>{item.shortcut}</Kbd> : null}
    </Command.Item>
  );
}
