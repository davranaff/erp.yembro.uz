'use client';

import { useEffect, useRef, useState } from 'react';
import { usePathname, useSearchParams } from 'next/navigation';

import { useNavigationStatus } from '@/contexts/NavigationContext';

/**
 * Тонкая полоса-индикатор навигации сверху окна.
 *
 * Поведение:
 *  - Слушает клики по любым внутренним `<a>`.
 *  - Слушает programmatic-переходы через `window.history.pushState` / `replaceState`
 *    (Next.js router их использует).
 *  - Прогресс анимируется CSS-ключами: "старт" (0 → 80% за 0.6s с easeOut) и
 *    "финиш" (80% → 100% за 0.2s, затем fade-out).
 *  - Когда `pathname` или `searchParams` меняется — индикатор уходит.
 *  - Параллельно пишет состояние в `NavigationContext`, чтобы Sidebar и
 *    другие компоненты могли:
 *      1) показать spinner на target-ссылке,
 *      2) задизейблить навигационные клики (защита от двойного клика),
 *      3) поставить cursor=wait на body.
 *
 * Не требует сторонних библиотек (nprogress).
 */
export default function RouteProgress() {
  const pathname = usePathname();
  const search = useSearchParams();
  const { isNavigating, startNavigation, endNavigation } = useNavigationStatus();
  const [state, setState] = useState<'idle' | 'loading' | 'done'>('idle');
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const startTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Завершить полосу (пошла фаза done → fade out → idle).
  useEffect(() => {
    if (state !== 'loading') return;
    setState('done');
  }, [pathname, search, state]);

  // Сбросить флаг "navigating" сразу как pathname сменился.
  useEffect(() => {
    if (isNavigating) {
      endNavigation();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname, search]);

  // Race-safe: targetPath совпал с pathname → закрываем navigation. Нужно
  // потому что startNavigation отложен в queueMicrotask (см. ниже), и эффект
  // выше может прочитать isNavigating=false до того, как контекст обновится.
  // Также страхует от случая, когда patched pushState вызывается уже на
  // целевой странице (логин-редирект — pathname уже /dashboard к моменту,
  // когда startNavigation('/dashboard') добегает).
  useEffect(() => {
    if (isNavigating && targetPath === pathname) {
      endNavigation();
    }
  }, [isNavigating, targetPath, pathname, endNavigation]);

  // Safety: если navigation не закрылся за 5с (network-stall, ошибка) —
  // принудительно гасим спиннер, чтобы UI не залипал.
  useEffect(() => {
    if (!isNavigating) return;
    const t = setTimeout(() => endNavigation(), 5000);
    return () => clearTimeout(t);
  }, [isNavigating, endNavigation]);

  useEffect(() => {
    if (state !== 'done') return;
    hideTimer.current = setTimeout(() => setState('idle'), 260);
    return () => {
      if (hideTimer.current) clearTimeout(hideTimer.current);
    };
  }, [state]);

  // Управление cursor=wait на body во время навигации.
  useEffect(() => {
    if (typeof document === 'undefined') return;
    if (isNavigating) {
      document.body.classList.add('navigating');
    } else {
      document.body.classList.remove('navigating');
    }
  }, [isNavigating]);

  useEffect(() => {
    const start = (path: string) => {
      if (startTimer.current) clearTimeout(startTimer.current);
      startTimer.current = setTimeout(() => setState('loading'), 80);
      // setState внутри NavigationContext нельзя вызывать в render/insertion
      // фазе React. Next.js использует useInsertionEffect для prefetch и
      // вызывает в нём history.pushState — а наш monkey-patch попадает
      // ровно в этот момент. Деферим в микротаск, чтобы планирование
      // setState произошло уже после фазы.
      queueMicrotask(() => startNavigation(path));
    };

    const onClick = (e: MouseEvent) => {
      if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const target = (e.target as HTMLElement | null)?.closest('a');
      if (!target) return;
      const href = target.getAttribute('href');
      if (!href) return;
      if (target.target && target.target !== '_self') return;
      if (target.hasAttribute('download')) return;

      let url: URL;
      try {
        url = new URL(href, window.location.href);
      } catch {
        return;
      }
      if (url.origin !== window.location.origin) return;
      if (href.startsWith('#')) return;
      if (
        url.pathname === window.location.pathname &&
        url.search === window.location.search
      ) {
        return;
      }
      start(url.pathname);
    };

    // patch history, чтобы ловить router.push из Next
    const origPush = window.history.pushState;
    const origReplace = window.history.replaceState;
    window.history.pushState = function (...args) {
      const url = args[2];
      if (typeof url === 'string') {
        try {
          const u = new URL(url, window.location.href);
          start(u.pathname);
        } catch {
          /* ignore */
        }
      }
      return origPush.apply(this, args as Parameters<typeof origPush>);
    };
    window.history.replaceState = function (...args) {
      const url = args[2];
      if (typeof url === 'string') {
        try {
          const u = new URL(url, window.location.href);
          start(u.pathname);
        } catch {
          /* ignore */
        }
      }
      return origReplace.apply(this, args as Parameters<typeof origReplace>);
    };
    const onPopState = () => start(window.location.pathname);

    document.addEventListener('click', onClick, { capture: true });
    window.addEventListener('popstate', onPopState);

    return () => {
      document.removeEventListener('click', onClick, { capture: true } as unknown as EventListenerOptions);
      window.removeEventListener('popstate', onPopState);
      window.history.pushState = origPush;
      window.history.replaceState = origReplace;
      if (startTimer.current) clearTimeout(startTimer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (state === 'idle') return null;

  return <div className={`route-progress route-progress-${state}`} aria-hidden />;
}
