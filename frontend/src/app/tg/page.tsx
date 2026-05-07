'use client';

/**
 * Telegram Mini App entrypoint.
 *
 * Запускается из @yembro_bot (BotFather → Bot Settings → Menu Button или
 * команда /start с web_app кнопкой). Telegram открывает наш URL в WebView,
 * предоставляет `window.Telegram.WebApp` со подписанным `initData`.
 *
 * Flow:
 *   1. Грузим telegram-web-app.js (sdk-скрипт от Telegram).
 *   2. Читаем initData → POST /api/tg/miniapp/auth/.
 *   3. Если бэк вернул `linked: false` (нет user-привязки для chat_id) —
 *      редирект на лендинг `/`.
 *   4. Если ok — кладём JWT в localStorage, ставим org-cookie, прогреваем
 *      ['me'] в react-query и идём на /dashboard.
 *   5. Любая ошибка сети/подписи → редирект на `/` (юзер ничего не может
 *      сделать без бота, сообщение бесполезно).
 *
 * Маршрут добавлен в PUBLIC_PATHS middleware — без cookie `erp.org` сюда
 * можно зайти.
 */

import { useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import { ME_QUERY_KEY } from '@/hooks/useUser';
import { setTokens, writeOrgCookie } from '@/lib/tokens';
import type { User } from '@/types/auth';
import '@/types/telegram';

interface MiniAppAuthLinked {
  linked: true;
  access: string;
  refresh: string;
  user: User;
  preferred_org: { code: string; name: string };
}

interface MiniAppAuthUnlinked {
  linked: false;
}

type MiniAppAuthResponse = MiniAppAuthLinked | MiniAppAuthUnlinked;

export default function TgMiniAppPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  // Защита от повторного auth при HMR/StrictMode dev double-invoke.
  const startedRef = useRef(false);

  useEffect(() => {
    if (startedRef.current) return;

    // SDK грузится в root layout (afterInteractive). К моменту mount /tg
    // он может быть ещё не готов — ждём появления WebApp до 5с.
    let cancelled = false;
    let tries = 0;

    const start = () => {
      if (cancelled || startedRef.current) return;
      const tg = window.Telegram?.WebApp;
      if (!tg) {
        tries += 1;
        if (tries < 50) {
          setTimeout(start, 100);
          return;
        }
        // SDK не приехал — мы не в Telegram, идём на лендинг.
        router.replace('/');
        return;
      }
      startedRef.current = true;

      const initData = tg.initData ?? '';
      if (!initData) {
        router.replace('/');
        return;
      }

      tg.ready?.();
      tg.expand?.();

      // Bot API 8.0+: переключаем в full-screen на телефоне. На desktop /
      // старых клиентах метода может не быть — игнорируем, expand() даёт
      // max-height в обычном режиме.
      try {
        if (tg.isVersionAtLeast?.('8.0') && !tg.isFullscreen) {
          tg.requestFullscreen?.();
          tg.disableVerticalSwipes?.();
        }
      } catch {
        /* Telegram <8.0 / desktop — silent. */
      }

      void (async () => {
        try {
          const res = await apiFetch<MiniAppAuthResponse>('/api/tg/miniapp/auth/', {
            method: 'POST',
            body: { init_data: initData },
            skipAuth: true,
            skipOrg: true,
          });

          if (!res.linked) {
            router.replace('/');
            return;
          }

          setTokens(res.access, res.refresh);
          writeOrgCookie(res.preferred_org);
          queryClient.setQueryData(ME_QUERY_KEY, res.user);
          router.replace('/dashboard');
        } catch (err) {
          // eslint-disable-next-line no-console
          console.error('Mini App auth failed', err instanceof ApiError ? err.status : err);
          router.replace('/');
        }
      })();
    };

    start();
    return () => {
      cancelled = true;
    };
  }, [router, queryClient]);

  return (
    <div
      style={{
        // 100dvh + safe-area: в full-screen Mini App Telegram-pill'ы и
        // home indicator не налезают на текст. --tg-safe-* проставляются
        // TgFrameSync из root layout.
        minHeight: '100dvh',
        display: 'grid',
        placeItems: 'center',
        background: 'var(--bg)',
        color: 'var(--fg-3)',
        fontSize: 13,
        paddingTop: 'max(24px, env(safe-area-inset-top), var(--tg-safe-top, 0px))',
        paddingBottom: 'max(24px, env(safe-area-inset-bottom), var(--tg-safe-bottom, 0px))',
        paddingLeft: 'max(24px, env(safe-area-inset-left), var(--tg-safe-left, 0px))',
        paddingRight: 'max(24px, env(safe-area-inset-right), var(--tg-safe-right, 0px))',
        textAlign: 'center',
      }}
    >
      Авторизация через Telegram…
    </div>
  );
}
