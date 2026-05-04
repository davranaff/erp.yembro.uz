'use client';

import { useState } from 'react';

import ConfirmDeleteWithReason from '@/components/ConfirmDeleteWithReason';
import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import EmptyState from '@/components/ui/EmptyState';
import Icon from '@/components/ui/Icon';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import { labTestsCrud } from '@/hooks/useSlaughter';
import type { SlaughterLabTest, SlaughterShift } from '@/types/auth';

import LabTestModal from './LabTestModal';

interface Props {
  shift: SlaughterShift;
}

const STATUS_LABEL: Record<SlaughterLabTest['status'], string> = {
  pending: 'В работе',
  passed: 'Норма',
  failed: 'Отклонение',
};

const STATUS_TONE: Record<SlaughterLabTest['status'], 'warn' | 'success' | 'danger'> = {
  pending: 'warn',
  passed: 'success',
  failed: 'danger',
};

export default function LabTestsPanel({ shift }: Props) {
  const { data: tests, isLoading } = labTestsCrud.useList({ shift: shift.id });
  const del = labTestsCrud.useDelete();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<SlaughterLabTest | null>(null);
  const [confirmDel, setConfirmDel] = useState<SlaughterLabTest | null>(null);

  const canEdit = shift.status === 'active' || shift.status === 'closed';

  return (
    <>
      <Panel
        title={`Лабораторные тесты (${tests?.length ?? 0})`}
        tools={
          canEdit ? (
            <button
              className="btn btn-primary btn-sm"
              onClick={() => { setEditing(null); setOpen(true); }}
            >
              <Icon name="plus" size={12} /> Тест
            </button>
          ) : null
        }
        flush
      >
        {(!tests || tests.length === 0) ? (
          <EmptyState
            icon="chart"
            title="Тестов пока нет"
            description="Запишите результаты лабораторных исследований: микробиология, физико-химия. Помогает контролировать соответствие СанПиН."
            action={canEdit ? {
              label: 'Записать тест',
              onClick: () => { setEditing(null); setOpen(true); },
            } : undefined}
            hint="Стандартный набор: КМАФАнМ, Сальмонелла, Листерия, E.coli."
          />
        ) : (
          <DataTable<SlaughterLabTest>
            isLoading={isLoading}
            rows={tests}
            rowKey={(t) => t.id}
            emptyMessage="—"
            columns={[
              { key: 'indicator', label: 'Показатель', mono: true,
                render: (t) => t.indicator },
              { key: 'normal', label: 'Норма', mono: true, cellStyle: { fontSize: 12 },
                render: (t) => t.normal_range },
              { key: 'actual', label: 'Факт', mono: true, cellStyle: { fontWeight: 600 },
                render: (t) => t.actual_value },
              { key: 'status', label: 'Результат',
                render: (t) => (
                  <Badge tone={STATUS_TONE[t.status]} dot>{STATUS_LABEL[t.status]}</Badge>
                ) },
              { key: 'date', label: 'Когда', mono: true, cellStyle: { fontSize: 11, color: 'var(--fg-3)' },
                render: (t) => (t.result_at ?? t.sampled_at ?? '').slice(0, 10) || '—' },
              { key: 'op', label: 'Оператор', cellStyle: { fontSize: 12 },
                render: (t) => t.operator_name ?? '—' },
              { key: 'actions', label: '', width: 60, align: 'right',
                render: (t) => (
                  <RowActions
                    actions={[
                      {
                        label: 'Редактировать',
                        hidden: !canEdit,
                        onClick: () => { setEditing(t); setOpen(true); },
                      },
                      {
                        label: 'Удалить',
                        danger: true,
                        hidden: !canEdit,
                        disabled: del.isPending,
                        onClick: () => setConfirmDel(t),
                      },
                    ]}
                  />
                ) },
            ]}
          />
        )}
      </Panel>

      {open && (
        <LabTestModal
          shift={shift}
          test={editing}
          onClose={() => { setOpen(false); setEditing(null); }}
        />
      )}
      {confirmDel && (
        <ConfirmDeleteWithReason
          title="Удалить лабораторный тест?"
          subject={`${confirmDel.indicator} · ${confirmDel.actual_value}`}
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
