'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';

import Sparkline from '@/components/ui/Sparkline';
import {
  shrinkageProfilesCrud,
  shrinkageStatesCrud,
  useApplyShrinkage,
  useResetShrinkage,
  useShrinkageHistory,
} from '@/hooks/useFeed';
import { useHasLevel } from '@/hooks/usePermissions';
import { ApiError } from '@/lib/api';
import type {
  FeedLotShrinkageState,
  FeedShrinkageProfile,
  ShrinkageLotType,
} from '@/types/auth';


interface Props {
  lotType: ShrinkageLotType;
  lotId: string;
  /** Начальная масса партии (для прогресс-бара когда state ещё не создан). */
  initialKg: string | null;
  unitLabel?: string;
}

function fmtKg(v: string | null | undefined, digits = 3): string {
  if (!v) return '—';
  const n = parseFloat(v);
  if (Number.isNaN(n)) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: digits });
}

/**
 * Compound-прогноз: сколько будет потеряно за `daysAhead` дней начиная от
 * текущего момента, с учётом уже накопленных потерь и max-лимита. Зеркало
 * `_compute_loss` из backend services/shrinkage_runner.py.
 */
function forecastLoss({
  currentRemaining,
  initial,
  accumulatedLoss,
  pctPerPeriod,
  periodDays,
  maxTotalPct,
  daysAhead,
}: {
  currentRemaining: number;
  initial: number;
  accumulatedLoss: number;
  pctPerPeriod: number;
  periodDays: number;
  maxTotalPct: number | null;
  daysAhead: number;
}): { extraLoss: number; remaining: number; willFreeze: boolean } {
  if (currentRemaining <= 0 || pctPerPeriod <= 0 || periodDays <= 0 || daysAhead <= 0) {
    return { extraLoss: 0, remaining: currentRemaining, willFreeze: false };
  }
  const periods = Math.floor(daysAhead / periodDays);
  if (periods <= 0) {
    return { extraLoss: 0, remaining: currentRemaining, willFreeze: false };
  }
  const factor = pctPerPeriod / 100;
  let remaining = currentRemaining;
  let extra = 0;
  let willFreeze = false;
  let maxExtra: number | null = null;
  if (maxTotalPct != null) {
    const maxTotal = (initial * maxTotalPct) / 100;
    maxExtra = Math.max(0, maxTotal - accumulatedLoss);
  }
  for (let i = 0; i < periods; i++) {
    if (remaining <= 0) break;
    let delta = remaining * factor;
    if (maxExtra != null && extra + delta >= maxExtra) {
      delta = Math.max(0, maxExtra - extra);
      extra += delta;
      remaining -= delta;
      willFreeze = true;
      break;
    }
    extra += delta;
    remaining -= delta;
  }
  return { extraLoss: extra, remaining, willFreeze };
}

/**
 * Виджет «Усушка» для drawer'а партии (сырьё или готовый корм).
 *
 * Показывает: профиль, прогресс-бар «накопленная усушка», даты, статус.
 * Кнопка «Пересчитать» (canEdit=feed.rw) триггерит точечный прогон по партии.
 * Кнопка «Откатить» (admin) удаляет все StockMovement(shrinkage) этой партии.
 *
 * Если state не создан — рендерит «партия попадёт в следующий цикл, если
 * для неё есть активный профиль».
 */
export default function ShrinkageWidget({ lotType, lotId, initialKg, unitLabel = 'кг' }: Props) {
  const hasLevel = useHasLevel();
  const canEdit = hasLevel('feed', 'rw');
  const canAdmin = hasLevel('feed', 'admin');

  // backend filter: lot_type+lot_id уникальны → max одна запись
  const { data: states, isLoading } = shrinkageStatesCrud.useList({
    lot_type: lotType,
    lot_id: lotId,
  });
  const state: FeedLotShrinkageState | undefined = states?.[0];

  const { data: history } = useShrinkageHistory(state?.id);

  // Профиль нужен для прогноза. Берём всё, фильтруем на фронте чтобы не плодить
  // запросы при каждом открытии drawer'а — список профилей кэшируется в QueryClient.
  const { data: allProfiles } = shrinkageProfilesCrud.useList();
  const profile: FeedShrinkageProfile | undefined = useMemo(() => {
    if (!state) return undefined;
    return (allProfiles ?? []).find((p) => p.id === state.profile);
  }, [allProfiles, state]);

  const apply = useApplyShrinkage();
  const reset = useResetShrinkage();
  const [error, setError] = useState<string | null>(null);

  const handleApply = async () => {
    setError(null);
    try {
      await apply.mutateAsync({ lot_type: lotType, lot_id: lotId });
    } catch (e) {
      setError((e as ApiError).message || 'Не удалось пересчитать');
    }
  };

  const handleReset = async () => {
    if (!state) return;
    if (!confirm(
      'Откатить все списания усушки по этой партии?\n\n' +
      'Будут удалены все StockMovement(kind=shrinkage), ' +
      'остаток партии восстановлен, state сброшен.\n\n' +
      'Эта операция необратима.',
    )) return;
    setError(null);
    try {
      await reset.mutateAsync({ id: state.id });
    } catch (e) {
      setError((e as ApiError).message || 'Не удалось откатить');
    }
  };

  const sectionStyle: React.CSSProperties = {
    marginTop: 16,
    padding: 14,
    borderRadius: 8,
    border: '1px solid var(--border)',
    background: 'var(--bg-card, #fff)',
  };
  const titleStyle: React.CSSProperties = {
    fontSize: 11, color: 'var(--fg-3)',
    letterSpacing: '.04em', textTransform: 'uppercase',
    fontWeight: 700, marginBottom: 10,
  };

  if (isLoading) {
    return (
      <div style={sectionStyle}>
        <div style={titleStyle}>Усушка</div>
        <div style={{ color: 'var(--fg-3)', fontSize: 12 }}>Загрузка…</div>
      </div>
    );
  }

  // ── Состояние ещё не создано ─────────────────────────────────────────
  if (!state) {
    return (
      <div style={sectionStyle}>
        <div style={titleStyle}>Усушка</div>
        <div style={{ fontSize: 12, lineHeight: 1.5, color: 'var(--fg-2)' }}>
          Усушка ещё не начислялась. Если для этой партии есть активный{' '}
          <Link href="/feed/shrinkage-profiles" style={{ color: 'var(--brand-orange)' }}>
            профиль
          </Link>
          {' '}— она автоматически попадёт в ночной цикл (02:00 Ташкент).
        </div>
        {canEdit && (
          <div style={{ marginTop: 10 }}>
            <button
              className="btn btn-sm"
              onClick={handleApply}
              disabled={apply.isPending}
            >
              {apply.isPending ? 'Прогон…' : 'Прогнать сейчас'}
            </button>
          </div>
        )}
        {error && (
          <div style={{ marginTop: 8, fontSize: 12, color: 'var(--danger)' }}>{error}</div>
        )}
      </div>
    );
  }

  // ── State есть ───────────────────────────────────────────────────────
  const initial = parseFloat(state.initial_quantity);
  const lost = parseFloat(state.accumulated_loss);
  const remaining = Math.max(0, initial - lost);
  const lostPctNum = state.accumulated_percent ? parseFloat(state.accumulated_percent) : 0;
  const barColor = state.is_frozen ? 'var(--fg-3)' : 'var(--brand-orange)';
  const barWidth = Math.min(100, lostPctNum);

  return (
    <div style={sectionStyle}>
      <div style={{ ...titleStyle, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span>Усушка</span>
        {state.is_frozen && (
          <span style={{
            fontSize: 10, fontWeight: 700, color: 'var(--fg-3)',
            padding: '2px 8px', background: 'var(--bg-soft)', borderRadius: 10,
            letterSpacing: '.05em',
          }}>
            Заморожена
          </span>
        )}
      </div>

      {/* Профиль */}
      <div style={{
        fontSize: 12, color: 'var(--fg-2)', marginBottom: 10,
        display: 'flex', justifyContent: 'space-between', gap: 12,
      }}>
        <span>{state.profile_label}</span>
        <Link
          href="/feed/shrinkage-profiles"
          style={{ color: 'var(--brand-orange)', textDecoration: 'none', whiteSpace: 'nowrap' }}
        >
          Профиль →
        </Link>
      </div>

      {profile?.note && profile.note.toLowerCase().includes('автоматически') && (
        <div style={{
          fontSize: 11, color: 'var(--fg-3)', marginBottom: 10, lineHeight: 1.5,
          padding: '6px 10px', background: 'var(--bg-soft)', borderRadius: 4,
        }}>
          ℹ Профиль создан автоматически с дефолтными значениями.
          Если у вашего склада усушка отличается — подкорректируйте в{' '}
          <Link href="/feed/shrinkage-profiles" style={{ color: 'var(--brand-orange)' }}>
            настройках
          </Link>.
        </div>
      )}

      {/* Progress bar */}
      <div style={{
        height: 8, background: 'var(--bg-soft)',
        borderRadius: 4, overflow: 'hidden', marginBottom: 8,
      }}>
        <div style={{
          height: '100%', width: `${barWidth}%`,
          background: barColor,
          transition: 'width .3s ease',
        }} />
      </div>

      {/* Stats */}
      <div style={{ fontSize: 12, color: 'var(--fg-2)', lineHeight: 1.6 }}>
        Списано: <strong style={{ color: 'var(--fg-1)', fontFamily: 'var(--font-jetbrains, monospace)' }}>
          {fmtKg(state.accumulated_loss)} {unitLabel}
        </strong>
        {' '}({state.accumulated_percent ?? '0.00'}%)<br />
        Остаток: <strong style={{ color: 'var(--fg-1)', fontFamily: 'var(--font-jetbrains, monospace)' }}>
          {remaining.toLocaleString('ru-RU', { maximumFractionDigits: 3 })} {unitLabel}
        </strong>
        {' '}из {fmtKg(state.initial_quantity)} {unitLabel}<br />
        Последний цикл: {state.last_applied_on ?? <span style={{ color: 'var(--fg-3)' }}>не было</span>}
      </div>

      {/* Sparkline истории */}
      {history && history.points.length >= 2 && (
        <div style={{ marginTop: 12 }}>
          <div style={{
            fontSize: 11, color: 'var(--fg-3)',
            letterSpacing: '.04em', textTransform: 'uppercase',
            fontWeight: 700, marginBottom: 4,
          }}>
            Остаток по циклам
          </div>
          <Sparkline
            values={history.points.map((p) => parseFloat(p.remaining_kg))}
            width={260}
            height={48}
            label={`Динамика остатка партии: ${history.points.length} списаний`}
          />
          <div style={{
            fontSize: 11, color: 'var(--fg-3)',
            display: 'flex', justifyContent: 'space-between', marginTop: 2,
          }}>
            <span>{history.points[0]?.date}</span>
            <span>{history.points[history.points.length - 1]?.date}</span>
          </div>
        </div>
      )}

      {/* Прогноз 30/60/90 дней */}
      {profile && !state.is_frozen && remaining > 0 && (
        <div style={{
          marginTop: 12, padding: 10,
          background: 'var(--bg-soft)', borderRadius: 6,
          fontSize: 12, color: 'var(--fg-2)',
        }}>
          <div style={{
            fontSize: 11, color: 'var(--fg-3)',
            letterSpacing: '.04em', textTransform: 'uppercase',
            fontWeight: 700, marginBottom: 6,
          }}>
            Прогноз
          </div>
          <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
            <tbody>
              {[30, 60, 90].map((days) => {
                const f = forecastLoss({
                  currentRemaining: remaining,
                  initial,
                  accumulatedLoss: lost,
                  pctPerPeriod: parseFloat(profile.percent_per_period),
                  periodDays: profile.period_days,
                  maxTotalPct: profile.max_total_percent
                    ? parseFloat(profile.max_total_percent)
                    : null,
                  daysAhead: days,
                });
                return (
                  <tr key={days}>
                    <td style={{ padding: '2px 0', color: 'var(--fg-3)' }}>через {days} д</td>
                    <td style={{ padding: '2px 0', textAlign: 'right', fontFamily: 'var(--font-jetbrains, monospace)' }}>
                      ≈ {f.remaining.toLocaleString('ru-RU', { maximumFractionDigits: 1 })} {unitLabel}
                    </td>
                    <td style={{ padding: '2px 0 2px 8px', textAlign: 'right', color: 'var(--fg-3)' }}>
                      −{f.extraLoss.toLocaleString('ru-RU', { maximumFractionDigits: 1 })}
                      {f.willFreeze && ' 🛑'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Actions */}
      {(canEdit || canAdmin) && (
        <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {canEdit && !state.is_frozen && (
            <button
              className="btn btn-sm"
              onClick={handleApply}
              disabled={apply.isPending}
              title="Точечный прогон алгоритма для этой партии"
            >
              {apply.isPending ? 'Прогон…' : 'Пересчитать'}
            </button>
          )}
          {canAdmin && (
            <button
              className="btn btn-sm btn-ghost"
              style={{ color: 'var(--danger)' }}
              onClick={handleReset}
              disabled={reset.isPending}
              title="Откатить все списания усушки по этой партии"
            >
              {reset.isPending ? 'Откат…' : 'Откатить'}
            </button>
          )}
        </div>
      )}

      {error && (
        <div style={{ marginTop: 8, fontSize: 12, color: 'var(--danger)' }}>{error}</div>
      )}

      {initialKg && Math.abs(parseFloat(initialKg) - initial) > 0.001 && (
        <div style={{ marginTop: 8, fontSize: 11, color: 'var(--fg-3)' }}>
          ⚠ Начальный объём в state ({fmtKg(state.initial_quantity)} {unitLabel}) отличается
          от партии ({fmtKg(initialKg)} {unitLabel}) — возможно, профиль был привязан после частичного расхода.
        </div>
      )}
    </div>
  );
}
