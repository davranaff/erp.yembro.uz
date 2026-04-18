import { LogOut, Moon, Search, Sun } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { useAuthStore } from '@/shared/auth/auth-store';
import { useI18n } from '@/shared/i18n/i18n';
import type { Locale } from '@/shared/i18n/types';
import { useAppStore } from '@/shared/state/app-store';
import { Kbd } from '@/shared/ui/kbd';

export function TopBar({ title, right }: { title: React.ReactNode; right?: React.ReactNode }) {
  const { t, locale, setLocale } = useI18n();
  const navigate = useNavigate();
  const setCommandOpen = useAppStore((s) => s.setCommandOpen);
  const theme = useAppStore((s) => s.theme);
  const toggleTheme = useAppStore((s) => s.toggleTheme);
  const session = useAuthStore((s) => s.session);
  const logout = useAuthStore((s) => s.logout);

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  return (
    <header className="flex h-11 shrink-0 items-center justify-between gap-3 border-b border-line bg-bg-surface/80 px-3 backdrop-blur">
      <div className="flex min-w-0 items-center gap-2">
        <div className="truncate text-sm font-medium text-ink">{title}</div>
      </div>

      <div className="flex items-center gap-1.5">
        {right}

        <button
          type="button"
          onClick={() => setCommandOpen(true)}
          className="flex h-7 items-center gap-2 rounded border border-line bg-bg-subtle px-2 text-xs text-ink-muted transition-colors hover:border-line-strong hover:text-ink"
        >
          <Search className="h-3 w-3" />
          <span className="hidden sm:inline">{t('shell.search')}</span>
          <Kbd>⌘K</Kbd>
        </button>

        <div className="mx-1 h-4 w-px bg-line" />

        <select
          value={locale}
          onChange={(e) => setLocale(e.target.value as Locale)}
          className="h-7 rounded border border-line bg-bg-subtle px-2 text-xs text-ink-soft hover:border-line-strong"
        >
          <option value="ru">RU</option>
          <option value="uz">UZ</option>
          <option value="en">EN</option>
        </select>

        <button
          type="button"
          onClick={toggleTheme}
          className="flex h-7 w-7 items-center justify-center rounded border border-line bg-bg-subtle text-ink-muted hover:border-line-strong hover:text-ink"
          title={theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}
        >
          {theme === 'dark' ? <Sun className="h-3 w-3" /> : <Moon className="h-3 w-3" />}
        </button>

        {session ? (
          <>
            <div className="ml-1 flex items-center gap-2 rounded border border-line bg-bg-subtle px-2 py-1 text-xs">
              <span className="max-w-[140px] truncate text-ink">
                {session.fullName || session.email || session.employeeId}
              </span>
            </div>
            <button
              type="button"
              onClick={handleLogout}
              className="flex h-7 w-7 items-center justify-center rounded border border-line bg-bg-subtle text-ink-muted hover:border-danger/40 hover:text-danger"
              title={t('nav.logout')}
            >
              <LogOut className="h-3 w-3" />
            </button>
          </>
        ) : null}
      </div>
    </header>
  );
}
