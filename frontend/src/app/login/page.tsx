'use client';

import { Suspense, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';

import Icon from '@/components/ui/Icon';
import { ApiError, apiFetch } from '@/lib/api';
import { ME_QUERY_KEY } from '@/hooks/useUser';
import { setTokens, writeOrgCookie } from '@/lib/tokens';
import type { Membership, TokenPair, User } from '@/types/auth';

type Step = 'login' | 'company';

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="login-screen" />}>
      <LoginInner />
    </Suspense>
  );
}

function Logo() {
  // logo.png — 2723x851 (~3.2:1). Высота 36 → ширина ≈ 115.
  return (
    <img
      src="/logo.png"
      alt="YemBro ERP"
      style={{ height: 36, width: 'auto', objectFit: 'contain', display: 'block' }}
    />
  );
}

function LoginInner() {
  const router = useRouter();
  const search = useSearchParams();
  const queryClient = useQueryClient();
  const nextPath = search.get('next') ?? '/dashboard';
  const errorParam = search.get('error');

  const [step, setStep] = useState<Step>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [memberships, setMemberships] = useState<Membership[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(
    errorParam === 'no-org' ? 'У вашего аккаунта нет активных организаций.' : null,
  );

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Заполните email и пароль.');
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      // Чистим React Query кеш ПЕРЕД логином — иначе если в этой
      // вкладке раньше был залогинен другой юзер (или этот же с другими
      // правами), Sidebar/permissions отрендерятся со старым ['me']
      // до того как новый запрос отработает (staleTime 60s). Симптом:
      // юзер видит nav-пункты предыдущего пользователя.
      queryClient.clear();

      const tokens = await apiFetch<TokenPair>('/api/auth/token/', {
        method: 'POST',
        body: { email, password },
        skipAuth: true,
        skipOrg: true,
      });
      setTokens(tokens.access, tokens.refresh);

      const me = await apiFetch<User>('/api/users/me/', { skipOrg: true });
      // Сразу прогреваем React Query кеш свежим /me — чтобы первый рендер
      // AuthGuard/Sidebar после redirect'а увидел корректные права без
      // моргания (loading → потом обновление).
      queryClient.setQueryData(ME_QUERY_KEY, me);
      const ms = me.memberships ?? [];

      if (ms.length === 0) {
        setError('У вас нет активных организаций.');
        setSubmitting(false);
        return;
      }
      if (ms.length === 1) {
        const o = ms[0].organization;
        writeOrgCookie({ code: o.code, name: o.name });
        router.replace(nextPath);
        return;
      }

      setMemberships(ms);
      setStep('company');
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          setError('Неверный email или пароль.');
        } else if (err.status === 0 || err.status >= 500) {
          setError('Сервер недоступен. Попробуйте позже.');
        } else {
          setError(`Ошибка входа: ${err.status}`);
        }
      } else {
        setError('Сетевая ошибка. Проверьте подключение.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handlePickCompany = (m: Membership) => {
    writeOrgCookie({ code: m.organization.code, name: m.organization.name });
    router.replace(nextPath);
  };

  if (step === 'login') {
    return (
      <div className="login-screen">
        <form className="login-card" onSubmit={handleLogin} autoComplete="on">
          <div className="login-brand">
            <Logo />
          </div>
          <h2 className="login-title">Вход в систему</h2>
          <div className="login-sub">Учётная система птицеводческого предприятия</div>

          <div className="field">
            <label htmlFor="login-email">Email</label>
            <input
              id="login-email"
              className="input"
              type="email"
              autoComplete="username"
              placeholder="user@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={submitting}
              required
              autoFocus
            />
          </div>

          <div className="field">
            <label htmlFor="login-password">Пароль</label>
            <div style={{ position: 'relative' }}>
              <input
                id="login-password"
                className="input"
                type={showPwd ? 'text' : 'password'}
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={submitting}
                required
                style={{ paddingRight: 38 }}
              />
              <button
                type="button"
                onClick={() => setShowPwd((v) => !v)}
                tabIndex={-1}
                aria-label={showPwd ? 'Скрыть пароль' : 'Показать пароль'}
                style={{
                  position: 'absolute',
                  right: 8,
                  top: '50%',
                  transform: 'translateY(-50%)',
                  border: 'none',
                  background: 'transparent',
                  color: 'var(--fg-3)',
                  cursor: 'pointer',
                  padding: 4,
                  display: 'grid',
                  placeItems: 'center',
                }}
              >
                <Icon name={showPwd ? 'chevron-down' : 'chevron-right'} size={14} />
              </button>
            </div>
          </div>

          {error && <div className="login-error">{error}</div>}

          <button
            type="submit"
            className="btn btn-primary login-submit"
            disabled={submitting}
          >
            {submitting ? 'Вход…' : 'Войти'}
          </button>

          <div className="login-foot">
            Проблемы со входом? Обратитесь к администратору.
          </div>
        </form>
      </div>
    );
  }

  return (
    <div className="login-screen">
      <div className="company-picker">
        <div className="login-brand">
          <Logo />
        </div>
        <h2 className="login-title">Выбор компании</h2>
        <div className="login-sub">
          {email} · доступ к {memberships.length} компаниям
        </div>
        {memberships.map((m) => (
          <div
            key={m.id}
            className="company-item"
            onClick={() => handlePickCompany(m)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') handlePickCompany(m);
            }}
          >
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: 6,
                background: 'var(--brand-orange)',
                color: 'white',
                display: 'grid',
                placeItems: 'center',
                fontSize: 13,
                fontWeight: 700,
                flexShrink: 0,
              }}
            >
              {m.organization.code.slice(0, 2).toUpperCase()}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  fontSize: 14,
                  fontWeight: 600,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {m.organization.name}
              </div>
              <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>
                {m.position_title || m.organization.direction}
              </div>
            </div>
            <Icon name="chevron-right" size={16} style={{ color: 'var(--fg-muted)' }} />
          </div>
        ))}
        <button
          type="button"
          className="btn btn-ghost"
          style={{ width: '100%', marginTop: 8, justifyContent: 'center' }}
          onClick={() => setStep('login')}
        >
          ← Назад
        </button>
      </div>
    </div>
  );
}
