import { ChevronDown, LogOut, Monitor, Moon, Sun, UserRound } from 'lucide-react';
import { useState } from 'react';

import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { useI18n } from '@/shared/i18n';
import { cn } from '@/shared/lib/cn';
import { useAppStore, type ThemePreference } from '@/shared/store';

type ProfileMenuProps = {
  username?: string;
  onLogout: () => void;
};

const THEME_OPTIONS: Array<{
  value: ThemePreference;
  icon: typeof Sun;
  labelKey: string;
  fallback: string;
}> = [
  { value: 'light', icon: Sun, labelKey: 'theme.light', fallback: 'Светлая' },
  { value: 'dark', icon: Moon, labelKey: 'theme.dark', fallback: 'Тёмная' },
  { value: 'system', icon: Monitor, labelKey: 'theme.system', fallback: 'Системная' },
];

export function ProfileMenu({ username, onLogout }: ProfileMenuProps) {
  const { t } = useI18n();
  const theme = useAppStore((state) => state.theme);
  const setTheme = useAppStore((state) => state.setTheme);
  const [isOpen, setIsOpen] = useState(false);

  const initials = (username ?? '')
    .split(/[\s._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((segment) => segment[0].toUpperCase())
    .join('');

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger
        aria-label={t('nav.profileMenu', undefined, 'Меню профиля')}
        className={cn(
          'border-primary/24 inline-flex h-8 shrink-0 items-center gap-1.5 rounded-full border bg-white px-3 text-sm font-medium text-foreground',
          'shadow-[0_14px_32px_-26px_rgba(15,23,42,0.1)] outline-none transition-all',
          'hover:bg-secondary/58 aria-expanded:border-primary/34 aria-expanded:bg-secondary/72',
          'focus-visible:ring-3 focus-visible:border-ring focus-visible:ring-ring/50 active:translate-y-px',
        )}
      >
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/15 text-xs font-semibold text-primary">
          {initials || <UserRound className="h-3.5 w-3.5" />}
        </span>
        {username ? (
          <span className="hidden max-w-[10rem] truncate sm:inline">{username}</span>
        ) : null}
        <ChevronDown className="h-3.5 w-3.5 opacity-70" />
      </PopoverTrigger>
      <PopoverContent
        align="end"
        sideOffset={10}
        className="w-60 rounded-2xl border border-slate-200 bg-white p-2 shadow-[0_30px_84px_-48px_rgba(15,23,42,0.18)]"
      >
        <div className="space-y-2">
          {username ? (
            <div className="rounded-xl bg-slate-50 px-3 py-2 text-xs text-muted-foreground">
              <p className="font-semibold text-foreground">{username}</p>
            </div>
          ) : null}
          <div className="space-y-1">
            <p className="px-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
              {t('theme.label', undefined, 'Тема')}
            </p>
            <div className="flex gap-1 px-1">
              {THEME_OPTIONS.map(({ value, icon: Icon, labelKey, fallback }) => {
                const isActive = theme === value;
                return (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setTheme(value)}
                    aria-pressed={isActive}
                    className={cn(
                      'flex flex-1 flex-col items-center gap-1 rounded-xl border px-2 py-2 text-xs font-medium transition',
                      isActive
                        ? 'border-primary/30 bg-primary/10 text-foreground'
                        : 'border-transparent bg-transparent text-muted-foreground hover:bg-slate-50',
                    )}
                  >
                    <Icon className="h-4 w-4" />
                    {t(labelKey, undefined, fallback)}
                  </button>
                );
              })}
            </div>
          </div>
          <button
            type="button"
            onClick={() => {
              setIsOpen(false);
              onLogout();
            }}
            className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium text-destructive transition hover:bg-destructive/10"
          >
            <LogOut className="h-4 w-4" />
            {t('common.logout', undefined, 'Выход')}
          </button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
