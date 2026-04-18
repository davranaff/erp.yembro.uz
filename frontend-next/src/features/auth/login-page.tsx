import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { ApiError } from '@/shared/api/client';
import { loginWithCredentials } from '@/shared/api/auth';
import { useAuthStore } from '@/shared/auth/auth-store';
import { useI18n } from '@/shared/i18n/i18n';
import type { Locale } from '@/shared/i18n/types';
import { Button } from '@/shared/ui/button';
import { Input } from '@/shared/ui/input';
import { Label } from '@/shared/ui/label';
import { Spinner } from '@/shared/ui/spinner';

interface LocationState {
  from?: { pathname: string };
}

export function LoginPage() {
  const { t, locale, setLocale } = useI18n();
  const navigate = useNavigate();
  const location = useLocation();
  const setSession = useAuthStore((s) => s.setSession);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const from = (location.state as LocationState | null)?.from?.pathname ?? '/dashboard';

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const data = await loginWithCredentials({ username: username.trim(), password });
      if (!data.accessToken) {
        setError(t('login.error', { message: 'no access token' }));
        return;
      }
      const expiresAt = data.expiresAt ? Date.parse(data.expiresAt) : null;
      setSession({
        employeeId: data.employeeId,
        email: null,
        fullName: null,
        organizationId: data.organizationId,
        roles: data.roles,
        permissions: data.permissions,
        accessToken: data.accessToken,
        refreshToken: data.refreshToken ?? null,
        expiresAt: Number.isFinite(expiresAt) ? expiresAt : null,
      });
      navigate(from, { replace: true });
    } catch (err) {
      const message = err instanceof ApiError ? err.message : (err as Error).message;
      setError(t('login.error', { message }));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg p-4">
      <div className="flex w-full max-w-[400px] flex-col gap-5 rounded-lg border border-line bg-bg-surface p-6 shadow-pane">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-6 w-6 items-center justify-center rounded bg-ink text-2xs font-semibold text-ink-invert">
              Y
            </div>
            <span className="text-sm font-medium tracking-tight">{t('app.brand')}</span>
          </div>
          <select
            value={locale}
            onChange={(e) => setLocale(e.target.value as Locale)}
            className="h-6 rounded border border-line bg-bg-subtle px-1.5 text-2xs text-ink-soft"
          >
            <option value="ru">RU</option>
            <option value="uz">UZ</option>
            <option value="en">EN</option>
          </select>
        </div>

        <div>
          <h1 className="text-base font-medium">{t('login.title')}</h1>
          <p className="mt-0.5 text-xs text-ink-muted">{t('login.hint')}</p>
        </div>

        <form onSubmit={submit} className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="username">{t('login.username')}</Label>
            <Input
              id="username"
              autoComplete="username"
              autoFocus
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="password">{t('login.password')}</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          {error ? (
            <div className="rounded border border-danger/40 bg-danger-soft/40 px-2.5 py-1.5 text-xs text-danger">
              {error}
            </div>
          ) : null}

          <Button type="submit" variant="primary" size="md" loading={submitting} className="mt-1">
            {submitting ? <Spinner /> : null}
            <span>{submitting ? t('login.submitting') : t('login.submit')}</span>
          </Button>
        </form>
      </div>
    </div>
  );
}
