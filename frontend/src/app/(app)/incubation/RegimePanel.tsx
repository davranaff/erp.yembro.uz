'use client';

import { useState } from 'react';

import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import { regimeDaysCrud } from '@/hooks/useIncubation';
import type { IncubationRegimeDay, IncubationRun } from '@/types/auth';

import RegimeDayModal from './RegimeDayModal';

interface Props {
  run: IncubationRun;
}

function deltaCell(target: string | null, actual: string | null, threshold: number, suffix: string) {
  if (!actual) return <span style={{ color: 'var(--fg-3)' }}>—</span>;
  if (!target) return <span className="mono">{actual}{suffix}</span>;
  const d = parseFloat(actual) - parseFloat(target);
  const warn = Math.abs(d) > threshold;
  return (
    <span className="mono" style={{ color: warn ? 'var(--danger)' : 'var(--fg)' }}>
      {actual}{suffix}
      <span style={{ fontSize: 10, color: 'var(--fg-3)', marginLeft: 4 }}>
        ({d > 0 ? '+' : ''}{d.toFixed(1)})
      </span>
    </span>
  );
}

export default function RegimePanel({ run }: Props) {
  const { data, isLoading } = regimeDaysCrud.useList({ run: run.id, ordering: 'day' });
  const del = regimeDaysCrud.useDelete();

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<IncubationRegimeDay | null>(null);

  const rows = data ?? [];

  const handleDelete = (r: IncubationRegimeDay) => {
    if (!window.confirm(`Удалить замер за день ${r.day}?`)) return;
    del.mutate(r.id, { onError: (err) => alert(err.message) });
  };

  return (
    <>
      <Panel
        title="Режим инкубации"
        tools={
          <button
            className="btn btn-primary btn-sm"
            onClick={() => { setEditing(null); setModalOpen(true); }}
          >
            <Icon name="plus" size={12} /> Замер
          </button>
        }
      >
        <DataTable<IncubationRegimeDay>
          isLoading={isLoading}
          rows={rows}
          rowKey={(r) => r.id}
          emptyMessage="Замеров режима пока нет."
          columns={[
            { key: 'day', label: 'День', mono: true, width: 60,
              render: (r) => `${r.day}/${run.days_total}` },
            { key: 'temp', label: 'T °C (целев.)', mono: true,
              render: (r) => r.temperature_c },
            { key: 'tempActual', label: 'T факт.', mono: true,
              render: (r) => deltaCell(r.temperature_c, r.actual_temperature_c, 1.0, '°') },
            { key: 'hum', label: 'H % (целев.)', mono: true,
              render: (r) => r.humidity_percent },
            { key: 'humActual', label: 'H факт.', mono: true,
              render: (r) => deltaCell(r.humidity_percent, r.actual_humidity_percent, 5.0, '%') },
            { key: 'turns', label: 'Поворотов', align: 'right', mono: true,
              render: (r) => r.egg_turns_per_day },
            { key: 'observed', label: 'Замер', mono: true, cellStyle: { fontSize: 11 },
              render: (r) => r.observed_at
                ? new Date(r.observed_at).toLocaleString('ru-RU', {
                    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
                  })
                : '—' },
            { key: 'by', label: 'Технолог', cellStyle: { fontSize: 11 },
              render: (r) => r.observed_by_name ?? '—' },
            { key: 'actions', label: '', width: 60, align: 'right',
              render: (r) => (
                <RowActions
                  actions={[
                    { label: 'Править', onClick: () => { setEditing(r); setModalOpen(true); } },
                    { label: 'Удалить', danger: true, onClick: () => handleDelete(r) },
                  ]}
                />
              ) },
          ]}
        />
      </Panel>

      {modalOpen && (
        <RegimeDayModal
          run={run}
          initial={editing}
          onClose={() => { setModalOpen(false); setEditing(null); }}
        />
      )}
    </>
  );
}
