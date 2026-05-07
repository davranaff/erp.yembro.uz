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
  ready?: () => void;
  expand?: () => void;
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
          minHeight: '100vh',
          display: 'grid',
          placeItems: 'center',
          background: 'var(--bg)',
          color: 'var(--fg-3)',
          fontSize: 13,
          padding: 24,
          textAlign: 'center',
        }}
      >
        Авторизация через Telegram…
      </div>
    </>
  );
}
