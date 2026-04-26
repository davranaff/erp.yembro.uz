'use client';

import { useState } from 'react';

import Modal from '@/components/ui/Modal';
import { ApiError } from '@/lib/api';
import { useCrystallizeEggs } from '@/hooks/useMatochnik';
import { useNomenclatureItems } from '@/hooks/useNomenclature';
import type { BreedingHerd } from '@/types/auth';

interface Props {
  herd: BreedingHerd;
  onClose: () => void;
}

export default function CrystallizeModal({ herd, onClose }: Props) {
  const { data: items } = useNomenclatureItems({ is_active: 'true' });
  const crystallize = useCrystallizeEggs();

  const [nom, setNom] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const error = crystallize.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, string[]>) ?? {})
    : {};

  const handleSubmit = async () => {
    try {
      await crystallize.mutateAsync({
        id: herd.id,
        body: { egg_nomenclature: nom, date_from: dateFrom, date_to: dateTo },
      });
      onClose();
    } catch { /* */ }
  };

  return (
    <Modal
      title={`Собрать партию яиц · ${herd.doc_number}`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={!nom || !dateFrom || !dateTo || crystallize.isPending}
            onClick={handleSubmit}
          >
            {crystallize.isPending ? 'Обработка…' : 'Сформировать партию'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
        Соберёт все несвязанные суточные яйцесборы за период в одну партию для передачи в инкубацию.
      </div>
      <div className="field">
        <label>Номенклатура (яйцо) *</label>
        <select className="input" value={nom} onChange={(e) => setNom(e.target.value)}>
          <option value="">— выберите —</option>
          {items?.map((it) => (
            <option key={it.id} value={it.id}>
              {it.sku} · {it.name}
            </option>
          ))}
        </select>
        {fieldErrors.egg_nomenclature && (
          <div style={{ fontSize: 11, color: 'var(--danger)' }}>{fieldErrors.egg_nomenclature.join(' · ')}</div>
        )}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>Дата с *</label>
          <input className="input" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </div>
        <div className="field">
          <label>Дата по *</label>
          <input className="input" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </div>
      </div>
      {(fieldErrors.records || fieldErrors.__all__) && (
        <div style={{ fontSize: 11, color: 'var(--danger)' }}>
          {(fieldErrors.records ?? fieldErrors.__all__).join(' · ')}
        </div>
      )}
      {error && error.status !== 400 && (
        <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 12 }}>Ошибка: {error.message}</div>
      )}
    </Modal>
  );
}
