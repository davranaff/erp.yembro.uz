'use client';

import { Dialog } from '@base-ui/react/dialog';
import {
  BarChart3,
  BookOpen,
  Building2,
  History,
  KeySquare,
  Search,
  Settings,
  type LucideIcon,
} from 'lucide-react';
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { AccessGate, canAccessDashboard, canReadAuditLogs, useAuthStore } from '@/shared/auth';
import { ROUTES } from '@/shared/config/routes';
import { useI18n } from '@/shared/i18n';
import { cn } from '@/shared/lib/cn';
import { useWorkspaceStore } from '@/shared/workspace';

type CommandAction = {
  id: string;
  label: string;
  hint?: string;
  icon: LucideIcon;
  to: string;
  keywords?: string[];
};

type CommandPaletteContextValue = {
  open: () => void;
  close: () => void;
  isOpen: boolean;
};

const CommandPaletteContext = createContext<CommandPaletteContextValue | null>(null);

const EMPTY_STRING_LIST: readonly string[] = [];

export function useCommandPalette(): CommandPaletteContextValue {
  const context = useContext(CommandPaletteContext);
  if (!context) {
    throw new Error('useCommandPalette must be used within CommandPaletteProvider');
  }
  return context;
}

export function CommandPaletteProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const open = useCallback(() => setIsOpen(true), []);
  const close = useCallback(() => setIsOpen(false), []);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      const isPalette = (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k';
      if (!isPalette) {
        return;
      }
      event.preventDefault();
      setIsOpen((current) => !current);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  const value = useMemo(() => ({ open, close, isOpen }), [open, close, isOpen]);

  return (
    <CommandPaletteContext.Provider value={value}>
      {children}
      <CommandPaletteDialog open={isOpen} onOpenChange={setIsOpen} />
    </CommandPaletteContext.Provider>
  );
}

function CommandPaletteDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (next: boolean) => void;
}) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const location = useLocation();
  const sessionRoles = useAuthStore((state) => state.session?.roles ?? EMPTY_STRING_LIST);
  const sessionPermissions = useAuthStore(
    (state) => state.session?.permissions ?? EMPTY_STRING_LIST,
  );
  const moduleMap = useWorkspaceStore((state) => state.moduleMap);
  const [query, setQuery] = useState('');
  const [highlight, setHighlight] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const actions = useMemo<CommandAction[]>(() => {
    const base: CommandAction[] = [];
    if (canAccessDashboard(sessionRoles, sessionPermissions)) {
      base.push({
        id: 'dashboard',
        label: t('nav.dashboard', undefined, 'Дашборд'),
        icon: BarChart3,
        to: ROUTES.dashboard,
        keywords: ['dashboard', 'обзор', 'аналитика'],
      });
    }
    base.push({
      id: 'settings',
      label: t('nav.settings', undefined, 'Настройки'),
      icon: Settings,
      to: ROUTES.settings,
      keywords: ['settings', 'profile', 'профиль'],
    });
    base.push({
      id: 'roles',
      label: t('nav.roleManagement', undefined, 'Роли'),
      icon: KeySquare,
      to: ROUTES.roleManagement,
      keywords: ['roles', 'permissions'],
    });
    if (canReadAuditLogs(sessionRoles, sessionPermissions)) {
      base.push({
        id: 'audit',
        label: t('nav.audit', undefined, 'Аудит'),
        icon: History,
        to: ROUTES.audit,
        keywords: ['audit', 'log', 'журнал'],
      });
    }
    base.push({
      id: 'core',
      label: t('modules.core.label', undefined, 'Справочники'),
      icon: BookOpen,
      to: ROUTES.dashboardModule('core'),
      keywords: ['reference', 'core', 'справочники'],
    });

    Object.values(moduleMap).forEach((module) => {
      if (!module.key || module.key === 'core') {
        return;
      }
      base.push({
        id: `module-${module.key}`,
        label: t(`modules.${module.key}.label`, undefined, module.label || module.key),
        hint: module.key,
        icon: Building2,
        to: ROUTES.dashboardModule(module.key),
        keywords: [module.key, module.label],
      });
    });

    return base;
  }, [moduleMap, sessionPermissions, sessionRoles, t]);

  const filteredActions = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) {
      return actions;
    }
    return actions.filter((action) => {
      const haystack = [action.label, action.hint, ...(action.keywords ?? [])]
        .filter(Boolean)
        .map((part) => String(part).toLowerCase())
        .join(' ');
      return haystack.includes(normalized);
    });
  }, [actions, query]);

  useEffect(() => {
    setHighlight(0);
  }, [query, open]);

  useEffect(() => {
    if (open) {
      setQuery('');
      const timer = setTimeout(() => inputRef.current?.focus(), 30);
      return () => clearTimeout(timer);
    }
  }, [open]);

  const runAction = useCallback(
    (action: CommandAction) => {
      onOpenChange(false);
      if (action.to !== location.pathname) {
        navigate(action.to);
      }
    },
    [location.pathname, navigate, onOpenChange],
  );

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setHighlight((current) => Math.min(filteredActions.length - 1, current + 1));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setHighlight((current) => Math.max(0, current - 1));
    } else if (event.key === 'Enter') {
      event.preventDefault();
      if (filteredActions.length > 0) {
        runAction(filteredActions[highlight]);
      }
    }
  };

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Backdrop className="data-ending-style:opacity-0 data-starting-style:opacity-0 fixed inset-0 z-[75] bg-[rgba(15,23,42,0.32)] backdrop-blur-sm transition-opacity duration-200" />
        <Dialog.Popup
          className="data-ending-style:opacity-0 data-starting-style:opacity-0 fixed left-1/2 top-[18vh] z-[76] w-[min(94vw,36rem)] -translate-x-1/2 overflow-hidden rounded-[24px] border border-border/70 bg-background shadow-[0_40px_120px_-56px_rgba(15,23,42,0.32)] transition-opacity duration-200"
          aria-label={t('nav.commandPalette', undefined, 'Быстрый переход')}
        >
          <div className="flex items-center gap-2 border-b border-border/60 px-3">
            <Search className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={t('common.search', undefined, 'Поиск')}
              className="h-12 w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
              aria-label={t('common.search', undefined, 'Поиск')}
            />
          </div>
          <AccessGate>
            <div
              role="listbox"
              aria-label={t('nav.commandPalette', undefined, 'Быстрый переход')}
              className="max-h-[40vh] overflow-y-auto p-2"
            >
              {filteredActions.length === 0 ? (
                <p className="px-3 py-6 text-center text-sm text-muted-foreground">
                  {t('common.noResults', undefined, 'Ничего не найдено')}
                </p>
              ) : (
                filteredActions.map((action, index) => {
                  const Icon = action.icon;
                  const isActive = index === highlight;
                  return (
                    <button
                      key={action.id}
                      type="button"
                      role="option"
                      aria-selected={isActive}
                      onMouseEnter={() => setHighlight(index)}
                      onClick={() => runAction(action)}
                      className={cn(
                        'flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition',
                        isActive
                          ? 'bg-primary/10 text-foreground'
                          : 'text-muted-foreground hover:bg-slate-50 hover:text-foreground',
                      )}
                    >
                      <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                      <span className="flex-1 truncate">{action.label}</span>
                      {action.hint ? (
                        <span className="text-xs text-muted-foreground">{action.hint}</span>
                      ) : null}
                    </button>
                  );
                })
              )}
            </div>
          </AccessGate>
          <div className="border-t border-border/60 bg-slate-50 px-3 py-2 text-[11px] text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <kbd className="rounded border border-border/70 bg-white px-1.5 py-0.5 font-mono text-[10px]">
                ↑↓
              </kbd>
              <span>— {t('nav.navigate', undefined, 'навигация')}</span>
            </span>
            <span className="mx-2 opacity-40">·</span>
            <span className="inline-flex items-center gap-1">
              <kbd className="rounded border border-border/70 bg-white px-1.5 py-0.5 font-mono text-[10px]">
                Enter
              </kbd>
              <span>— {t('nav.openAction', undefined, 'открыть')}</span>
            </span>
            <span className="mx-2 opacity-40">·</span>
            <span className="inline-flex items-center gap-1">
              <kbd className="rounded border border-border/70 bg-white px-1.5 py-0.5 font-mono text-[10px]">
                Esc
              </kbd>
              <span>— {t('common.close', undefined, 'Закрыть')}</span>
            </span>
          </div>
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
