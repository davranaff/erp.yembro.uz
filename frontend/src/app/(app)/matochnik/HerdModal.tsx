'use client';

import { useEffect, useState } from 'react';

import Modal from '@/components/ui/Modal';
import { ApiError } from '@/lib/api';
import { useProductionBlocks } from '@/hooks/useBlocks';
import { useModules } from '@/hooks/useModules';
import { herdsCrud } from '@/hooks/useMatochnik';
import { usePeople } from '@/hooks/usePeople';
import type { BreedingHerd } from '@/types/auth';

interface Props {
  initial?: BreedingHerd | null;
  onClose: () => void;
  onSaved?: (h: BreedingHerd) => void;
}

export default function HerdModal({ initial, onClose, onSaved }: Props) {
  const isEdit = !!initial;
  const create = herdsCrud.useCreate();
  const update = herdsCrud.useUpdate();
  const error = (isEdit ? update.error : create.error) ?? null;

  const { data: modules } = useModules();
  const { data: blocks } = useProductionBlocks({ kind: 'matochnik' });
  const { data: people } = usePeople({ is_active: 'true' });

  const matochnikModuleId = modules?.find((m) => m.code === 'matochnik')?.id ?? '';

  const [docNumber, setDocNumber] = useState(initial?.doc_number ?? '');
  const [block, setBlock] = useState(initial?.block ?? '');
  const [direction, setDirection] = useState(initial?.direction ?? 'broiler_parent');
  const [placedAt, setPlacedAt] = useState(initial?.placed_at ?? new Date().toISOString().slice(0, 10));
  const [initialHeads, setInitialHeads] = useState(String(initial?.initial_heads ?? ''));
  const [currentHeads, setCurrentHeads] = useState(String(initial?.current_heads ?? ''));
  const [ageWeeks, setAgeWeeks] = useState(String(initial?.age_weeks_at_placement ?? ''));
  const [technologist, setTechnologist] = useState(initial?.technologist ?? '');
  const [status, setStatus] = useState(initial?.status ?? 'growing');
  const [notes, setNotes] = useState(initial?.notes ?? '');

  useEffect(() => {
    if (initial) return;
    if (initialHeads && !currentHeads) setCurrentHeads(initialHeads);
  }, [initialHeads, currentHeads, initial]);

  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, string[]>) ?? {})
    : {};

  const handleSave = async () => {
    if (!matochnikModuleId) {
      alert('Модуль matochnik не найден.');
      return;
    }
    const payload = {
      doc_number: docNumber,
      module: matochnikModuleId,
      block,
      direction,
      placed_at: placedAt,
      initial_heads: Number(initialHeads),
      current_heads: Number(currentHeads || initialHeads),
      age_weeks_at_placement: Number(ageWeeks),
      status,
      technologist,
      notes,
    };
    try {
      const res = isEdit && initial
        ? await update.mutateAsync({ id: initial.id, patch: payload })
        : await create.mutateAsync(payload);
      onSaved?.(res);
      onClose();
    } catch { /* field errors */ }
  };

  return (
    <Modal
      title={isEdit ? `Стадо · ${initial?.doc_number}` : 'Новое стадо'}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={create.isPending || update.isPending || !docNumber || !block || !technologist || !initialHeads || !ageWeeks}
            onClick={handleSave}
          >
            {create.isPending || update.isPending ? 'Сохранение…' : 'Сохранить'}
          </button>
        </>
      }
    >
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>Номер *</label>
          <input
            className="input mono"
            value={docNumber}
            onChange={(e) => setDocNumber(e.target.value)}
            disabled={isEdit}
            placeholder="СТ-2026-01"
          />
          {fieldErrors.doc_number && <div style={{ fontSize: 11, color: 'var(--danger)' }}>{fieldErrors.doc_number.join(' · ')}</div>}
        </div>
        <div className="field">
          <label>Направление *</label>
          <select className="input" value={direction} onChange={(e) => setDirection(e.target.value as typeof direction)}>
            <option value="broiler_parent">Бройлерное родительское</option>
            <option value="layer_parent">Яичное родительское</option>
          </select>
        </div>
        <div className="field">
          <label>Корпус *</label>
          <select className="input" value={block} onChange={(e) => setBlock(e.target.value)}>
            <option value="">— выберите —</option>
            {blocks?.map((b) => (
              <option key={b.id} value={b.id}>{b.code} · {b.name}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Статус</label>
          <select className="input" value={status} onChange={(e) => setStatus(e.target.value as typeof status)}>
            <option value="growing">Разгон</option>
            <option value="producing">Продуктив</option>
            <option value="depopulated">Снято</option>
          </select>
        </div>
        <div className="field">
          <label>Дата посадки *</label>
          <input className="input" type="date" value={placedAt} onChange={(e) => setPlacedAt(e.target.value)} />
        </div>
        <div className="field">
          <label>Возраст при посадке (недель) *</label>
          <input className="input mono" type="number" value={ageWeeks} onChange={(e) => setAgeWeeks(e.target.value)} />
        </div>
        <div className="field">
          <label>Поголовье начальное *</label>
          <input className="input mono" type="number" value={initialHeads} onChange={(e) => setInitialHeads(e.target.value)} />
        </div>
        <div className="field">
          <label>Поголовье текущее</label>
          <input className="input mono" type="number" value={currentHeads} onChange={(e) => setCurrentHeads(e.target.value)} />
        </div>
        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>Технолог *</label>
          <select className="input" value={technologist} onChange={(e) => setTechnologist(e.target.value)}>
            <option value="">— выберите —</option>
            {people?.map((p) => (
              <option key={p.user} value={p.user}>
                {p.user_full_name} · {p.position_title || p.user_email}
              </option>
            ))}
          </select>
        </div>
        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>Заметка</label>
          <input className="input" value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>
      </div>
      {error && error.status !== 400 && (
        <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 12 }}>Ошибка: {error.message}</div>
      )}
    </Modal>
  );
}
