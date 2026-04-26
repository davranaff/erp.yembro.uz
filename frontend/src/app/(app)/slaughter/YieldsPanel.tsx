'use client';

import { useState } from 'react';

import ConfirmDeleteWithReason from '@/components/ConfirmDeleteWithReason';
import DataTable from '@/components/ui/DataTable';
import EmptyState from '@/components/ui/EmptyState';
import Icon from '@/components/ui/Icon';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import { yieldsCrud } from '@/hooks/useSlaughter';
import type { SlaughterShift, SlaughterYield } from '@/types/auth';

import BulkYieldsModal from './BulkYieldsModal';
import YieldModal from './YieldModal';

interface Props {
  shift: SlaughterShift;
}

export default function YieldsPanel({ shift }: Props) {
  const { data: yields, isLoading } = yieldsCrud.useList({ shift: shift.id });
  const del = yieldsCrud.useDelete();
  const [open, setOpen] = useState(false);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [editing, setEditing] = useState<SlaughterYield | null>(null);
  const [confirmDel, setConfirmDel] = useState<SlaughterYield | null>(null);

  const canEdit = shift.status === 'active' || shift.status === 'closed';

  return (
    <>
      <Panel
        title={`Выходы по SKU (${yields?.length ?? 0})`}
        tools={
          canEdit ? (
            <div style={{ display: 'flex', gap: 6 }}>
              <button
                className="btn btn-primary btn-sm"
                onClick={() => setBulkOpen(true)}
              >
                <Icon name="chart" size={12} /> Разделка партии
              </button>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => { setEditing(null); setOpen(true); }}
              >
                <Icon name="plus" size={12} /> Один SKU
              </button>
            </div>
          ) : null
        }
        flush
      >
        {(!yields || yields.length === 0) ? (
          <EmptyState
            icon="check"
            title="Выходов пока нет"
            description="Откройте «Разделка партии» — введите все SKU одной формой с автозаполнением по нормам бройлера."
            action={canEdit ? {
              label: 'Разделка партии',
              onClick: () => setBulkOpen(true),
            } : undefined}
            hint="Стандартный выход тушки бройлера: 70-75% от живого веса."
          />
        ) : (
          <DataTable<SlaughterYield>
            isLoading={isLoading}
            rows={yields}
            rowKey={(y) => y.id}
            emptyMessage="—"
            columns={[
              { key: 'sku', label: 'SKU', mono: true,
                render: (y) => y.nom_sku ?? y.nomenclature.slice(0, 8) },
              { key: 'name', label: 'Наименование',
                render: (y) => y.nom_name ?? '—' },
              { key: 'qty', label: 'Кол-во', align: 'right', mono: true,
                cellStyle: { fontWeight: 600 },
                render: (y) => parseFloat(y.quantity).toLocaleString('ru-RU', {
                  maximumFractionDigits: 3,
                }) },
              { key: 'unit', label: 'Ед.', mono: true, muted: true,
                render: (y) => y.unit_code ?? '—' },
              { key: 'yield', label: 'Выход %', align: 'right', mono: true,
                cellStyle: { fontWeight: 600 },
                render: (y) => {
                  if (!y.yield_pct) return '—';
                  const color = y.is_within_tolerance ? 'var(--fg-1)' : 'var(--danger)';
                  return (
                    <span style={{ color }}>
                      {parseFloat(y.yield_pct).toFixed(2)}%
                    </span>
                  );
                } },
              { key: 'norm', label: 'Норма %', align: 'right', mono: true, muted: true,
                cellStyle: { fontSize: 12 },
                render: (y) => y.norm_pct
                  ? parseFloat(y.norm_pct).toFixed(2) + '%'
                  : '—' },
              { key: 'dev', label: 'Δ к норме', align: 'right', mono: true,
                cellStyle: { fontSize: 12 },
                render: (y) => {
                  if (!y.deviation_pct) return '—';
                  const dev = parseFloat(y.deviation_pct);
                  const color = y.is_within_tolerance
                    ? 'var(--fg-3)'
                    : 'var(--danger)';
                  const sign = dev > 0 ? '+' : '';
                  return (
                    <span style={{ color }}>
                      {sign}{dev.toFixed(2)}%
                    </span>
                  );
                } },
              { key: 'share', label: 'Доля cost, %', align: 'right', mono: true, muted: true,
                cellStyle: { fontSize: 11 },
                render: (y) => y.share_percent
                  ? parseFloat(y.share_percent).toFixed(2)
                  : '—' },
              { key: 'out', label: 'Выход. партия', mono: true, muted: true,
                cellStyle: { fontSize: 11 },
                render: (y) => y.output_batch_doc ?? '—' },
              { key: 'actions', label: '', width: 60, align: 'right',
                render: (y) => (
                  <RowActions
                    actions={[
                      {
                        label: 'Редактировать',
                        hidden: !canEdit,
                        onClick: () => { setEditing(y); setOpen(true); },
                      },
                      {
                        label: 'Удалить',
                        danger: true,
                        hidden: !canEdit,
                        disabled: del.isPending,
                        onClick: () => setConfirmDel(y),
                      },
                    ]}
                  />
                ) },
            ]}
          />
        )}
      </Panel>

      {open && (
        <YieldModal
          shift={shift}
          yieldRow={editing}
          onClose={() => { setOpen(false); setEditing(null); }}
        />
      )}
      {bulkOpen && (
        <BulkYieldsModal
          shift={shift}
          onClose={() => setBulkOpen(false)}
        />
      )}
      {confirmDel && (
        <ConfirmDeleteWithReason
          title="Удалить выход?"
          subject={`${confirmDel.nom_sku ?? '—'} · ${parseFloat(confirmDel.quantity).toLocaleString('ru-RU')} ${confirmDel.unit_code ?? ''}`}
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
