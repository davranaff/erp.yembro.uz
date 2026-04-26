'use client';

import { useState } from 'react';

import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import { mirageCrud } from '@/hooks/useIncubation';
import type { IncubationRun, MirageInspection } from '@/types/auth';

import MirageModal from './MirageModal';

interface Props {
  run: IncubationRun;
}

export default function MiragePanel({ run }: Props) {
  const { data, isLoading } = mirageCrud.useList({ run: run.id });
  const del = mirageCrud.useDelete();

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<MirageInspection | null>(null);

  const rows = data ?? [];

  const handleDelete = (m: MirageInspection) => {
    if (!window.confirm(`Удалить овоскопию за ${m.inspection_date}?`)) return;
    del.mutate(m.id, { onError: (err) => alert(err.message) });
  };

  return (
    <>
      <Panel
        title="Овоскопия"
        tools={
          <button
            className="btn btn-primary btn-sm"
            onClick={() => { setEditing(null); setModalOpen(true); }}
          >
            <Icon name="plus" size={12} /> Овоскопия
          </button>
        }
      >
        <DataTable<MirageInspection>
          isLoading={isLoading}
          rows={rows}
          rowKey={(m) => m.id}
          emptyMessage="Овоскопий ещё не было. Обычно проводят на 7-й, 14-й и 18-й день."
          columns={[
            { key: 'date', label: 'Дата', mono: true,
              render: (m) => m.inspection_date },
            { key: 'day', label: 'День', mono: true, width: 60,
              render: (m) => `${m.day_of_incubation}/${run.days_total}` },
            { key: 'inspected', label: 'Осмотрено', align: 'right', mono: true,
              render: (m) => m.inspected_count.toLocaleString('ru-RU') },
            { key: 'fertile', label: 'Оплод.', align: 'right', mono: true,
              render: (m) => (
                <span style={{ color: 'var(--success)' }}>
                  {m.fertile_count.toLocaleString('ru-RU')}
                </span>
              ) },
            { key: 'discarded', label: 'Брак', align: 'right', mono: true,
              render: (m) => (
                <span style={{ color: 'var(--danger)' }}>
                  {m.discarded_count.toLocaleString('ru-RU')}
                </span>
              ) },
            { key: 'infertile', label: 'Неоплод.', align: 'right', mono: true,
              render: (m) => {
                const inf = m.inspected_count - m.fertile_count - m.discarded_count;
                return (
                  <span style={{ color: 'var(--fg-3)' }}>
                    {inf.toLocaleString('ru-RU')}
                    {m.infertile_pct && (
                      <span style={{ fontSize: 10, marginLeft: 4 }}>
                        ({m.infertile_pct}%)
                      </span>
                    )}
                  </span>
                );
              } },
            { key: 'inspector', label: 'Инспектор', cellStyle: { fontSize: 11 },
              render: (m) => m.inspector_name ?? '—' },
            { key: 'actions', label: '', width: 60, align: 'right',
              render: (m) => (
                <RowActions
                  actions={[
                    { label: 'Править', onClick: () => { setEditing(m); setModalOpen(true); } },
                    { label: 'Удалить', danger: true, onClick: () => handleDelete(m) },
                  ]}
                />
              ) },
          ]}
        />
      </Panel>

      {modalOpen && (
        <MirageModal
          run={run}
          initial={editing}
          onClose={() => { setModalOpen(false); setEditing(null); }}
        />
      )}
    </>
  );
}
