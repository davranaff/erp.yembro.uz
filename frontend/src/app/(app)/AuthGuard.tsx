'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

import { useAuth } from '@/contexts/AuthContext';
import { getAccessToken } from '@/lib/tokens';

/**
 * Клиентская часть auth-проверки:
 *  - если нет access-токена → /login
 *  - useUser() в AuthContext автоматически словит 401 и редиректнет
 *  - если у юзера нет ни одной организации → /login (с маркером)
 *  - если activeOrg в cookie не входит в memberships → выставляем первую доступную
 */
export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, isLoading, isError, org, setOrg } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (!getAccessToken()) {
      router.replace('/login');
    }
  }, [router]);

  useEffect(() => {
    if (isError) {
      router.replace('/login');
    }
  }, [isError, router]);

  useEffect(() => {
    if (!user) return;
    const memberships = user.memberships ?? [];
    if (memberships.length === 0) {
      router.replace('/login?error=no-org');
      return;
    }
    // org из cookie может оказаться невалидной — синхронизируем.
    const valid = org && memberships.find((m) => m.organization.code === org.code);
    if (!valid) {
      const first = memberships[0].organization;
      setOrg({ code: first.code, name: first.name });
    }
  }, [user, org, setOrg, router]);

  if (isLoading || !user) {
    return (
      <div style={{ padding: 32, fontSize: 13, color: 'var(--fg-3)' }}>
        Загрузка…
      </div>
    );
  }

  return <>{children}</>;
}
