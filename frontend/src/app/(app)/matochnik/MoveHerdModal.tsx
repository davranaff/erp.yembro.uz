'use client';

import { useMemo, useState } from 'react';

import Modal from '@/components/ui/Modal';
import { useProductionBlocks } from '@/hooks/useBlocks';
import { useMoveHerd } from '@/hooks/useMatochnik';
import { ApiError } from '@/lib/api';
import type { BreedingHerd } from '@/types/auth';

interface Props {
  herd: BreedingHerd;
  onClose: () => void;
}

/**
 * Перемещение стада в другой корпус (без изменения поголовья).
 * Полезно при уплотнении, ремонте, перераспределении стад по корпусам.
 */
export default function MoveHerdModal({ herd, onClose }: Props) {
  const move = useMoveHerd();
  const { data: allBlocks } = useProductionBlocks({ kind: 'matochnik' });

  // Исключаем текущий блок
  const blocks = useMemo(
    () => (allBlocks ?? []).filter((b) => b.id !== herd.block),
    [allBlocks, herd.block],
  );

  const [block, setBlock] = useState('');
  const [reason, setReason] = useState('');

  const error = move.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, unknown>) ?? {})
    : {};

  const getFieldErr = (k: string): string | null => {
    const v = (fieldErrors as Record<string, unknown>)[k];
    if (Array.isArray(v)) return v.join(' · ');
    if (typeof v === 'string') return v;
    return null;
  };

  const canSave = Boolean(block) && !move.isPending;

  const handleSave = async () => {
    try {
      await move.mutateAsync({ id: herd.id, body: { block, reason } });
      onClose();
    } catch {
      /* */
    }
  };

  return (
    <Modal
      title={`Перевести стадо ${herd.doc_number}`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button className="btn btn-primary" disabled={!canSave} onClick={handleSave}>
            {move.isPending ? 'Перемещение…' : 'Переместить'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
        Перемещение стада в другой корпус без изменения поголовья. Сохраняется
        в аудит-журнале с указанной причиной.
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 12 }}>
        <div className="field">
          <label>Текущий корпус</label>
          <div className="input mono" style={{ background: 'var(--bg-soft)', cursor: 'default' }}>
            {herd.block_code ?? '—'}
          </div>
        </div>

        <div className="field">
          <label>Новый корпус *</label>
          <select className="input" value={block} onChange={(e) => setBlock(e.target.value)}>
            <option value="">—</option>
            {blocks.map((b) => (
              <option key={b.id} value={b.id}>{b.code} · {b.name}</option>
            ))}
          </select>
          {blocks.length === 0 && (
            <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
              Других корпусов маточника нет. Добавьте их на странице «Блоки».
            </div>
          )}
          {getFieldErr('block') && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getFieldErr('block')}</div>
          )}
        </div>

        <div className="field">
          <label>Причина</label>
          <input
            className="input"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="например: ремонт корпуса К-02"
          />
        </div>
      </div>

      {error instanceof ApiError && error.status !== 400 && (
        <div style={{ marginTop: 10, padding: 8, background: '#fef2f2', color: 'var(--danger)', borderRadius: 6, fontSize: 12 }}>
          {error.message}
        </div>
      )}
    </Modal>
  );
}
