'use client';

import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import {
  useHerdEggBatches,
  useSendToIncubation,
} from '@/hooks/useMatochnik';
import type { Batch, BreedingHerd } from '@/types/auth';

interface Props {
  herd: BreedingHerd;
}

const STATE_LABEL: Record<string, string> = {
  active: 'Активна',
  in_transit: 'В пути',
  completed: 'Завершена',
  rejected: 'Отклонена',
  review: 'На проверке',
};

const STATE_TONE: Record<string, 'success' | 'info' | 'neutral' | 'danger' | 'warn'> = {
  active: 'success',
  in_transit: 'info',
  completed: 'neutral',
  rejected: 'danger',
  review: 'warn',
};

/** Партию можно отправить в инкубацию только если она в маточнике и активна. */
function canSendToIncubation(b: Batch): boolean {
  if (b.state !== 'active') return false;
  if (parseFloat(b.current_quantity) <= 0) return false;
  const cur = b.current_module_code ?? b.origin_module_code;
  return cur === 'matochnik';
}

export default function EggBatchesPanel({ herd }: Props) {
  const { data, isLoading } = useHerdEggBatches(herd.id);
  const sendMut = useSendToIncubation();

  const batches = data ?? [];

  const handleSend = (b: Batch) => {
    if (!window.confirm(
      `Отправить партию ${b.doc_number} в инкубацию?\n` +
      `Будет создана межмодульная передача, партия перейдёт в модуль incubation.`,
    )) return;
    sendMut.mutate(
      { id: b.id },
      {
        onError: (err) => alert('Не удалось: ' + err.message),
      },
    );
  };

  return (
    <Panel title={`Партии яиц · ${batches.length}`} flush>
      <DataTable<Batch>
        isLoading={isLoading}
        rows={batches}
        rowKey={(b) => b.id}
        emptyMessage="Партий пока нет. Сформируйте партию из яйцесбора кнопкой «Сформировать партию»."
        columns={[
          { key: 'doc', label: 'Документ', mono: true, cellStyle: { fontSize: 12 },
            render: (b) => b.doc_number },
          { key: 'started', label: 'Посажено', mono: true, muted: true,
            render: (b) => b.started_at },
          { key: 'qty', label: 'Количество', align: 'right', mono: true,
            render: (b) => (
              <>
                {parseFloat(b.current_quantity).toLocaleString('ru-RU')}
                <span style={{ fontSize: 10, color: 'var(--fg-3)', marginLeft: 4 }}>
                  {b.unit_code ?? ''}
                </span>
              </>
            ) },
          { key: 'cost', label: 'Себестоимость', align: 'right', mono: true,
            cellStyle: { fontSize: 12 },
            render: (b) => parseFloat(b.accumulated_cost_uzs).toLocaleString('ru-RU', { maximumFractionDigits: 0 }) },
          { key: 'module', label: 'Модуль', mono: true, muted: true,
            render: (b) => b.current_module_code ?? b.origin_module_code },
          { key: 'state', label: 'Статус',
            render: (b) => (
              <Badge tone={STATE_TONE[b.state] ?? 'neutral'}>
                {STATE_LABEL[b.state] ?? b.state}
              </Badge>
            ) },
          { key: 'actions', label: '', align: 'right', width: 60,
            render: (b) => (
              <RowActions
                actions={[
                  {
                    label: 'В инкубацию',
                    hidden: !canSendToIncubation(b),
                    disabled: sendMut.isPending,
                    onClick: () => handleSend(b),
                  },
                ]}
              />
            ) },
        ]}
      />
    </Panel>
  );
}
