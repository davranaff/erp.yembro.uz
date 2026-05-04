'use client';

import { useState } from 'react';

import BatchSelector from '@/components/BatchSelector';
import Modal from '@/components/ui/Modal';
import { ApiError } from '@/lib/api';
import { useProductionBlocks } from '@/hooks/useBlocks';
import { usePlaceFeedlotBatch } from '@/hooks/useFeedlot';
import { useModules } from '@/hooks/useModules';
import { usePeople } from '@/hooks/usePeople';

interface Props {
  onClose: () => void;
}

/**
 * Размещение Batch (цыплят) в Feedlot-партию.
 * action: POST /api/feedlot/batches/place/
 */
export default function PlaceModal({ onClose }: Props) {
  const { data: modules } = useModules();
  const { data: houses } = useProductionBlocks({ kind: 'feedlot' });
  const { data: people } = usePeople({ is_active: 'true' });
  const place = usePlaceFeedlotBatch();

  const feedlotModuleId = modules?.find((m) => m.code === 'feedlot')?.id ?? '';

  const [batchId, setBatchId] = useState('');
  const [house, setHouse] = useState('');
  const [placedDate, setPlacedDate] = useState(new Date().toISOString().slice(0, 10));
  const [tech, setTech] = useState('');
  const [initialHeads, setInitialHeads] = useState('');
  const [targetWeight, setTargetWeight] = useState('2.5');
  const [targetSlaughter, setTargetSlaughter] = useState('');
  const [docNumber, setDocNumber] = useState('');
  const [notes, setNotes] = useState('');

  const error = place.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, string[]>) ?? {})
    : {};

  const handleSubmit = async () => {
    try {
      await place.mutateAsync({
        batch: batchId,
        house_block: house,
        placed_date: placedDate,
        technologist: tech,
        initial_heads: initialHeads ? Number(initialHeads) : undefined,
        target_weight_kg: targetWeight || undefined,
        target_slaughter_date: targetSlaughter || undefined,
        doc_number: docNumber || undefined,
        notes,
      });
      onClose();
    } catch { /* */ }
  };

  return (
    <Modal
      title="Разместить партию на откорме"
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={!batchId || !house || !tech || place.isPending}
            onClick={handleSubmit}
          >
            {place.isPending ? 'Размещение…' : 'Разместить'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
        Создаёт FeedlotBatch для уже существующей Batch (цыплят), пришедшей из инкубации.
        Партия должна быть в модуле <span className="mono">feedlot</span> (после accept_transfer).
      </div>

      <BatchSelector
        label="Партия цыплят *"
        value={batchId}
        onChange={(id) => setBatchId(id)}
        filter={feedlotModuleId ? { state: 'active', current_module: feedlotModuleId } : { state: 'active' }}
      />
      {fieldErrors.batch && <div style={{ fontSize: 11, color: 'var(--danger)' }}>{fieldErrors.batch.join(' · ')}</div>}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>Птичник *</label>
          <select className="input" value={house} onChange={(e) => setHouse(e.target.value)}>
            <option value="">—</option>
            {houses?.map((b) => <option key={b.id} value={b.id}>{b.code} · {b.name}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Дата посадки *</label>
          <input className="input" type="date" value={placedDate} onChange={(e) => setPlacedDate(e.target.value)} />
        </div>
        <div className="field">
          <label>Поголовье (опц.)</label>
          <input
            className="input mono"
            type="number"
            value={initialHeads}
            onChange={(e) => setInitialHeads(e.target.value)}
            placeholder="по умолчанию = current_quantity"
          />
        </div>
        <div className="field">
          <label>Целевой вес, кг</label>
          <input
            className="input mono"
            type="number"
            step="0.001"
            value={targetWeight}
            onChange={(e) => setTargetWeight(e.target.value)}
          />
        </div>
        <div className="field">
          <label>Целевой съём (дата)</label>
          <input
            className="input"
            type="date"
            value={targetSlaughter}
            onChange={(e) => setTargetSlaughter(e.target.value)}
          />
        </div>
        <div className="field">
          <label>№ документа (опц.)</label>
          <input
            className="input mono"
            value={docNumber}
            onChange={(e) => setDocNumber(e.target.value)}
            placeholder="авто, если пусто"
          />
        </div>
        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>Технолог *</label>
          <select className="input" value={tech} onChange={(e) => setTech(e.target.value)}>
            <option value="">—</option>
            {people?.map((p) => (
              <option key={p.user} value={p.user}>{p.user_full_name} · {p.position_title || p.user_email}</option>
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
