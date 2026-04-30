'use client';

import { useState } from 'react';

import DetailDrawer, { KV } from '@/components/DetailDrawer';
import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import EmptyState from '@/components/ui/EmptyState';
import Sparkline from '@/components/ui/Sparkline';
import {
  useApplyShrinkage,
  useResetShrinkage,
  useShrinkageHistory,
} from '@/hooks/useFeed';
import { useHasLevel } from '@/hooks/usePermissions';
import { ApiError } from '@/lib/api';
import type {
  FeedLotShrinkageState,
  ShrinkageHistoryPoint,
} from '@/types/auth';


interface Props {
  state: FeedLotShrinkageState;
  onClose: () => void;
}

function fmtKg(v: string | null | undefined, digits = 3): string {
  if (!v) return '—';
  const n = parseFloat(v);
  if (Number.isNaN(n)) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: digits });
}

function fmtMoney(v: string | null | undefined): string {
  if (!v) return '—';
  const n = parseFloat(v);
  if (Number.isNaN(n)) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 }) + ' сум';
}

/**
 * Drawer с детальной историей усушки конкретной партии.
 *
 * Показывает: KV-блок состояния, sparkline остатка, полную таблицу
 * движений (дата, списано, накопит., остаток, стоимость) и админские
 * actions «Пересчитать» / «Откатить».
 */
export default function StateDetailDrawer({ state, onClose }: Props) {
  const hasLevel = useHasLevel();
  const canEdit = hasLevel('feed', 'rw');
  const canAdmin = hasLevel('feed', 'admin');

  const { data: history, isLoading } = useShrinkageHistory(state.id);
  const apply = useApplyShrinkage();
  const reset = useResetShrinkage();

  const [error, setError] = useState<string | null>(null);

  const initial = parseFloat(state.initial_quantity);
  const lost = parseFloat(state.accumulated_loss);
  const remaining = Math.max(0, initial - lost);
  const lostPct = state.accumulated_percent ? parseFloat(state.accumulated_percent) : 0;

  const handleApply = async () => {
    setError(null);
    try {
      await apply.mutateAsync({
        lot_type: state.lot_type,
        lot_id: state.lot_id,
      });
    } catch (e) {
      setError((e as ApiError).message || 'Не удалось пересчитать');
    }
  };

  const handleReset = async () => {
    if (!confirm(
      'Откатить все списания усушки по этой партии?\n\n' +
      'Удалятся все StockMovement(kind=shrinkage) этой партии, ' +
      'остаток восстановится, state сбросится. Операция необратима.',
    )) return;
    setError(null);
    try {
      await reset.mutateAsync({ id: state.id });
      onClose();
    } catch (e) {
      setError((e as ApiError).message || 'Не удалось откатить');
    }
  };

  return (
    <DetailDrawer
      title="Состояние усушки партии"
      subtitle={state.profile_label}
      onClose={onClose}
      actions={
        <>
          {canEdit && !state.is_frozen && (
            <button
              className="btn btn-sm"
              onClick={handleApply}
              disabled={apply.isPending}
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
            >
              {reset.isPending ? 'Откат…' : 'Откатить'}
            </button>
          )}
        </>
      }
    >
      {/* State summary */}
      <KV
        items={[
          {
            k: 'Тип партии',
            v: (
              <Badge tone={state.lot_type === 'raw_arrival' ? 'info' : 'warn'}>
                {state.lot_type === 'raw_arrival' ? 'сырьё' : 'готовый корм'}
              </Badge>
            ),
          },
          { k: 'ID партии', v: state.lot_id, mono: true },
          { k: 'Начальная масса', v: fmtKg(state.initial_quantity) + ' кг', mono: true },
          { k: 'Списано', v: `${fmtKg(state.accumulated_loss)} кг (${state.accumulated_percent ?? '0'}%)`, mono: true },
          { k: 'Остаток', v: fmtKg(String(remaining)) + ' кг', mono: true },
          { k: 'Последний цикл', v: state.last_applied_on ?? 'не было', mono: true },
          {
            k: 'Статус',
            v: state.is_frozen
              ? <Badge tone="neutral">заморожена</Badge>
              : <Badge tone="success">активна</Badge>,
          },
        ]}
      />

      {/* Progress bar */}
      <div style={{
        height: 10, background: 'var(--bg-soft)', borderRadius: 5,
        overflow: 'hidden', marginBottom: 16,
      }}>
        <div style={{
          height: '100%',
          width: `${Math.min(100, lostPct)}%`,
          background: state.is_frozen ? 'var(--fg-3)' : 'var(--brand-orange)',
          transition: 'width .3s ease',
        }} />
      </div>

      {/* History */}
      <div style={{
        fontSize: 11, color: 'var(--fg-3)',
        letterSpacing: '.04em', textTransform: 'uppercase',
        fontWeight: 700, marginBottom: 10,
        display: 'flex', justifyContent: 'space-between',
      }}>
        <span>История списаний</span>
        <span>{history?.points.length ?? 0}</span>
      </div>

      {isLoading ? (
        <div style={{ padding: 16, color: 'var(--fg-3)', fontSize: 12 }}>Загрузка…</div>
      ) : !history || history.points.length === 0 ? (
        <EmptyState
          title="Нет списаний"
          description="История появится после первого прогона алгоритма усушки."
        />
      ) : (
        <>
          {/* Sparkline */}
          {history.points.length >= 2 && (
            <div style={{ marginBottom: 16 }}>
              <Sparkline
                values={history.points.map((p) => parseFloat(p.remaining_kg))}
                width={420}
                height={64}
                label={`Динамика остатка: ${history.points.length} списаний`}
              />
              <div style={{
                fontSize: 11, color: 'var(--fg-3)',
                display: 'flex', justifyContent: 'space-between', marginTop: 4,
              }}>
                <span>{history.points[0]?.date}</span>
                <span style={{ color: 'var(--fg-2)' }}>
                  Остаток: {fmtKg(history.points[history.points.length - 1]?.remaining_kg)} кг
                </span>
                <span>{history.points[history.points.length - 1]?.date}</span>
              </div>
            </div>
          )}

          {/* Полная таблица движений */}
          <DataTable<ShrinkageHistoryPoint>
            rows={history.points}
            rowKey={(p) => p.movement_id}
            columns={[
              { key: 'date', label: 'Дата', mono: true, render: (p) => p.date ?? '—' },
              {
                key: 'lost_kg', label: 'Списано', mono: true, align: 'right',
                render: (p) => fmtKg(p.lost_kg) + ' кг',
              },
              {
                key: 'cumulative', label: 'Накопит.', mono: true, align: 'right',
                render: (p) => fmtKg(p.cumulative_loss_kg) + ' кг',
              },
              {
                key: 'remaining', label: 'Остаток', mono: true, align: 'right',
                render: (p) => fmtKg(p.remaining_kg) + ' кг',
              },
              {
                key: 'cost', label: 'Стоимость', mono: true, align: 'right', muted: true,
                render: (p) => fmtMoney(p.lost_uzs),
              },
            ]}
          />
        </>
      )}

      {error && (
        <div style={{ marginTop: 12, fontSize: 12, color: 'var(--danger)' }}>{error}</div>
      )}
    </DetailDrawer>
  );
}
