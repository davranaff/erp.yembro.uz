import { useEffect, useRef } from 'react';

import { useToast } from '@/components/ui/toast';
import { useI18n } from '@/shared/i18n';

import { useAuthStore } from './auth-store';

const WARN_BEFORE_MS = 2 * 60 * 1000;

export function useSessionExpiryWarning(): void {
  const expiresAt = useAuthStore((state) => state.session?.expiresAt ?? null);
  const { show } = useToast();
  const { t } = useI18n();
  const warnedForRef = useRef<string | null>(null);

  useEffect(() => {
    if (!expiresAt) {
      return;
    }
    const expiryTime = Date.parse(expiresAt);
    if (Number.isNaN(expiryTime)) {
      return;
    }
    const warnAt = expiryTime - WARN_BEFORE_MS;
    const delay = warnAt - Date.now();

    const fire = () => {
      if (warnedForRef.current === expiresAt) {
        return;
      }
      warnedForRef.current = expiresAt;
      show({
        tone: 'warning',
        title: t('common.sessionExpiringTitle', undefined, 'Сессия скоро истечёт'),
        description: t(
          'common.sessionExpiringDescription',
          undefined,
          'Сохраните изменения и войдите заново, чтобы не потерять работу.',
        ),
        durationMs: 12_000,
      });
    };

    if (delay <= 0) {
      if (Date.now() < expiryTime) {
        fire();
      }
      return;
    }

    const timer = setTimeout(fire, delay);
    return () => clearTimeout(timer);
  }, [expiresAt, show, t]);
}
