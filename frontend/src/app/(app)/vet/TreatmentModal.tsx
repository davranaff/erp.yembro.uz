'use client';

import { useMemo, useState } from 'react';

import BatchSelector from '@/components/BatchSelector';
import Modal from '@/components/ui/Modal';
import { ApiError } from '@/lib/api';
import { useProductionBlocks } from '@/hooks/useBlocks';
import { useModules } from '@/hooks/useModules';
import { useUnits } from '@/hooks/useNomenclature';
import { usePeople } from '@/hooks/usePeople';
import {
  drugsCrud,
  stockBatchesCrud,
  treatmentsCrud,
  useApplyTreatment,
} from '@/hooks/useVet';

interface Props {
  onClose: () => void;
}

const ROUTE_OPTIONS = [
  { value: '', label: 'По карточке препарата' },
  { value: 'injection', label: 'Инъекция' },
  { value: 'oral', label: 'Перорально' },
  { value: 'drinking_water', label: 'С водой' },
  { value: 'spray', label: 'Спрей' },
  { value: 'other', label: 'Другое' },
];

const INDICATION_OPTIONS = [
  { value: 'routine', label: 'Плановая обработка' },
  { value: 'prophylaxis', label: 'Профилактика' },
  { value: 'therapy', label: 'Лечение' },
  { value: 'emergency', label: 'Экстренная' },
];

/**
 * Двухшаговая операция:
 *   1. POST /api/vet/treatments/  — создаёт TreatmentLog (DRAFT)
 *   2. POST /api/vet/treatments/{id}/apply/  — декремент лота + JE + withdrawal_period_ends
 *
 * Форма принуждает выбрать ровно один target: партия ИЛИ стадо (XOR).
 */
export default function TreatmentModal({ onClose }: Props) {
  const create = treatmentsCrud.useCreate();
  const apply = useApplyTreatment();

  const { data: modules } = useModules();
  const { data: drugs } = drugsCrud.useList({ is_active: 'true' });
  const { data: stockBatches } = stockBatchesCrud.useList({ status: 'available' });
  const { data: blocks } = useProductionBlocks();
  const { data: units } = useUnits();
  const { data: people } = usePeople({ is_active: 'true' });

  const vetModuleId = modules?.find((m) => m.code === 'vet')?.id ?? '';

  const [docNumber, setDocNumber] = useState('');
  const [treatmentDate, setTreatmentDate] = useState(new Date().toISOString().slice(0, 10));
  const [targetBlock, setTargetBlock] = useState('');
  const [targetType, setTargetType] = useState<'batch' | 'herd'>('batch');
  const [targetBatch, setTargetBatch] = useState('');
  const [targetHerd, setTargetHerd] = useState('');
  const [drug, setDrug] = useState('');
  const [stockBatch, setStockBatch] = useState('');
  const [doseQty, setDoseQty] = useState('');
  const [unit, setUnit] = useState('');
  const [headsTreated, setHeadsTreated] = useState('');
  const [withdrawalDays, setWithdrawalDays] = useState('');
  const [route, setRoute] = useState<string>('');
  const [vet, setVet] = useState('');
  const [indication, setIndication] = useState('routine');
  const [notes, setNotes] = useState('');

  // Авто-фильтр лотов под выбранный препарат
  const filteredLots = useMemo(
    () => (stockBatches ?? []).filter((s) => !drug || s.drug === drug),
    [stockBatches, drug],
  );

  const error = create.error ?? apply.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, string[]>) ?? {})
    : {};

  const handleSubmit = async () => {
    if (!vetModuleId) { alert('Модуль vet не найден'); return; }
    if ((targetType === 'batch' && !targetBatch) || (targetType === 'herd' && !targetHerd)) {
      alert('Укажите цель: партия ИЛИ стадо');
      return;
    }
    try {
      const created = await create.mutateAsync({
        doc_number: docNumber,
        module: vetModuleId,
        treatment_date: treatmentDate,
        target_block: targetBlock,
        target_batch: targetType === 'batch' ? targetBatch : null,
        target_herd: targetType === 'herd' ? targetHerd : null,
        drug,
        stock_batch: stockBatch,
        dose_quantity: doseQty,
        unit,
        heads_treated: Number(headsTreated),
        withdrawal_period_days: Number(withdrawalDays || 0),
        administration_route: route || null,
        veterinarian: vet,
        indication,
        notes,
      } as never);
      // 2-й шаг — провести
      if (created?.id) {
        await apply.mutateAsync({ id: created.id });
      }
      onClose();
    } catch { /* */ }
  };

  return (
    <Modal
      title="Назначить лечение / вакцинацию"
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={create.isPending || apply.isPending || !docNumber || !targetBlock || !drug || !stockBatch || !doseQty || !unit || !headsTreated || !vet}
            onClick={handleSubmit}
          >
            {create.isPending || apply.isPending ? 'Применение…' : 'Создать и применить'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
        2 шага: создаст TreatmentLog → POST <span className="mono">/apply/</span> (декремент лота + withdrawal_period_ends на партии).
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>Документ *</label>
          <input className="input mono" value={docNumber} onChange={(e) => setDocNumber(e.target.value)} placeholder="ВЛ-2026-001" />
          {fieldErrors.doc_number && <div style={{ fontSize: 11, color: 'var(--danger)' }}>{fieldErrors.doc_number.join(' · ')}</div>}
        </div>
        <div className="field">
          <label>Дата *</label>
          <input className="input" type="date" value={treatmentDate} onChange={(e) => setTreatmentDate(e.target.value)} />
        </div>

        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>Блок назначения *</label>
          <select className="input" value={targetBlock} onChange={(e) => setTargetBlock(e.target.value)}>
            <option value="">—</option>
            {blocks?.map((b) => <option key={b.id} value={b.id}>{b.code} · {b.name}</option>)}
          </select>
        </div>

        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>Цель (XOR) *</label>
          <div style={{ display: 'flex', gap: 12, marginBottom: 6 }}>
            <label style={{ display: 'flex', gap: 4, alignItems: 'center', fontSize: 12 }}>
              <input type="radio" name="target" checked={targetType === 'batch'} onChange={() => setTargetType('batch')} />
              Партия (откорм/инкубация)
            </label>
            <label style={{ display: 'flex', gap: 4, alignItems: 'center', fontSize: 12 }}>
              <input type="radio" name="target" checked={targetType === 'herd'} onChange={() => setTargetType('herd')} />
              Стадо (маточник)
            </label>
          </div>
          {targetType === 'batch' ? (
            <BatchSelector
              label=""
              value={targetBatch}
              onChange={(id) => setTargetBatch(id)}
              filter={{ state: 'active' }}
            />
          ) : (
            <input
              className="input mono"
              value={targetHerd}
              onChange={(e) => setTargetHerd(e.target.value)}
              placeholder="UUID стада из /api/matochnik/herds/"
            />
          )}
        </div>

        <div className="field">
          <label>Препарат *</label>
          <select
            className="input"
            value={drug}
            onChange={(e) => { setDrug(e.target.value); setStockBatch(''); }}
          >
            <option value="">—</option>
            {drugs?.map((d) => (
              <option key={d.id} value={d.id}>
                {d.nomenclature_sku} · {d.nomenclature_name}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Лот (доступный) *</label>
          <select
            className="input"
            value={stockBatch}
            onChange={(e) => {
              setStockBatch(e.target.value);
              const lot = filteredLots.find((l) => l.id === e.target.value);
              if (lot && !unit) setUnit(lot.unit);
            }}
            disabled={!drug}
          >
            <option value="">—</option>
            {filteredLots.map((s) => (
              <option key={s.id} value={s.id}>
                {s.lot_number} (остаток {parseFloat(s.current_quantity)} {s.unit_code ?? ''})
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label>Доза *</label>
          <input
            className="input mono"
            type="number"
            step="0.0001"
            value={doseQty}
            onChange={(e) => setDoseQty(e.target.value)}
          />
        </div>
        <div className="field">
          <label>Ед. *</label>
          <select className="input" value={unit} onChange={(e) => setUnit(e.target.value)}>
            <option value="">—</option>
            {units?.map((u) => <option key={u.id} value={u.id}>{u.code} · {u.name}</option>)}
          </select>
        </div>

        <div className="field">
          <label>Голов *</label>
          <input
            className="input mono"
            type="number"
            value={headsTreated}
            onChange={(e) => setHeadsTreated(e.target.value)}
          />
        </div>
        <div className="field">
          <label>Каренция, дн</label>
          <input
            className="input mono"
            type="number"
            value={withdrawalDays}
            onChange={(e) => setWithdrawalDays(e.target.value)}
            placeholder="0 = без"
          />
        </div>

        <div className="field">
          <label>Путь введения</label>
          <select className="input" value={route} onChange={(e) => setRoute(e.target.value)}>
            {ROUTE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Показание</label>
          <select className="input" value={indication} onChange={(e) => setIndication(e.target.value)}>
            {INDICATION_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>

        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>Ветврач *</label>
          <select className="input" value={vet} onChange={(e) => setVet(e.target.value)}>
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
