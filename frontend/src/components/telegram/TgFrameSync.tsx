'use client';

/**
 * Синхронизация Telegram-инсетов в CSS-переменные на :root.
 *
 * Зачем: в full-screen Mini App Telegram рисует свои pill-ы поверх WebView
 * (слева — «Закрыть», справа — меню). CSS `env(safe-area-inset-top)` про
 * них НЕ знает — env() возвращает только системные insets (notch / home
 * indicator). Чтобы topbar не оказался под Telegram-кнопками, читаем
 * `WebApp.contentSafeAreaInset` (Bot API 8.0+) и складываем с
 * `safeAreaInset` (system).
 *
 * Получившиеся значения кладём в CSS-переменные:
 *   --tg-safe-top    --tg-safe-bottom
 *   --tg-safe-left   --tg-safe-right
 *
 * CSS пользуется как `max(env(safe-area-inset-top), var(--tg-safe-top, 0px))`
 * — на не-Telegram страницах var() даст 0 и сработает env() (или ничего на
 * десктопе).
 *
 * Подписываемся на все события которые могут изменить layout:
 *   safeAreaChanged, contentSafeAreaChanged, viewportChanged, fullscreenChanged.
 *
 * Компонент монтируется в root layout — переменные живут пока открыто
 * Mini App, переживают навигацию (root layout не размонтируется в Next).
 */

import { useEffect } from 'react';

import type { TgInset } from '@/types/telegram';
import '@/types/telegram';

const ZERO: TgInset = { top: 0, bottom: 0, left: 0, right: 0 };
const EVENTS = [
  'safeAreaChanged',
  'contentSafeAreaChanged',
  'viewportChanged',
  'fullscreenChanged',
] as const;

export default function TgFrameSync() {
  useEffect(() => {
    let cancelled = false;
    let unsubscribe: (() => void) | null = null;

    const apply = () => {
      const tg = window.Telegram?.WebApp;
      if (!tg) return;
      const sa = tg.safeAreaInset ?? ZERO;
      const ca = tg.contentSafeAreaInset ?? ZERO;
      const root = document.documentElement;
      root.style.setProperty('--tg-safe-top', `${sa.top + ca.top}px`);
      root.style.setProperty('--tg-safe-bottom', `${sa.bottom + ca.bottom}px`);
      root.style.setProperty('--tg-safe-left', `${sa.left + ca.left}px`);
      root.style.setProperty('--tg-safe-right', `${sa.right + ca.right}px`);
    };

    // SDK может быть ещё не загружен (next/script afterInteractive).
    // Поллим до ~5с и сдаёмся — на не-Telegram страницах WebApp не появится.
    let tries = 0;
    const connect = () => {
      if (cancelled) return;
      const tg = window.Telegram?.WebApp;
      if (!tg) {
        tries += 1;
        if (tries < 50) setTimeout(connect, 100);
        return;
      }

      apply();

      if (typeof tg.onEvent === 'function') {
        for (const ev of EVENTS) tg.onEvent(ev, apply);
        unsubscribe = () => {
          for (const ev of EVENTS) tg.offEvent?.(ev, apply);
        };
      }
    };
    connect();

    return () => {
      cancelled = true;
      unsubscribe?.();
    };
  }, []);

  return null;
}
