'use client';

import { useEffect } from 'react';

/**
 * Регистрирует `/sw.js` после монтирования приложения. Только в production
 * (в dev SW мешает HMR). Тихо игнорирует ошибки если SW не поддерживается.
 */
export default function ServiceWorkerRegistration() {
  useEffect(() => {
    if (process.env.NODE_ENV !== 'production') return;
    if (typeof navigator === 'undefined' || !('serviceWorker' in navigator)) return;

    const register = async () => {
      try {
        await navigator.serviceWorker.register('/sw.js', { scope: '/' });
      } catch {
        // Ignore — оффлайн-страница это nice-to-have, не критично
      }
    };

    // Регистрируем после полной загрузки страницы чтобы не замедлять старт
    if (document.readyState === 'complete') {
      register();
    } else {
      window.addEventListener('load', register, { once: true });
    }
  }, []);

  return null;
}
