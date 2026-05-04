'use client';

import { useMemo, useState } from 'react';

import ConfirmDeleteWithReason from '@/components/ConfirmDeleteWithReason';
import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import EmptyState from '@/components/ui/EmptyState';
import HelpHint from '@/components/ui/HelpHint';
import Icon from '@/components/ui/Icon';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import { feedConsumptionCrud } from '@/hooks/useFeedlot';
import type { FeedConsumptionType, FeedlotBatch, FeedlotFeedConsumption } from '@/types/auth';

import FeedConsumptionModal from './FeedConsumptionModal';

interface Props {
  batch: FeedlotBatch;
}

const TYPE_LABEL: Record<FeedConsumptionType, string> = {
  start: 'Старт',
  growth: 'Рост',
  finish: 'Финиш',
};

const TYPE_TONE: Record<FeedConsumptionType, 'info' | 'warn' | 'success'> = {
  start: 'info',
  growth: 'warn',
  finish: 'success',
};

function fmtNum(v: string | null | undefined, digits = 0): string {
  if (!v) return '—';
  const n = parseFloat(v);
  if (Number.isNaN(n)) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: digits });
}

export default function FeedConsumptionPanel({ batch }: Props) {
  const { data: rows, isLoading } = feedConsumptionCrud.useList({
    feedlot_batch: batch.id,
    ordering: '-period_from_day',
  });
  const [open, setOpen] = useState(false);
  const del = feedConsumptionCrud.useDelete();
  const [confirmDel, setConfirmDel] = useState<FeedlotFeedConsumption | null>(null);

  const totalKg = useMemo(() => {
    if (!rows) return 0;
    return rows.reduce((s, r) => s + parseFloat(r.total_kg || '0'), 0);
  }, [rows]);

  const canAdd = batch.status !== 'shipped';

  return (
    <>
      <Panel
        title={
          <span style={{ display: 'inline-flex', alignItems: 'center' }}>
            Кормление
            <HelpHint
              text="Списанный корм по периодам откорма."
              details={
                'Каждая запись = один документ списания со склада. '
                + 'Создаёт проводку Дт 20.02 / Кт 10.05. '
                + 'period_fcr считается автоматически если на границах периода '
                + 'есть взвешивания (нужны для расчёта прироста массы).'
              }
            />
          </span> as unknown as string
        }
        tools={
          canAdd ? (
            <button
              className="btn btn-primary btn-sm"
              onClick={() => setOpen(true)}
            >
              <Icon name="plus" size={12} /> Кормление
            </button>
          ) : null
        }
        flush
      >
        {(!rows || rows.length === 0) ? (
          <EmptyState
            icon="bag"
            title="Кормлений ещё нет"
            description="Запишите кормление чтобы списать корм со склада в проводки 20.02 (Откорм) ← 10.05 (Готовый корм). Это нужно для расчёта FCR и реальной себестоимости птицы."
            action={canAdd ? {
              label: 'Записать кормление',
              onClick: () => setOpen(true),
            } : undefined}
            hint="Стандартные стадии: Старт 0–14 дн, Рост 15–28 дн, Финиш 29+ дн."
          />
        ) : (
          <>
            <div style={{
              padding: '6px 12px', fontSize: 11,
              color: 'var(--fg-3)', borderBottom: '1px solid var(--border)',
              display: 'flex', justifyContent: 'space-between',
            }}>
              <span>Записей: {rows.length}</span>
              <span>
                Σ скормлено: <b className="mono">{fmtNum(String(totalKg), 0)} кг</b>
              </span>
            </div>
            <DataTable<FeedlotFeedConsumption>
              isLoading={isLoading}
              rows={rows}
              rowKey={(r) => r.id}
              emptyMessage="—"
              columns={[
                { key: 'period', label: 'Период', mono: true,
                  render: (r) => `${r.period_from_day}–${r.period_to_day} дн` },
                { key: 'type', label: 'Тип',
                  render: (r) => (
                    <Badge tone={TYPE_TONE[r.feed_type]} dot>
                      {TYPE_LABEL[r.feed_type]}
                    </Badge>
                  ) },
                { key: 'feed_doc', label: 'Партия корма', mono: true, cellStyle: { fontSize: 12 },
                  render: (r) => r.feed_batch_doc ?? '—' },
                { key: 'total_kg', label: 'Скормлено, кг', align: 'right', mono: true,
                  cellStyle: { fontWeight: 600 },
                  render: (r) => fmtNum(r.total_kg, 0) },
                { key: 'per_head', label: 'На гол, г', align: 'right', mono: true,
                  cellStyle: { fontSize: 12 },
                  render: (r) => fmtNum(r.per_head_g, 1) },
                { key: 'fcr', label: 'FCR', align: 'right', mono: true,
                  cellStyle: { fontWeight: 600, color: 'var(--brand-orange)' },
                  render: (r) => r.period_fcr
                    ? parseFloat(r.period_fcr).toFixed(2)
                    : '—' },
                { key: 'notes', label: 'Заметка',
                  cellStyle: { fontSize: 11, color: 'var(--fg-3)' },
                  render: (r) => r.notes || '—' },
                { key: 'actions', label: '', width: 60, align: 'right',
                  render: (r) => (
                    <RowActions
                      actions={[
                        {
                          label: 'Удалить',
                          danger: true,
                          hidden: !canAdd,
                          disabled: del.isPending,
                          onClick: () => setConfirmDel(r),
                        },
                      ]}
                    />
                  ) },
              ]}
            />
          </>
        )}
      </Panel>

      {open && <FeedConsumptionModal batch={batch} onClose={() => setOpen(false)} />}
      {confirmDel && (
        <ConfirmDeleteWithReason
          title="Удалить запись кормления?"
          subject={`дни ${confirmDel.period_from_day}-${confirmDel.period_to_day} · ${parseFloat(confirmDel.total_kg).toLocaleString('ru-RU')} кг`}
          isPending={del.isPending}
          onConfirm={async (reason) => {
            await del.mutateAsync({ id: confirmDel.id, reason });
            setConfirmDel(null);
          }}
          onClose={() => setConfirmDel(null)}
        />
      )}
    </>
  );
}
