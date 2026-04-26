'use client';

import { useState } from 'react';

import ConfirmDeleteWithReason from '@/components/ConfirmDeleteWithReason';
import EmptyState from '@/components/ui/EmptyState';
import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import { weighingsCrud } from '@/hooks/useFeedlot';
import type { DailyWeighing, FeedlotBatch } from '@/types/auth';

import WeighingModal from './WeighingModal';

interface Props {
  batch: FeedlotBatch;
}

export default function WeighingsPanel({ batch }: Props) {
  const { data: weighings, isLoading } = weighingsCrud.useList({
    feedlot_batch: batch.id,
    ordering: '-day_of_age',
  });
  const del = weighingsCrud.useDelete();
  const [open, setOpen] = useState(false);
  const [confirmDel, setConfirmDel] = useState<DailyWeighing | null>(null);

  const canAdd = batch.status !== 'shipped';

  return (
    <>
      <Panel
        title="Взвешивания"
        tools={
          canAdd ? (
            <button
              className="btn btn-primary btn-sm"
              onClick={() => setOpen(true)}
            >
              <Icon name="plus" size={12} /> Замер
            </button>
          ) : null
        }
        flush
      >
        {(!weighings || weighings.length === 0) ? (
          <EmptyState
            icon="chart"
            title="Взвешиваний пока нет"
            description="Сделайте первое взвешивание выборки птицы — после этого партия перейдёт в статус «Откорм» и начнётся отслеживание прироста и FCR."
            action={canAdd ? {
              label: 'Сделать замер',
              onClick: () => setOpen(true),
            } : undefined}
            hint="Обычно взвешивают каждые 5–7 дней по выборке 30–100 голов."
          />
        ) : (
          <DataTable<DailyWeighing>
            isLoading={isLoading}
            rows={weighings}
            rowKey={(w) => w.id}
            emptyMessage="—"
            columns={[
              { key: 'day', label: 'День', mono: true, width: 60,
                render: (w) => w.day_of_age },
              { key: 'date', label: 'Дата', mono: true, cellStyle: { fontSize: 12 },
                render: (w) => w.date },
              { key: 'sample', label: 'Выборка', align: 'right', mono: true,
                render: (w) => w.sample_size },
              { key: 'avg', label: 'Ср. вес, кг', align: 'right', mono: true,
                cellStyle: { fontWeight: 600 },
                render: (w) => parseFloat(w.avg_weight_kg).toLocaleString('ru-RU', {
                  maximumFractionDigits: 3,
                }) },
              { key: 'gain', label: 'Прирост, кг', align: 'right', mono: true,
                cellStyle: { fontSize: 12 },
                render: (w) => w.gain_kg ? (
                  <span style={{ color: 'var(--success)' }}>
                    +{parseFloat(w.gain_kg).toLocaleString('ru-RU', {
                      maximumFractionDigits: 3,
                    })}
                  </span>
                ) : '—' },
              { key: 'notes', label: 'Заметка', cellStyle: { fontSize: 11, color: 'var(--fg-3)' },
                render: (w) => w.notes || '—' },
              { key: 'actions', label: '', width: 60, align: 'right',
                render: (w) => (
                  <RowActions
                    actions={[
                      {
                        label: 'Удалить',
                        danger: true,
                        disabled: del.isPending,
                        onClick: () => setConfirmDel(w),
                      },
                    ]}
                  />
                ) },
            ]}
          />
        )}
      </Panel>

      {open && <WeighingModal batch={batch} onClose={() => setOpen(false)} />}
      {confirmDel && (
        <ConfirmDeleteWithReason
          title="Удалить взвешивание?"
          subject={`день ${confirmDel.day_of_age} · ${parseFloat(confirmDel.avg_weight_kg).toFixed(3)} кг`}
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
