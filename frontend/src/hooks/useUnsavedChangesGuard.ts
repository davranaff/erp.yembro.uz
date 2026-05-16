'use client';

import { useCallback, useEffect, useRef, useState, type MouseEvent } from 'react';

const CLOSE_KEYWORDS = ['закрыть', 'отмена', 'cancel', 'close'];

function isCloseButtonTarget(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) return false;
  const button = target.closest('button, a, [role="button"]');
  if (!button) return false;

  const ariaLabel = button.getAttribute('aria-label')?.toLowerCase();
  const title = button.getAttribute('title')?.toLowerCase();
  const text = button.textContent?.trim().toLowerCase();

  if (ariaLabel && CLOSE_KEYWORDS.some((keyword) => ariaLabel.includes(keyword))) {
    return true;
  }
  if (title && CLOSE_KEYWORDS.some((keyword) => title.includes(keyword))) {
    return true;
  }
  if (text && CLOSE_KEYWORDS.some((keyword) => text === keyword || text.startsWith(`${keyword} `) || text.endsWith(` ${keyword}`) || text.includes(` ${keyword} `))) {
    return true;
  }

  return false;
}

export function useUnsavedChangesGuard(onClose: () => void) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [dirty, setDirty] = useState(false);

  const handleClose = useCallback(() => {
    if (dirty) {
      if (!window.confirm('В форме есть несохранённые изменения. Закрыть без сохранения?')) {
        return;
      }
    }
    onClose();
  }, [dirty, onClose]);

  const handleClickCapture = useCallback(
    (event: MouseEvent<HTMLDivElement>) => {
      if (!dirty) return;
      if (isCloseButtonTarget(event.target)) {
        if (!window.confirm('В форме есть несохранённые изменения. Закрыть без сохранения?')) {
          event.preventDefault();
          event.stopPropagation();
        }
      }
    },
    [dirty],
  );

  useEffect(() => {
    const root = containerRef.current;
    if (!root) return;

    const markDirty = () => {
      setDirty(true);
    };

    root.addEventListener('input', markDirty, true);
    root.addEventListener('change', markDirty, true);

    return () => {
      root.removeEventListener('input', markDirty, true);
      root.removeEventListener('change', markDirty, true);
    };
  }, []);

  return { containerRef, handleClose, handleClickCapture };
}
