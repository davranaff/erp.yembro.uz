import { useEffect, useRef } from 'react';

import { getMyProfile } from '@/shared/api/auth';
import { ApiError } from '@/shared/api/errors';

import { useAuthStore } from './auth-store';

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const hydrate = useAuthStore((s) => s.hydrate);
  const session = useAuthStore((s) => s.session);
  const setSession = useAuthStore((s) => s.setSession);
  const isInitialized = useAuthStore((s) => s.isInitialized);
  const hydrated = useRef(false);

  useEffect(() => {
    if (hydrated.current) return;
    hydrated.current = true;
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    if (!isInitialized || !session) return;
    let cancelled = false;
    getMyProfile()
      .then((profile) => {
        if (cancelled) return;
        setSession({
          ...session,
          email: profile.email ?? session.email,
          fullName: [profile.firstName, profile.lastName].filter(Boolean).join(' ') || null,
          organizationId: profile.organizationId,
          roles: profile.roles,
          permissions: profile.permissions,
        });
      })
      .catch((error) => {
        if (cancelled) return;
        if (error instanceof ApiError && error.status === 401) {
          setSession(null);
        }
      });
    return () => {
      cancelled = true;
    };
    // Only run once after hydration
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isInitialized]);

  return <>{children}</>;
}
