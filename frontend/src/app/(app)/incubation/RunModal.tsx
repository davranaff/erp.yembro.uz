'use client';

import { useState } from 'react';

import BatchSelector from '@/components/BatchSelector';
import Modal from '@/components/ui/Modal';
import SmartSelect from '@/components/ui/SmartSelect';
import { ApiError } from '@/lib/api';
import { useProductionBlocks } from '@/hooks/useBlocks';
import { runsCrud } from '@/hooks/useIncubation';
import { useModules } from '@/hooks/useModules';
import { usePeople } from '@/hooks/usePeople';
import type { Batch } from '@/types/auth';

interface Props {
  onClose: () => void;
}

/**
 * Создание новой партии инкубации. Требует уже созданную Batch яиц
 * (обычно через crystallize-eggs в /matochnik). Поле batch — UUID.
 */
export default function RunModal({ onClose }: Props) {
  const { data: modules } = useModules();
  const { data: incubators } = useProductionBlocks({ kind: 'incubation' });
  const { data: people } = usePeople({ is_active: 'true' });
  const create = runsCrud.useCreate();

  const incubationModuleId = modules?.find((m) => m.code === 'incubation')?.id ?? '';

  const [incubatorBlock, setIncubatorBlock] = useState('');
  const [batchId, setBatchId] = useState('');
  const [loadedDate, setLoadedDate] = useState(new Date().toISOString().slice(0, 10));
  const [expectedHatchDate, setExpectedHatchDate] = useState('');
  const [eggsLoaded, setEggsLoaded] = useState('');
  const [daysTotal, setDaysTotal] = useState('21');
  const [technologist, setTechnologist] = useState('');
  const [notes, setNotes] = useState('');

  const error = create.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, string[]>) ?? {})
    : {};

  const handleSave = async () => {
    if (!incubationModuleId) { alert('Модуль incubation не найден'); return; }
    try {
      await create.mutateAsync({
        module: incubationModuleId,
        incubator_block: incubatorBlock,
        batch: batchId,
        loaded_date: loadedDate,
        expected_hatch_date: expectedHatchDate,
        eggs_loaded: Number(eggsLoaded),
        days_total: Number(daysTotal),
        technologist,
        notes,
      });
      onClose();
    } catch { /* */ }
  };

  return (
    <Modal
      title="Новая партия инкубации"
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={create.isPending || !incubatorBlock || !batchId || !eggsLoaded || !technologist || !expectedHatchDate}
            onClick={handleSave}
          >
            {create.isPending ? 'Сохранение…' : 'Загрузить партию'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 11, color: 'var(--fg-3)', marginBottom: 12, padding: 8, background: 'var(--bg-soft)', borderRadius: 4 }}>
        Партия яиц должна быть уже передана в модуль <b>incubation</b> (из маточника
        кнопкой «→ В инкубацию»). Здесь вы закладываете её в конкретный инкубационный шкаф.
      </div>

      <BatchSelector
        label="Партия яиц (в модуле incubation) *"
        value={batchId}
        onChange={(id, batch?: Batch) => {
          setBatchId(id);
          if (batch && !eggsLoaded) {
            setEggsLoaded(String(Math.floor(parseFloat(batch.current_quantity || '0'))));
          }
        }}
        filter={
          incubationModuleId
            ? { state: 'active', current_module: incubationModuleId }
            : { state: 'active' }
        }
        placeholder="— выберите партию яиц, прибывшую в инкубацию —"
      />
      {fieldErrors.batch && <div style={{ fontSize: 11, color: 'var(--danger)' }}>{fieldErrors.batch.join(' · ')}</div>}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>Инкубатор (шкаф) *</label>
          <SmartSelect
            value={incubatorBlock}
            onChange={setIncubatorBlock}
            options={incubators?.map((b) => ({
              value: b.id,
              label: b.name,
              sublabel: b.code,
            })) ?? []}
            placeholder="— выберите шкаф —"
            searchPlaceholder="Поиск шкафа…"
            emptyText="Шкафов нет"
          />
        </div>
        <div className="field">
          <label>Дата загрузки *</label>
          <input className="input" type="date" value={loadedDate} onChange={(e) => setLoadedDate(e.target.value)} />
        </div>
        <div className="field">
          <label>Ожидаемый вывод *</label>
          <input className="input" type="date" value={expectedHatchDate} onChange={(e) => setExpectedHatchDate(e.target.value)} />
        </div>
        <div className="field">
          <label>Яиц загружено *</label>
          <input className="input mono" type="number" value={eggsLoaded} onChange={(e) => setEggsLoaded(e.target.value)} />
        </div>
        <div className="field">
          <label>Всего дней</label>
          <input className="input mono" type="number" value={daysTotal} onChange={(e) => setDaysTotal(e.target.value)} />
        </div>
        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>Технолог *</label>
          <SmartSelect
            value={technologist}
            onChange={setTechnologist}
            options={people?.map((p) => ({
              value: p.user,
              label: p.user_full_name,
              sublabel: p.position_title || p.user_email,
            })) ?? []}
            placeholder="— выберите технолога —"
            searchPlaceholder="Поиск по ФИО или должности…"
          />
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
