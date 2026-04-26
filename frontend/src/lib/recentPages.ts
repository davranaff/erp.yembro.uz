'use client';

import { useEffect, useState } from 'react';
import { usePathname } from 'next/navigation';

/**
 * Последние посещённые страницы для CommandPalette.
 *
 * Хранятся в localStorage (не критичные данные, синк между устройствами не нужен).
 * Запоминаем только pathname-и, которые есть в nav.ts (label резолвится через
 * labelForHref на фронте — не надо хранить локально).
 *
 * MRU (most-recently-used) порядок, последняя — самая свежая.
 */

const STORAGE_KEY = 'recent-pages';
const MAX = 8;

function read(): string[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((p): p is string => typeof p === 'string') : [];
  } catch {
    return [];
  }
}

function write(items: string[]) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(0, MAX)));
  } catch {
    /* quota / private mode */
  }
}

/** Помечает текущий pathname как «недавно посещённый». */
export function useTrackRecentPage() {
  const pathname = usePathname();
  useEffect(() => {
    if (!pathname || pathname === '/' || pathname === '/login') return;
    const current = read();
    // Удаляем дубликат если есть, ставим в начало
    const next = [pathname, ...current.filter((p) => p !== pathname)];
    write(next);
  }, [pathname]);
}

/** Читает список недавних страниц. */
export function useRecentPages(): string[] {
  const [items, setItems] = useState<string[]>([]);
  useEffect(() => {
    setItems(read());
  }, []);
  return items;
}

/** Очистить историю (например по кнопке). */
export function clearRecentPages() {
  write([]);
}
