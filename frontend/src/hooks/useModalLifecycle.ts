'use client';

/**
 * Жизненный цикл модального окна / drawer'а:
 *   - Esc → onClose
 *   - body scroll lock пока открыто (иначе на мобилке фоновая страница
 *     прокручивается под модалкой)
 *
 * Подключается в Modal и DetailDrawer. Оба раньше были «открыл — скролл
 * фона остался, Esc не работает».
 */

import { useEffect } from 'react';

export function useModalLifecycle(onClose: () => void): void {
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
      }
    };
    document.addEventListener('keydown', handleKey);

    // body-scroll-lock: фиксируем overflow и сохраняем pad чтобы не
    // прыгал layout при появлении/исчезновении вертикальной полосы.
    const html = document.documentElement;
    const prevOverflow = html.style.overflow;
    html.style.overflow = 'hidden';

    return () => {
      document.removeEventListener('keydown', handleKey);
      html.style.overflow = prevOverflow;
    };
  }, [onClose]);
}
