'use client';

import { useState } from 'react';

import Modal from '@/components/ui/Modal';
import { ApiError } from '@/lib/api';
import { useDepopulateHerd } from '@/hooks/useMatochnik';
import type { BreedingHerd } from '@/types/auth';

interface Props {
  herd: BreedingHerd;
  onClose: () => void;
}

export default function DepopulateModal({ herd, onClose }: Props) {
  const dep = useDepopulateHerd();
  const [reduceBy, setReduceBy] = useState('');
  const [date, setDate] = useState<string>(new Date().toISOString().slice(0, 10));
  const [reason, setReason] = useState('');
  const [asMortality, setAsMortality] = useState(false);

  const error = dep.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, string[]>) ?? {})
    : {};

  const handleSubmit = async () => {
    try {
      await dep.mutateAsync({
        id: herd.id,
        body: { reduce_by: Number(reduceBy), date, reason, mark_as_mortality: asMortality },
      });
      onClose();
    } catch { /* */ }
  };

  return (
    <Modal
      title={`Снятие поголовья · ${herd.doc_number}`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={!reduceBy || dep.isPending}
            onClick={handleSubmit}
          >
            {dep.isPending ? 'Обработка…' : 'Снять'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
        Текущее поголовье: <b>{herd.current_heads.toLocaleString('ru-RU')} гол</b>.
        {' '}Снимаемое кол-во можно дополнительно записать как падёж.
      </div>
      <div className="field">
        <label>Снять голов *</label>
        <input
          className="input mono"
          type="number"
          value={reduceBy}
          onChange={(e) => setReduceBy(e.target.value)}
          max={herd.current_heads}
        />
        {fieldErrors.reduce_by && (
          <div style={{ fontSize: 11, color: 'var(--danger)' }}>{fieldErrors.reduce_by.join(' · ')}</div>
        )}
      </div>
      <div className="field">
        <label>Дата</label>
        <input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
      </div>
      <div className="field">
        <label>Причина</label>
        <input className="input" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="плановое снятие / выбраковка / …" />
      </div>
      <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 12, marginTop: 6 }}>
        <input type="checkbox" checked={asMortality} onChange={(e) => setAsMortality(e.target.checked)} />
        Записать как падёж (BreedingMortality)
      </label>
      {error && error.status !== 400 && (
        <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 12 }}>Ошибка: {error.message}</div>
      )}
    </Modal>
  );
}
