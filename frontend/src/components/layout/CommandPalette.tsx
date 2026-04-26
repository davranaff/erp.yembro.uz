'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';

import Icon from '@/components/ui/Icon';
import { useAuth } from '@/contexts/AuthContext';
import { useNavigationStatus } from '@/contexts/NavigationContext';
import { useRecentPages } from '@/lib/recentPages';

import { flatItems, isGroup, NAV, type NavItem } from './nav';

interface Props {
  open: boolean;
  onClose: () => void;
}

interface Match {
  item: NavItem;
  group: string | null;
  /** Меньше = лучше совпадение (для сортировки). */
  score: number;
}

/**
 * Командная палитра (⌘K).
 *
 * Поиск идёт по `label`, `aliases`, имени группы и пути. Сортировка:
 * 1. exact prefix match по label, 2. prefix по alias, 3. infix по label,
 * 4. infix по alias / group / href.
 *
 * Возвращает только страницы, к которым у пользователя есть доступ
 * (RBAC через `hasLevel(module, 'r')`). Без поискового запроса — топ-10
 * закреплённых + первые 10 разрешённых.
 */
export default function CommandPalette({ open, onClose }: Props) {
  const router = useRouter();
  const { hasLevel } = useAuth();
  const { startNavigation, isNavigating } = useNavigationStatus();
  const recentHrefs = useRecentPages();
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Фокус на input при открытии + сброс
  useEffect(() => {
    if (open) {
      setQuery('');
      setActive(0);
      // Дать DOM отрендериться, потом focus
      const t = setTimeout(() => inputRef.current?.focus(), 30);
      return () => clearTimeout(t);
    }
  }, [open]);

  // Глобальные клавиши: только пока открыто
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, onClose]);

  // Группа для каждого NavItem (вычисляем один раз)
  const itemGroups = useMemo(() => {
    const map = new Map<string, string | null>();
    let currentGroup: string | null = null;
    for (const e of NAV) {
      if (isGroup(e)) {
        currentGroup = e.group;
      } else {
        map.set(e.key, currentGroup);
      }
    }
    return map;
  }, []);

  const allowed = (it: NavItem) => {
    if (!it.module) return true;
    return hasLevel(it.module, it.min ?? 'r');
  };

  const matches: Match[] = useMemo(() => {
    const items = flatItems().filter(allowed);
    const q = query.trim().toLowerCase();

    if (!q) {
      // Без запроса — сверху недавние посещённые, потом топ-N разрешённых
      const itemsByHref = new Map(items.map((i) => [i.href, i]));
      const recent: NavItem[] = [];
      const seenHrefs = new Set<string>();
      for (const href of recentHrefs) {
        const it = itemsByHref.get(href);
        if (it && !seenHrefs.has(href)) {
          recent.push(it);
          seenHrefs.add(href);
        }
        if (recent.length >= 5) break;
      }
      const pinned = items.filter((i) => i.pin && !seenHrefs.has(i.href));
      const rest = items
        .filter((i) => !i.pin && !seenHrefs.has(i.href))
        .slice(0, Math.max(0, 12 - recent.length - pinned.length));

      return [...recent, ...pinned, ...rest].map((item, idx) => ({
        item,
        group: idx < recent.length
          ? '↻ Недавние'
          : (itemGroups.get(item.key) ?? null),
        score: 0,
      }));
    }

    const out: Match[] = [];
    for (const item of items) {
      const label = item.label.toLowerCase();
      const aliases = (item.aliases ?? []).map((a) => a.toLowerCase());
      const group = (itemGroups.get(item.key) ?? '').toLowerCase();
      const href = item.href.toLowerCase();

      let score = 999;
      if (label === q) score = 0;
      else if (label.startsWith(q)) score = 1;
      else if (aliases.some((a) => a === q)) score = 2;
      else if (aliases.some((a) => a.startsWith(q))) score = 3;
      else if (label.includes(q)) score = 4;
      else if (aliases.some((a) => a.includes(q))) score = 5;
      else if (group.includes(q)) score = 6;
      else if (href.includes(q)) score = 7;
      else continue;

      out.push({ item, group: itemGroups.get(item.key) ?? null, score });
    }
    out.sort((a, b) => a.score - b.score || a.item.label.localeCompare(b.item.label));
    return out.slice(0, 30);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, itemGroups, recentHrefs]);

  // Если активная позиция вылезает за границы — выровнять
  useEffect(() => {
    if (active >= matches.length) setActive(Math.max(0, matches.length - 1));
  }, [active, matches.length]);

  // Прокрутка активного в видимую часть
  useEffect(() => {
    if (!listRef.current) return;
    const el = listRef.current.querySelector<HTMLElement>(
      `[data-idx="${active}"]`,
    );
    el?.scrollIntoView({ block: 'nearest' });
  }, [active]);

  if (!open) return null;

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActive((a) => Math.min(matches.length - 1, a + 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActive((a) => Math.max(0, a - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const m = matches[active];
      if (m) navigate(m.item.href);
    }
  };

  const navigate = (href: string) => {
    onClose();
    if (isNavigating) return;
    startNavigation(href);
    router.push(href);
  };

  return (
    <div
      className="cp-backdrop"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Поиск страниц"
    >
      <div className="cp-shell" onClick={(e) => e.stopPropagation()}>
        <div className="cp-input-wrap">
          <Icon name="search" size={16} />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActive(0);
            }}
            onKeyDown={onKeyDown}
            className="cp-input"
            placeholder="Поиск страницы или действия…"
          />
          <span className="cp-hint">
            <kbd>↑↓</kbd> навигация · <kbd>Enter</kbd> открыть · <kbd>Esc</kbd> закрыть
          </span>
        </div>

        <div className="cp-list" ref={listRef}>
          {matches.length === 0 && (
            <div className="cp-empty">
              Ничего не нашлось. Попробуйте «закуп», «склад» или «отчёты».
            </div>
          )}
          {matches.map((m, i) => (
            <button
              key={m.item.key}
              data-idx={i}
              className={'cp-item' + (i === active ? ' active' : '')}
              onMouseEnter={() => setActive(i)}
              onClick={() => navigate(m.item.href)}
              type="button"
            >
              <Icon name={m.item.icon} size={16} />
              <div className="cp-item-text">
                <div className="cp-item-label">{m.item.label}</div>
                <div className="cp-item-meta">
                  {m.group && <span>{m.group}</span>}
                  <span className="mono">{m.item.href}</span>
                </div>
              </div>
              <Icon name="arrow-right" size={14} />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
