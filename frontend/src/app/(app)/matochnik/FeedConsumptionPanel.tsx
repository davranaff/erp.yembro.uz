'use client';

import { useMemo, useState } from 'react';

import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import Panel from '@/components/ui/Panel';
import { feedConsumptionCrud } from '@/hooks/useMatochnik';
import type { BreedingFeedConsumption, BreedingHerd } from '@/types/auth';

import FeedConsumptionModal from './FeedConsumptionModal';

interface Props {
  herd: BreedingHerd;
}

function fmtKg(v: string | null | undefined): string {
  if (v == null) return '—';
  const n = parseFloat(v);
  return Number.isNaN(n) ? '—' : n.toLocaleString('ru-RU') + ' кг';
}

function fmtUzs(v: string | null | undefined): string {
  if (v == null) return '—';
  const n = parseFloat(v);
  return Number.isNaN(n) ? '—' : n.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
}

export default function FeedConsumptionPanel({ herd }: Props) {
  const [open, setOpen] = useState(false);
  const { data, isLoading } = feedConsumptionCrud.useList({ herd: herd.id });

  const records = useMemo(() => (data ?? []).slice(0, 20), [data]);

  return (
    <>
      <Panel
        title={`Расход кормов · ${data?.length ?? 0} записей`}
        flush
        tools={
          <button className="btn btn-secondary btn-sm" onClick={() => setOpen(true)}>
            <Icon name="plus" size={12} /> Расход
          </button>
        }
      >
        <DataTable<BreedingFeedConsumption>
          isLoading={isLoading}
          rows={records}
          rowKey={(r) => r.id}
          emptyMessage="Записей нет. Нажмите «Расход» чтобы зафиксировать суточное потребление."
          columns={[
            { key: 'date', label: 'Дата', mono: true, cellStyle: { fontSize: 12 },
              render: (r) => r.date },
            { key: 'feed_batch', label: 'Партия корма', cellStyle: { fontSize: 12 },
              render: (r) => r.feed_batch_doc ? (
                <>
                  <span className="mono">{r.feed_batch_doc}</span>
                  {r.feed_batch_recipe && (
                    <span style={{ fontSize: 11, color: 'var(--fg-3)', marginLeft: 4 }}>
                      · {r.feed_batch_recipe}
                    </span>
                  )}
                </>
              ) : <span style={{ color: 'var(--fg-3)' }}>—</span> },
            { key: 'qty', label: 'Количество', align: 'right', mono: true,
              render: (r) => fmtKg(r.quantity_kg) },
            { key: 'per_head', label: 'На голову', align: 'right', mono: true, muted: true,
              render: (r) => r.per_head_g ? `${parseFloat(r.per_head_g).toFixed(1)} г` : '—' },
            { key: 'cost', label: 'Стоимость', align: 'right', mono: true,
              cellStyle: { fontSize: 12, fontWeight: 600 },
              render: (r) => r.total_cost_uzs ? fmtUzs(r.total_cost_uzs) : '—' },
          ]}
        />
      </Panel>

      {open && (
        <FeedConsumptionModal herd={herd} onClose={() => setOpen(false)} />
      )}
    </>
  );
}
