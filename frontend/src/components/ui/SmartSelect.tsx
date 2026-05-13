'use client';

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

import Icon from './Icon';

export interface SmartSelectOption {
  value: string;
  /** Главная строка опции (то что покажется как выбранное значение). */
  label: string;
  /** Доп. описание справа/мелким — например доли, остатки, тип. */
  sublabel?: string;
  /** True → опция показывается серой и не кликабельна. */
  disabled?: boolean;
}

interface Props {
  /** Выбранный value. Пустая строка = ничего не выбрано. */
  value: string;
  /** Колбэк. Передаётся value пустой строкой при очистке. */
  onChange: (value: string) => void;
  /** Список опций. */
  options: SmartSelectOption[];
  /** Placeholder когда ничего не выбрано. */
  placeholder?: string;
  /** Текст когда `options=[]`. */
  emptyText?: string;
  /** Дополнительный текст в поиске. */
  searchPlaceholder?: string;
  disabled?: boolean;
  /** Доп. CSS-класс на корневой div. */
  className?: string;
  /** Inline-стиль на корневой div. */
  style?: React.CSSProperties;
  /** Скрывать кнопку «очистить» (если выбор обязательный). */
  hideClear?: boolean;
}

/**
 * Универсальный autocomplete-select: dropdown с поиском, клавиатурой и
 * подсветкой текущего выбора. Заменяет нативный `<select>` для списков
 * где нужен фильтр по тексту (контрагенты, склады, номенклатура,
 * сотрудники и т.п.).
 *
 * API совместим со стандартным паттерном:
 *   const [v, setV] = useState('');
 *   <SmartSelect value={v} onChange={setV} options={[{value, label}, …]} />
 */
export default function SmartSelect({
  value,
  onChange,
  options,
  placeholder = '— выберите —',
  emptyText = 'Нет данных',
  searchPlaceholder = 'Поиск…',
  disabled,
  className,
  style,
  hideClear,
}: Props) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [highlighted, setHighlighted] = useState(0);
  // Координаты дропдауна в viewport (для портала). Считаются от
  // bounding-rect триггера. Пересчитываются на scroll/resize пока открыт.
  const [pos, setPos] = useState<{ top: number; left: number; width: number; flipUp: boolean } | null>(null);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const dropdownRef = useRef<HTMLDivElement | null>(null);
  const searchRef = useRef<HTMLInputElement | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);

  // Рассчитать позицию дропдауна. Если внизу мало места и сверху больше —
  // открываемся вверх.
  const recalcPosition = () => {
    const trigger = triggerRef.current;
    if (!trigger) return;
    const r = trigger.getBoundingClientRect();
    const DROPDOWN_MAX_H = 320;
    const spaceBelow = window.innerHeight - r.bottom;
    const spaceAbove = r.top;
    const flipUp = spaceBelow < DROPDOWN_MAX_H && spaceAbove > spaceBelow;
    setPos({
      top: flipUp ? r.top - 4 : r.bottom + 4,
      left: r.left,
      width: r.width,
      flipUp,
    });
  };

  // Текущая опция — для отображения в заголовке
  const selected = useMemo(
    () => options.find((o) => o.value === value),
    [options, value],
  );

  // Поисковая фильтрация — по label + sublabel, case-insensitive
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return options;
    return options.filter((o) => {
      const hay = `${o.label} ${o.sublabel ?? ''}`.toLowerCase();
      return hay.includes(q);
    });
  }, [options, search]);

  // Сбрасываем highlight при изменении фильтра
  useEffect(() => {
    setHighlighted(0);
  }, [search]);

  // Открыли → автофокус в поиск + highlight + рассчитать позицию портала.
  // useLayoutEffect — чтобы измерить и спозиционировать ДО первого пэйнта
  // дропдауна (без useLayoutEffect видно «прыжок» из угла экрана).
  useLayoutEffect(() => {
    if (!open) return;
    recalcPosition();
    setTimeout(() => searchRef.current?.focus(), 0);
    const idx = filtered.findIndex((o) => o.value === value);
    setHighlighted(idx >= 0 ? idx : 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Пока открыт — следим за скроллом/ресайзом контейнера, обновляем позицию.
  // Это нужно потому что портал = position: fixed, а триггер живёт внутри
  // прокручиваемого .modal-body.
  useEffect(() => {
    if (!open) return;
    const onScroll = () => recalcPosition();
    window.addEventListener('scroll', onScroll, true);
    window.addEventListener('resize', onScroll);
    return () => {
      window.removeEventListener('scroll', onScroll, true);
      window.removeEventListener('resize', onScroll);
    };
  }, [open]);

  // Клик вне (триггера И самого дропдауна) → закрыть.
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      const t = e.target as Node;
      if (rootRef.current?.contains(t)) return;
      if (dropdownRef.current?.contains(t)) return;
      setOpen(false);
      setSearch('');
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  // Скролл к выделенной строке клавиатурой
  useEffect(() => {
    if (!open || !listRef.current) return;
    const el = listRef.current.children[highlighted] as HTMLElement | undefined;
    if (el) el.scrollIntoView({ block: 'nearest' });
  }, [highlighted, open]);

  const handleSelect = (v: string) => {
    onChange(v);
    setOpen(false);
    setSearch('');
  };

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlighted((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlighted((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const opt = filtered[highlighted];
      if (opt && !opt.disabled) handleSelect(opt.value);
    } else if (e.key === 'Escape') {
      setOpen(false);
      setSearch('');
    }
  };

  return (
    <div
      ref={rootRef}
      className={className}
      style={{ position: 'relative', ...style }}
    >
      <button
        ref={triggerRef}
        type="button"
        className="input"
        onClick={() => !disabled && setOpen((o) => !o)}
        disabled={disabled}
        style={{
          textAlign: 'left',
          cursor: disabled ? 'not-allowed' : 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
          width: '100%',
        }}
      >
        <span
          style={{
            color: selected ? 'var(--fg-1)' : 'var(--fg-3)',
            flex: 1,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {selected ? selected.label : placeholder}
        </span>
        {!hideClear && value && !disabled && (
          <span
            role="button"
            tabIndex={-1}
            onClick={(e) => {
              e.stopPropagation();
              onChange('');
            }}
            style={{
              display: 'inline-flex',
              padding: 2,
              color: 'var(--fg-3)',
              cursor: 'pointer',
            }}
          >
            <Icon name="close" size={12} />
          </span>
        )}
        <Icon name="chevron-down" size={12} style={{ color: 'var(--fg-3)' }} />
      </button>

      {open && pos && typeof document !== 'undefined' && createPortal(
        <div
          ref={dropdownRef}
          style={{
            position: 'fixed',
            top: pos.flipUp ? undefined : pos.top,
            bottom: pos.flipUp ? window.innerHeight - pos.top : undefined,
            left: pos.left,
            width: pos.width,
            // z-index выше .modal-backdrop (var(--z-modal)) — иначе портал
            // под бэкдропом. 1100 безопасно поверх любой модалки.
            zIndex: 1100,
            background: 'var(--bg-card)',
            border: '1px solid var(--border-strong)',
            borderRadius: 6,
            boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            maxHeight: 320,
          }}
        >
          <input
            ref={searchRef}
            className="input"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={handleKey}
            placeholder={searchPlaceholder}
            style={{
              border: 'none',
              borderBottom: '1px solid var(--border)',
              borderRadius: 0,
              margin: 0,
            }}
          />
          <div
            ref={listRef}
            style={{
              overflowY: 'auto',
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            {filtered.length === 0 ? (
              <div
                style={{
                  padding: 12,
                  fontSize: 12,
                  color: 'var(--fg-3)',
                  textAlign: 'center',
                }}
              >
                {emptyText}
              </div>
            ) : (
              filtered.map((opt, idx) => {
                const isSel = opt.value === value;
                const isHi = idx === highlighted;
                return (
                  <button
                    key={opt.value}
                    type="button"
                    disabled={opt.disabled}
                    onClick={() => !opt.disabled && handleSelect(opt.value)}
                    onMouseEnter={() => setHighlighted(idx)}
                    style={{
                      padding: '6px 10px',
                      textAlign: 'left',
                      background:
                        isHi && !opt.disabled
                          ? 'var(--bg-active)'
                          : isSel
                            ? 'var(--bg-soft)'
                            : 'transparent',
                      color: opt.disabled
                        ? 'var(--fg-3)'
                        : isSel
                          ? 'var(--brand-orange)'
                          : 'var(--fg-1)',
                      border: 'none',
                      borderLeft: isSel
                        ? '3px solid var(--brand-orange)'
                        : '3px solid transparent',
                      cursor: opt.disabled ? 'not-allowed' : 'pointer',
                      fontSize: 12,
                      display: 'flex',
                      alignItems: 'baseline',
                      justifyContent: 'space-between',
                      gap: 8,
                      fontFamily: 'var(--font-sans)',
                      fontWeight: isSel ? 600 : 400,
                    }}
                  >
                    <span
                      style={{
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        flex: 1,
                      }}
                    >
                      {opt.label}
                    </span>
                    {opt.sublabel && (
                      <span
                        style={{
                          fontSize: 11,
                          color: 'var(--fg-3)',
                          flex: 0,
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {opt.sublabel}
                      </span>
                    )}
                  </button>
                );
              })
            )}
          </div>
        </div>,
        document.body,
      )}
    </div>
  );
}
