'use client';

import { useState } from 'react';

import HelpHint from '@/components/ui/HelpHint';
import Modal from '@/components/ui/Modal';
import { ApiError } from '@/lib/api';
import { useProductionBlocks } from '@/hooks/useBlocks';
import { useExecuteTask } from '@/hooks/useFeed';
import { useWarehouses } from '@/hooks/useStockMovements';
import type { ProductionTask } from '@/types/auth';

interface Props {
  task: ProductionTask;
  onClose: () => void;
}

export default function ExecuteTaskModal({ task, onClose }: Props) {
  const { data: warehouses } = useWarehouses({ module_code: 'feed' });
  const { data: bins } = useProductionBlocks({
    module_code: 'feed', kind: 'storage_bin',
  });
  const exec = useExecuteTask();

  const [outputWarehouse, setOutputWarehouse] = useState('');
  const [storageBin, setStorageBin] = useState('');
  const [actualQty, setActualQty] = useState(task.planned_quantity_kg);

  const error = exec.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, string[]>) ?? {})
    : {};

  const handleSubmit = async () => {
    try {
      await exec.mutateAsync({
        id: task.id,
        body: { output_warehouse: outputWarehouse, storage_bin: storageBin, actual_quantity_kg: actualQty },
      });
      onClose();
    } catch { /* */ }
  };

  const planned = parseFloat(task.planned_quantity_kg || '0');
  const actual = parseFloat(actualQty || '0');
  const delta = actual - planned;
  const deltaPct = planned > 0 ? (delta / planned) * 100 : 0;

  return (
    <Modal
      title={`Провести замес · ${task.doc_number}`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={!outputWarehouse || !storageBin || !actualQty || exec.isPending}
            onClick={handleSubmit}
          >
            {exec.isPending ? 'Выполнение…' : 'Провести замес'}
          </button>
        </>
      }
    >
      <div style={{
        padding: 10, background: 'var(--bg-soft)', borderRadius: 6,
        fontSize: 12, lineHeight: 1.5, marginBottom: 14,
      }}>
        <div style={{ fontWeight: 600, marginBottom: 4 }}>
          Что произойдёт при проведении:
        </div>
        <ul style={{ margin: 0, paddingLeft: 18, color: 'var(--fg-2)' }}>
          <li>Сырьё со склада списывается по составу версии</li>
          <li>Создаётся партия готового корма с автоматической себестоимостью</li>
          <li>Делается проводка в журнале (Дт «Готовая продукция» / Кт «Сырьё»)</li>
          <li>Задание переходит в статус «Закрыто»</li>
        </ul>
      </div>

      <div className="field">
        <label>
          Склад готовой продукции *
          <HelpHint
            text="Куда положим выпущенный корм."
            details="Это должен быть склад модуля «Корма» предназначенный для готовой продукции (не сырьевой). Если склад пуст — создайте в /stock."
          />
        </label>
        <select className="input" value={outputWarehouse} onChange={(e) => setOutputWarehouse(e.target.value)}>
          <option value="">—</option>
          {warehouses?.filter((w) => w.module_code === 'feed').map((w) => (
            <option key={w.id} value={w.id}>{w.code} · {w.name}</option>
          ))}
        </select>
      </div>
      <div className="field">
        <label>
          Бункер хранения *
          <HelpHint
            text="Конкретный бункер на складе ГП."
            details="Корм хранится в бункерах разной ёмкости. Если бункеров нет — создайте блоки типа storage_bin в /blocks."
          />
        </label>
        <select className="input" value={storageBin} onChange={(e) => setStorageBin(e.target.value)}>
          <option value="">—</option>
          {bins?.map((b) => <option key={b.id} value={b.id}>{b.code} · {b.name}</option>)}
        </select>
      </div>
      <div className="field">
        <label>
          Фактический выпуск, кг *
          <HelpHint
            text="Сколько корма реально получилось."
            details={
              `План задания — ${planned.toLocaleString('ru-RU')} кг. `
              + 'В реальности возможны отклонения (точность весов, потери при гранулировании). '
              + 'Если факт сильно отличается от плана — проверьте расход сырья. '
              + 'Себестоимость 1 кг = (стоимость списанного сырья) ÷ фактический выпуск.'
            }
          />
        </label>
        <input
          className="input mono"
          type="number"
          step="0.001"
          value={actualQty}
          onChange={(e) => setActualQty(e.target.value)}
        />
        {actual > 0 && Math.abs(deltaPct) > 0.5 && (
          <div style={{
            fontSize: 11,
            color: Math.abs(deltaPct) > 5 ? 'var(--warning)' : 'var(--fg-3)',
            marginTop: 4,
          }}>
            Δ к плану: {delta > 0 ? '+' : ''}{delta.toLocaleString('ru-RU', { maximumFractionDigits: 1 })} кг
            ({deltaPct > 0 ? '+' : ''}{deltaPct.toFixed(1)}%)
            {Math.abs(deltaPct) > 5 && ' · значительное отклонение'}
          </div>
        )}
        {fieldErrors.actual_quantity_kg && <div style={{ fontSize: 11, color: 'var(--danger)' }}>{fieldErrors.actual_quantity_kg.join(' · ')}</div>}
      </div>
      {error && error.status !== 400 && (
        <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 12 }}>Ошибка: {error.message}</div>
      )}
    </Modal>
  );
}
