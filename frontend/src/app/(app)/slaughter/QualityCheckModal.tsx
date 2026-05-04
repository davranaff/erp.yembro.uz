'use client';

import { useState } from 'react';

import HelpHint from '@/components/ui/HelpHint';
import Modal from '@/components/ui/Modal';
import { useUser } from '@/hooks/useUser';
import { qualityChecksCrud } from '@/hooks/useSlaughter';
import { ApiError } from '@/lib/api';
import type { SlaughterQualityCheck, SlaughterShift } from '@/types/auth';

interface Props {
  shift: SlaughterShift;
  qc?: SlaughterQualityCheck | null;
  onClose: () => void;
}

export default function QualityCheckModal({ shift, qc, onClose }: Props) {
  const create = qualityChecksCrud.useCreate();
  const update = qualityChecksCrud.useUpdate();
  const { data: user } = useUser();

  const [defectPct, setDefectPct] = useState(qc?.carcass_defect_percent ?? '');
  const [traumaPct, setTraumaPct] = useState(qc?.trauma_percent ?? '');
  const [tempC, setTempC] = useState(qc?.cooling_temperature_c ?? '');
  const [vetPassed, setVetPassed] = useState(qc?.vet_inspection_passed ?? false);
  const [notes, setNotes] = useState(qc?.notes ?? '');

  const isEdit = Boolean(qc);
  const action = isEdit ? update : create;
  const error = action.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, string[] | string>) ?? {})
    : {};

  const submit = async () => {
    const body = {
      shift: shift.id,
      carcass_defect_percent: defectPct || null,
      trauma_percent: traumaPct || null,
      cooling_temperature_c: tempC || null,
      vet_inspection_passed: vetPassed,
      inspector: user?.id ?? '',
      inspected_at: new Date().toISOString(),
      notes,
    };
    try {
      if (isEdit && qc) {
        await update.mutateAsync({ id: qc.id, body } as never);
      } else {
        await create.mutateAsync(body as never);
      }
      onClose();
    } catch { /* */ }
  };

  return (
    <Modal
      title={isEdit ? 'Редактировать контроль качества' : 'Контроль качества смены'}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={action.isPending || !user?.id}
            onClick={submit}
          >
            {action.isPending ? 'Сохранение…' : isEdit ? 'Сохранить' : 'Записать'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
        Без отметки <strong>«Ветеринарная инспекция пройдена»</strong> провести смену
        невозможно. <HelpHint
          text="Ветеринарный контроль обязателен по СанПиН для пищевой продукции животного происхождения. Дефекты тушки до 1.5% — нормально."
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>Дефект тушки, %</label>
          <input
            className="input mono"
            type="number" step="0.01"
            value={defectPct}
            onChange={(e) => setDefectPct(e.target.value)}
          />
        </div>
        <div className="field">
          <label>Травмы, %</label>
          <input
            className="input mono"
            type="number" step="0.01"
            value={traumaPct}
            onChange={(e) => setTraumaPct(e.target.value)}
          />
        </div>
        <div className="field">
          <label>Темп. охлажд., °C</label>
          <input
            className="input mono"
            type="number" step="0.1"
            value={tempC}
            onChange={(e) => setTempC(e.target.value)}
          />
        </div>
      </div>

      <label style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 0', cursor: 'pointer' }}>
        <input
          type="checkbox"
          checked={vetPassed}
          onChange={(e) => setVetPassed(e.target.checked)}
        />
        <strong>Ветеринарная инспекция пройдена</strong>
      </label>

      <div className="field">
        <label>Заметка</label>
        <textarea
          className="input"
          rows={2}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </div>

      {fieldErrors.shift && (
        <div style={{ fontSize: 12, color: 'var(--danger)' }}>
          {Array.isArray(fieldErrors.shift)
            ? fieldErrors.shift.join(' · ')
            : String(fieldErrors.shift)}
        </div>
      )}
      {error && error.status !== 400 && (
        <div style={{ fontSize: 12, color: 'var(--danger)' }}>Ошибка: {error.message}</div>
      )}
    </Modal>
  );
}
