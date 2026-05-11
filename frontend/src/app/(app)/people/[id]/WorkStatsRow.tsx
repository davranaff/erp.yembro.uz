'use client';

/**
 * Блок счётчиков работы за месяц: должен / отработал / прогулы /
 * больничные / отпуск / явка.
 *
 * Источник данных — endpoint /api/payroll/employees/<id>/calendar/, который
 * уже отдаёт expected[] (по графику) и actual[] (по фактическим сменам).
 * Здесь всё считается на фронте — лишний запрос не нужен, данные уже под
 * рукой в карточке.
 */
import { useMemo, useState } from 'react';

import Icon from '@/components/ui/Icon';
import { useEmployeeCalendar } from '@/hooks/usePayroll';
import type { WorkShiftKind } from '@/types/payroll';

function ymd(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
function startOfMonth(d: Date) { return new Date(d.getFullYear(), d.getMonth(), 1); }
function endOfMonth(d: Date) { return new Date(d.getFullYear(), d.getMonth() + 1, 0); }

const MONTHS = [
  'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
];

// «Рабочая» смена в нашей системе — это `work` или `overtime`.
const IS_WORK = (k: WorkShiftKind) => k === 'work' || k === 'overtime';

type Counter = {
  label: string;
  value: number;
  sub?: string;
  tone: 'primary' | 'green' | 'red' | 'orange' | 'blue' | 'neutral';
  icon?: string;
};

const TONE_BG: Record<Counter['tone'], string> = {
  primary: 'linear-gradient(135deg, #fef3c7 0%, #fde68a 100%)',
  green:   'linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%)',
  red:     'linear-gradient(135deg, #fee2e2 0%, #fecaca 100%)',
  orange:  'linear-gradient(135deg, #fed7aa 0%, #fdba74 100%)',
  blue:    'linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%)',
  neutral: 'linear-gradient(135deg, #f3f4f6 0%, #e5e7eb 100%)',
};
const TONE_FG: Record<Counter['tone'], string> = {
  primary: '#92400e',
  green:   '#065f46',
  red:     '#991b1b',
  orange:  '#9a3412',
  blue:    '#1e40af',
  neutral: '#4b5563',
};

export default function WorkStatsRow({ employeeId }: { employeeId: string }) {
  const today = new Date();
  const [offset, setOffset] = useState(0); // 0 = текущий, -1 = прошлый, +1 = следующий
  const refDate = new Date(today.getFullYear(), today.getMonth() + offset, 1);
  const fromStr = ymd(startOfMonth(refDate));
  const toStr = ymd(endOfMonth(refDate));
  const { data: cal, isLoading } = useEmployeeCalendar(employeeId, fromStr, toStr);

  const counters: Counter[] = useMemo(() => {
    if (!cal) return [];

    // Expected — по графику. Считаем рабочие смены и их часы.
    let expectedShifts = 0;
    let expectedHours = 0;
    for (const e of cal.expected) {
      if (IS_WORK(e.kind as WorkShiftKind)) {
        expectedShifts++;
        expectedHours += Number(e.duration_hours || 0);
      }
    }

    // Actual — по фактическим WorkShift'ам.
    const counts: Record<WorkShiftKind, number> = {
      work: 0, overtime: 0, vacation: 0, sick_leave: 0,
      absence: 0, day_off: 0, holiday: 0,
    };
    let actualHours = 0;
    for (const a of cal.actual) {
      counts[a.kind] = (counts[a.kind] || 0) + 1;
      if (IS_WORK(a.kind) && a.hours) actualHours += Number(a.hours);
    }
    const actualShifts = counts.work + counts.overtime;

    // Процент явки — рабочих смен / ожидавшихся.
    const attendance = expectedShifts > 0
      ? Math.round((actualShifts / expectedShifts) * 100)
      : actualShifts > 0 ? 100 : 0;

    // Часы — если нет данных по часам в смене, используем expected*8 как fallback
    const hoursLabel = actualHours > 0
      ? `${actualHours.toFixed(1)} ч`
      : actualShifts > 0 ? `≈${(actualShifts * 8).toFixed(0)} ч` : '—';

    return [
      {
        label: 'Должен был',
        value: expectedShifts,
        sub: expectedHours > 0 ? `${expectedHours.toFixed(0)} ч по графику` : 'нет графика',
        tone: 'blue',
        icon: 'calendar',
      },
      {
        label: 'Отработал',
        value: actualShifts,
        sub: hoursLabel,
        tone: 'green',
        icon: 'check',
      },
      {
        label: 'Явка',
        value: attendance,
        sub: expectedShifts > 0 ? `${actualShifts} из ${expectedShifts}` : 'график не задан',
        tone: attendance >= 90 ? 'green' : attendance >= 70 ? 'primary' : 'red',
        icon: 'chart',
      },
      {
        label: 'Прогулы',
        value: counts.absence,
        sub: counts.absence > 0 ? 'дней' : 'отлично',
        tone: counts.absence > 0 ? 'red' : 'neutral',
        icon: 'close',
      },
      {
        label: 'Больничный',
        value: counts.sick_leave,
        sub: counts.sick_leave > 0 ? 'дней' : '—',
        tone: 'orange',
        icon: 'pharma',
      },
      {
        label: 'Отпуск',
        value: counts.vacation,
        sub: counts.vacation > 0 ? 'дней' : '—',
        tone: 'blue',
        icon: 'sun',
      },
    ];
  }, [cal]);

  const monthLabel = `${MONTHS[refDate.getMonth()]} ${refDate.getFullYear()}`;
  const isCurrent = offset === 0;

  return (
    <div className="work-stats" style={{ marginTop: 12 }}>
      <div
        className="work-stats__head"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
          marginBottom: 10,
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: '0.08em',
              color: 'var(--fg-3)',
              textTransform: 'uppercase',
            }}
          >
            Учёт рабочего времени
          </span>
          <span style={{ fontSize: 13, color: 'var(--fg-2)' }}>· {monthLabel}</span>
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setOffset((o) => o - 1)}
            aria-label="Предыдущий месяц"
          >
            ←
          </button>
          {!isCurrent && (
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => setOffset(0)}
            >
              Текущий
            </button>
          )}
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setOffset((o) => o + 1)}
            disabled={offset >= 0}
            aria-label="Следующий месяц"
          >
            →
          </button>
        </div>
      </div>

      <div
        className="work-stats__grid"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(6, minmax(0, 1fr))',
          gap: 8,
        }}
      >
        {isLoading && !cal ? (
          Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              style={{
                height: 86,
                borderRadius: 8,
                background: 'var(--bg-subtle)',
                opacity: 0.5,
              }}
            />
          ))
        ) : (
          counters.map((c, i) => (
            <div
              key={i}
              style={{
                padding: '12px 14px',
                borderRadius: 8,
                background: TONE_BG[c.tone],
                color: TONE_FG[c.tone],
                display: 'flex',
                flexDirection: 'column',
                gap: 4,
                minHeight: 86,
                position: 'relative',
              }}
            >
              {c.icon && (
                <div style={{ position: 'absolute', top: 10, right: 10, opacity: 0.5 }}>
                  <Icon name={c.icon} size={14} />
                </div>
              )}
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                  opacity: 0.85,
                }}
              >
                {c.label}
              </div>
              <div
                style={{
                  fontSize: 24,
                  fontWeight: 700,
                  fontFamily: 'var(--mono, monospace)',
                  lineHeight: 1.1,
                }}
              >
                {c.value}
                {c.label === 'Явка' && <span style={{ fontSize: 14, marginLeft: 2 }}>%</span>}
              </div>
              {c.sub && (
                <div style={{ fontSize: 11, opacity: 0.75 }}>{c.sub}</div>
              )}
            </div>
          ))
        )}
      </div>

      <style jsx>{`
        @media (max-width: 1024px) {
          .work-stats__grid {
            grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
          }
        }
        @media (max-width: 560px) {
          .work-stats__grid {
            grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
            gap: 6px !important;
          }
        }
      `}</style>
    </div>
  );
}
