'use client';

import { useState } from 'react';

import Modal from '@/components/ui/Modal';
import { ApiError } from '@/lib/api';
import { usePostShift } from '@/hooks/useSlaughter';
import { useWarehouses } from '@/hooks/useStockMovements';
import type { SlaughterShift } from '@/types/auth';

interface Props {
  shift: SlaughterShift;
  onClose: () => void;
}

export default function PostShiftModal({ shift, onClose }: Props) {
  // Источник — склад откорма (откуда живая птица), приёмник — склад убойни.
  const { data: feedlotWarehouses } = useWarehouses({ module_code: 'feedlot' });
  const { data: slaughterWarehouses } = useWarehouses({ module_code: 'slaughter' });
  const post = usePostShift();
  const [outputWh, setOutputWh] = useState('');
  const [sourceWh, setSourceWh] = useState('');

  const error = post.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, string[]>) ?? {})
    : {};

  const submit = async () => {
    try {
      await post.mutateAsync({
        id: shift.id,
        body: { output_warehouse: outputWh, source_warehouse: sourceWh },
      });
      onClose();
    } catch { /* */ }
  };

  return (
    <Modal
      title={`Закрыть смену · ${shift.doc_number}`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={!outputWh || !sourceWh || post.isPending}
            onClick={submit}
          >
            {post.isPending ? 'Проведение…' : 'Провести смену'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
        Создаст SlaughterYield не требуется (уже введены), output-Batch, StockMovement,
        JournalEntry. Сторнируется через «Реверс». Перед проведением проверьте:
        ветеринарную инспекцию пройдено, выходы введены, баланс {' '}
        <strong>Σ выходы ≈ живой вес ±10%</strong>.
      </div>
      <div className="field">
        <label>Склад живой птицы (источник) *</label>
        <select className="input" value={sourceWh} onChange={(e) => setSourceWh(e.target.value)}>
          <option value="">—</option>
          {feedlotWarehouses?.map((w) => <option key={w.id} value={w.id}>{w.code} · {w.name}</option>)}
        </select>
        {fieldErrors.source_warehouse && (
          <div style={{ fontSize: 11, color: 'var(--danger)' }}>
            {Array.isArray(fieldErrors.source_warehouse)
              ? fieldErrors.source_warehouse.join(' · ')
              : String(fieldErrors.source_warehouse)}
          </div>
        )}
      </div>
      <div className="field">
        <label>Склад ГП (выход) *</label>
        <select className="input" value={outputWh} onChange={(e) => setOutputWh(e.target.value)}>
          <option value="">—</option>
          {slaughterWarehouses?.map((w) => <option key={w.id} value={w.id}>{w.code} · {w.name}</option>)}
        </select>
        {fieldErrors.output_warehouse && (
          <div style={{ fontSize: 11, color: 'var(--danger)' }}>
            {Array.isArray(fieldErrors.output_warehouse)
              ? fieldErrors.output_warehouse.join(' · ')
              : String(fieldErrors.output_warehouse)}
          </div>
        )}
      </div>
      {fieldErrors.quality_check && (
        <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 8 }}>
          {Array.isArray(fieldErrors.quality_check)
            ? fieldErrors.quality_check.join(' · ')
            : String(fieldErrors.quality_check)}
        </div>
      )}
      {fieldErrors.yields && (
        <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 8 }}>
          {Array.isArray(fieldErrors.yields)
            ? fieldErrors.yields.join(' · ')
            : String(fieldErrors.yields)}
        </div>
      )}
      {error && error.status !== 400 && (
        <div style={{ fontSize: 12, color: 'var(--danger)' }}>Ошибка: {error.message}</div>
      )}
    </Modal>
  );
}
