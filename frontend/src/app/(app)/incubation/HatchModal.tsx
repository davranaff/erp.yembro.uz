'use client';

import { useState } from 'react';

import Modal from '@/components/ui/Modal';
import { ApiError } from '@/lib/api';
import { useHatch } from '@/hooks/useIncubation';
import { useNomenclatureItems } from '@/hooks/useNomenclature';
import type { IncubationRun } from '@/types/auth';

interface Props {
  run: IncubationRun;
  onClose: () => void;
}

export default function HatchModal({ run, onClose }: Props) {
  const { data: items } = useNomenclatureItems({ is_active: 'true' });
  const hatch = useHatch();

  const [chickNom, setChickNom] = useState('');
  const [hatchedCount, setHatchedCount] = useState('');
  const [discardedCount, setDiscardedCount] = useState('');
  const [actualDate, setActualDate] = useState(new Date().toISOString().slice(0, 10));

  const error = hatch.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, string[]>) ?? {})
    : {};

  const handleSubmit = async () => {
    try {
      await hatch.mutateAsync({
        id: run.id,
        body: {
          chick_nomenclature: chickNom,
          hatched_count: Number(hatchedCount),
          discarded_count: discardedCount ? Number(discardedCount) : undefined,
          actual_hatch_date: actualDate,
        },
      });
      onClose();
    } catch { /* */ }
  };

  return (
    <Modal
      title={`Вывод · ${run.doc_number}`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={!chickNom || !hatchedCount || hatch.isPending}
            onClick={handleSubmit}
          >
            {hatch.isPending ? 'Выполнение…' : 'Провести вывод'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
        Создаст Batch цыплят (parent_batch = партия яиц) и закроет egg-batch.
      </div>
      <div className="field">
        <label>Номенклатура цыплят *</label>
        <select className="input" value={chickNom} onChange={(e) => setChickNom(e.target.value)}>
          <option value="">—</option>
          {items?.map((it) => <option key={it.id} value={it.id}>{it.sku} · {it.name}</option>)}
        </select>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>Выведено *</label>
          <input className="input mono" type="number" value={hatchedCount} onChange={(e) => setHatchedCount(e.target.value)} />
          {fieldErrors.hatched_count && <div style={{ fontSize: 11, color: 'var(--danger)' }}>{fieldErrors.hatched_count.join(' · ')}</div>}
        </div>
        <div className="field">
          <label>Отбраковано</label>
          <input className="input mono" type="number" value={discardedCount} onChange={(e) => setDiscardedCount(e.target.value)} />
        </div>
        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>Дата вывода *</label>
          <input className="input" type="date" value={actualDate} onChange={(e) => setActualDate(e.target.value)} />
        </div>
      </div>
      {error && error.status !== 400 && (
        <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 12 }}>Ошибка: {error.message}</div>
      )}
    </Modal>
  );
}
