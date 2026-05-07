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

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import Script from 'next/script';
import { useQueryClient } from '@tanstack/react-query';

import { ApiError, apiFetch } from '@/lib/api';
import { ME_QUERY_KEY } from '@/hooks/useUser';
import { setTokens, writeOrgCookie } from '@/lib/tokens';
import type { User } from '@/types/auth';

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

interface TelegramWebAppLite {
  initData: string;
  version?: string;
  isFullscreen?: boolean;
  ready?: () => void;
  expand?: () => void;
  /** Bot API 8.0+. На desktop / старых клиентах метода нет — оборачиваем в try/catch. */
  requestFullscreen?: () => void;
  /** Bot API 8.0+. true → iOS swipe-down не свернёт WebApp при скролле. */
  disableVerticalSwipes?: () => void;
  isVersionAtLeast?: (v: string) => boolean;
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebAppLite };
  }
}

export default function TgMiniAppPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [sdkReady, setSdkReady] = useState(false);
  // Защита от повторного auth при HMR/StrictMode dev double-invoke.
  const startedRef = useRef(false);

  useEffect(() => {
    if (!sdkReady || startedRef.current) return;
    startedRef.current = true;

    const tg = typeof window !== 'undefined' ? window.Telegram?.WebApp : undefined;
    const initData = tg?.initData ?? '';

    // Если страница открыта вне Telegram (например DevTools) — initData пуст.
    // Отправлять нечего, сразу на лендинг.
    if (!initData) {
      router.replace('/');
      return;
    }

    tg?.ready?.();
    tg?.expand?.();

    // Bot API 8.0+: переключаем в full-screen на телефоне. На desktop /
    // старых клиентах метода может не быть (или он бросит "UNSUPPORTED")
    // — игнорируем, expand() уже даст max-height в обычном режиме.
    try {
      if (tg?.isVersionAtLeast?.('8.0') && !tg.isFullscreen) {
        tg.requestFullscreen?.();
        // В full-screen iOS swipe-down закроет WebApp на любом скролле —
        // отключаем вертикальный жест, чтобы юзер не сворачивал нас
        // случайно при прокрутке таблиц.
        tg.disableVerticalSwipes?.();
      }
    } catch {
      // Telegram <8.0 / desktop — silent. UI остаётся в expand-режиме.
    }

    (async () => {
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
        // 401 (битая подпись / просрочено) и любые сетевые — на лендинг.
        // Логируем чтобы при отладке Mini App видеть в DevTools.
        // eslint-disable-next-line no-console
        console.error('Mini App auth failed', err instanceof ApiError ? err.status : err);
        router.replace('/');
      }
    })();
  }, [sdkReady, router, queryClient]);

  return (
    <>
      <Script
        src="https://telegram.org/js/telegram-web-app.js"
        strategy="afterInteractive"
        onLoad={() => setSdkReady(true)}
        onError={() => router.replace('/')}
      />
      <div
        style={{
          // 100dvh + safe-area: в full-screen Mini App статус-бар iOS / home
          // indicator не налезают на текст.
          minHeight: '100dvh',
          display: 'grid',
          placeItems: 'center',
          background: 'var(--bg)',
          color: 'var(--fg-3)',
          fontSize: 13,
          paddingTop: 'max(24px, env(safe-area-inset-top))',
          paddingBottom: 'max(24px, env(safe-area-inset-bottom))',
          paddingLeft: 'max(24px, env(safe-area-inset-left))',
          paddingRight: 'max(24px, env(safe-area-inset-right))',
          textAlign: 'center',
        }}
      >
        Авторизация через Telegram…
      </div>
    </>
  );
}
