'use client';

import { useEffect, useRef, useState } from 'react';
import { usePathname } from 'next/navigation';

import Icon from '@/components/ui/Icon';

import { labelForHref } from './nav';

interface Props {
  /** Колбек открытия palette — пробрасывается из Topbar. */
  onOpenPalette?: () => void;
}

const SECTION_HELP: Record<string, string> = {
  '/dashboard':
    'Сводка по компании за период: финансовые KPI, движения денег, состояние производства и список того, что ждёт действия.',
  '/traceability':
    'Сквозной путь партии: откуда взялась, куда ушла, какая накопленная себестоимость и какие операции на неё легли.',
  '/purchases':
    'Закупки у поставщиков: создание, проведение (приход на склад + Дт 10.X / Кт 60.X), сторнирование. После проведения документ иммутабелен.',
  '/sales':
    'Продажи клиентам: резерв партий в DRAFT, проведение (списание + выручка), приём оплат, сторно.',
  '/finance/cashbox':
    'Касса и банк: проведённые платежи, остатки по каналам, прочие расходы/доходы (OPEX) с моментальной проводкой в ГК.',
  '/ledger':
    'Журнал бухгалтерских проводок (двойная запись). Drill-down к ОСВ и Главной книге по субсчёту.',
  '/reports':
    'Бухгалтерские отчёты: ОСВ, Главная книга по субсчёту, P&L. Поддерживают CSV-экспорт.',
  '/stock':
    'Сквозной журнал движений по складам и сами склады с CRUD. KPI по приходам/расходам/списанию.',
  '/audit-log':
    'Журнал аудита: все действия пользователей с фильтрами по дате/действию/сущности и CSV-экспортом.',
  '/roles':
    'Роли с матрицей доступов и индивидуальные исключения. Каждое изменение прав попадает в журнал аудита.',
  '/holding':
    'Сводный вид по всем компаниям, к которым у вас есть доступ. Изоляция данных компаний — железная.',
  '/finance/rates':
    'Архив курсов ЦБ Узбекистана. При проведении валютной операции курс снапшотится в документ.',
};

const HOTKEYS: { keys: string[]; label: string }[] = [
  { keys: ['⌘', 'K'], label: 'Открыть поиск страниц' },
  { keys: ['Ctrl', 'K'], label: 'То же на Windows / Linux' },
  { keys: ['Esc'], label: 'Закрыть модалку / меню' },
];

/**
 * Last-N изменений в системе. Видны всем пользователям. Обновляется
 * вручную при каждом релизе. Самое свежее — сверху.
 */
const CHANGELOG: { date: string; title: string }[] = [
  { date: '2026-04-26', title: 'План счетов: KPI, фильтры по типу/модулю, drill-down в ГК, CSV-экспорт' },
  { date: '2026-04-25', title: 'Профиль: hero-шапка с аватаром и KPI пользователя' },
  { date: '2026-04-25', title: 'Адаптивный дизайн: модалки/дроверы fullscreen на мобиле, безопасная зона iOS' },
  { date: '2026-04-24', title: '7 ролей с продуманной матрицей прав: маточник, инкубация, откорм, убойня, корма, бухгалтерия' },
  { date: '2026-04-24', title: 'Ребрендинг «Курочка» → YemBro' },
  { date: '2026-04-24', title: 'Журнал аудита: фильтры по дате/пользователю + CSV-экспорт' },
  { date: '2026-04-23', title: 'Избранные страницы синхронизируются с бэкендом, видны в сайдбаре' },
];

export default function HelpMenu({ onOpenPalette }: Props) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  // Контекстная справка по текущей странице (простой prefix-match)
  const sectionHelp = (() => {
    const exact = SECTION_HELP[pathname];
    if (exact) return { label: labelForHref(pathname) ?? pathname, text: exact };
    const prefix = Object.keys(SECTION_HELP)
      .filter((k) => pathname.startsWith(k))
      .sort((a, b) => b.length - a.length)[0];
    if (prefix) {
      return { label: labelForHref(prefix) ?? prefix, text: SECTION_HELP[prefix] };
    }
    return null;
  })();

  return (
    <div ref={wrapRef} style={{ position: 'relative' }}>
      <button
        className="topbar-btn"
        onClick={() => setOpen((v) => !v)}
        title="Справка"
        type="button"
      >
        <Icon name="help" size={16} />
      </button>

      {open && (
        <div className="help-menu" role="menu">
          {sectionHelp && (
            <div className="help-section">
              <div className="help-section-hdr">
                <Icon name="book" size={12} /> {sectionHelp.label}
              </div>
              <div className="help-section-text">{sectionHelp.text}</div>
            </div>
          )}

          <div className="help-section">
            <div className="help-section-hdr">
              <Icon name="search" size={12} /> Горячие клавиши
            </div>
            <div className="help-hotkeys">
              {HOTKEYS.map((h) => (
                <div key={h.label} className="help-hotkey">
                  <span>{h.label}</span>
                  <span>
                    {h.keys.map((k, i) => (
                      <kbd key={i}>{k}</kbd>
                    ))}
                  </span>
                </div>
              ))}
            </div>
            {onOpenPalette && (
              <button
                className="btn btn-secondary btn-sm"
                style={{ marginTop: 8, width: '100%' }}
                onClick={() => {
                  setOpen(false);
                  onOpenPalette();
                }}
                type="button"
              >
                <Icon name="search" size={12} /> Открыть поиск
              </button>
            )}
          </div>

          <div className="help-section">
            <div className="help-section-hdr">
              <Icon name="star" size={12} /> Что нового
            </div>
            <div className="help-changelog">
              {CHANGELOG.slice(0, 5).map((item, i) => (
                <div key={i} className="help-changelog-item">
                  <div className="help-changelog-date">{item.date}</div>
                  <div className="help-changelog-title">{item.title}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="help-section">
            <div className="help-section-hdr">
              <Icon name="users" size={12} /> Поддержка
            </div>
            <div className="help-section-text">
              Если что-то сломалось или нужна функция — напишите{' '}
              <a
                href="mailto:support@yembro.uz"
                style={{ color: 'var(--brand-orange)' }}
              >
                support@yembro.uz
              </a>
              .
            </div>
          </div>

          <div className="help-foot">
            <span className="mono">YemBro ERP</span>
            <span className="mono" style={{ color: 'var(--fg-3)' }}>
              build {process.env.NEXT_PUBLIC_BUILD_VERSION ?? 'dev'}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
