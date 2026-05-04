'use client';

import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

interface Props {
  /** Короткая подсказка для tooltip (нативный title). */
  text: string;
  /**
   * Расширенное описание — раскрывается в popover при клике.
   * Если не задано, по клику ничего не открывается, остаётся только tooltip.
   */
  details?: string;
  size?: number;
}

/**
 * Универсальная подсказка-«?» для сложных полей форм.
 *
 * Popover рендерится через React Portal в `document.body`, чтобы не обрезаться
 * родительскими контейнерами с `overflow:hidden/auto` (модалки, drawer'ы и т.д.).
 * Позиция вычисляется по координатам кнопки на каждое открытие.
 *
 *   <label>
 *     Фактическая влажность
 *     <HelpHint
 *       text="Влажность из лаборатории."
 *       details="Базисная влажность (14% для зерна)…"
 *     />
 *   </label>
 */
export default function HelpHint({ text, details, size = 14 }: Props) {
  const [open, setOpen] = useState(false);
  const [hover, setHover] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const btnRef = useRef<HTMLButtonElement | null>(null);
  const popRef = useRef<HTMLDivElement | null>(null);

  // Видим popover если открыт по клику ИЛИ при hover
  const visible = open || hover;

  useEffect(() => {
    setMounted(true);
  }, []);

  // Закрыть по клику снаружи / Escape
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      const t = e.target as Node;
      if (
        btnRef.current && !btnRef.current.contains(t)
        && popRef.current && !popRef.current.contains(t)
      ) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    const onScroll = () => setOpen(false);
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    window.addEventListener('scroll', onScroll, true);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
      window.removeEventListener('scroll', onScroll, true);
    };
  }, [open]);

  // Расчёт позиции popover'а после открытия (с учётом краёв окна)
  useLayoutEffect(() => {
    if (!visible || !btnRef.current) return;
    const r = btnRef.current.getBoundingClientRect();
    const W = 320;
    const margin = 8;
    let left = r.left;
    if (left + W > window.innerWidth - margin) {
      left = window.innerWidth - W - margin;
    }
    if (left < margin) left = margin;
    setPos({ top: r.bottom + 6, left });
  }, [visible]);

  return (
    <>
      <span
        style={{ position: 'relative', display: 'inline-block', marginLeft: 4 }}
        onClick={(e) => e.stopPropagation()}
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
      >
        <button
          ref={btnRef}
          type="button"
          aria-label={text}
          onClick={(e) => {
            e.preventDefault();
            if (details) setOpen((v) => !v);
          }}
          style={{
            width: size + 4,
            height: size + 4,
            borderRadius: '50%',
            border: '1px solid var(--border)',
            background: visible ? 'var(--brand-orange)' : 'var(--bg-soft)',
            color: visible ? '#fff' : 'var(--fg-3)',
            fontSize: size - 3,
            fontWeight: 600,
            cursor: details ? 'pointer' : 'help',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 0,
            lineHeight: 1,
          }}
        >
          ?
        </button>
      </span>

      {mounted && visible && pos && createPortal(
        <div
          ref={popRef}
          role="tooltip"
          onClick={(e) => e.stopPropagation()}
          onMouseEnter={() => setHover(true)}
          onMouseLeave={() => setHover(false)}
          style={{
            position: 'fixed',
            top: pos.top,
            left: pos.left,
            zIndex: 10000,
            maxWidth: 320,
            padding: details ? '10px 12px' : '8px 10px',
            background: '#1F2937',  // тёмный фон для контраста
            border: 'none',
            borderRadius: 6,
            boxShadow: '0 4px 12px rgba(0,0,0,.25)',
            fontSize: 12,
            lineHeight: 1.45,
            color: '#fff',
            whiteSpace: 'normal',
            pointerEvents: 'auto',
          }}
        >
          {details ? (
            <>
              <div style={{ fontWeight: 600, marginBottom: 4, color: '#fff' }}>
                {text}
              </div>
              <div style={{ color: '#D1D5DB' }}>{details}</div>
            </>
          ) : (
            <div style={{ color: '#fff' }}>{text}</div>
          )}
        </div>,
        document.body,
      )}
    </>
  );
}
