'use client';

import { useState } from 'react';

import HelpHint from '@/components/ui/HelpHint';
import Modal from '@/components/ui/Modal';
import { ApiError } from '@/lib/api';
import { recipesCrud } from '@/hooks/useFeed';
import type { Recipe } from '@/types/auth';

interface Props {
  initial?: Recipe | null;
  onClose: () => void;
}

export default function RecipeModal({ initial, onClose }: Props) {
  const isEdit = !!initial;
  const create = recipesCrud.useCreate();
  const update = recipesCrud.useUpdate();
  const error = (isEdit ? update.error : create.error) ?? null;

  const [code, setCode] = useState(initial?.code ?? '');
  const [name, setName] = useState(initial?.name ?? '');
  const [direction, setDirection] = useState(initial?.direction ?? 'broiler');
  const [ageRange, setAgeRange] = useState(initial?.age_range ?? '');
  const [isMedicated, setIsMedicated] = useState(initial?.is_medicated ?? false);
  const [isActive, setIsActive] = useState(initial?.is_active ?? true);
  const [notes, setNotes] = useState(initial?.notes ?? '');

  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, string[]>) ?? {})
    : {};

  const handleSave = async () => {
    const payload = { code, name, direction, age_range: ageRange, is_medicated: isMedicated, is_active: isActive, notes };
    try {
      if (isEdit && initial) await update.mutateAsync({ id: initial.id, patch: payload });
      else await create.mutateAsync(payload);
      onClose();
    } catch { /* */ }
  };

  return (
    <Modal
      title={isEdit ? `Рецептура · ${initial?.code}` : 'Новая рецептура'}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={!code || !name || create.isPending || update.isPending}
            onClick={handleSave}
          >
            {create.isPending || update.isPending ? 'Сохранение…' : 'Сохранить'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 11, color: 'var(--fg-3)', marginBottom: 10 }}>
        Рецептура — это «чертёж» комбикорма. После создания добавьте к ней
        версию с компонентами — на основе версии будут делаться задания.
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>
            Код *
            <HelpHint
              text="Короткий идентификатор рецепта."
              details="Например «Р-БР-СТ» (старт бройлера) или «Р-НЕС-ПК» (несушка пик). Используется в документах и отчётах."
            />
          </label>
          <input className="input mono" value={code} onChange={(e) => setCode(e.target.value)} disabled={isEdit} placeholder="Р-БР-СТ" />
          {fieldErrors.code && <div style={{ fontSize: 11, color: 'var(--danger)' }}>{fieldErrors.code.join(' · ')}</div>}
        </div>
        <div className="field">
          <label>Название *</label>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Старт бройлера 0–14 дн" />
        </div>
        <div className="field">
          <label>
            Направление
            <HelpHint
              text="Тип птицы для которой корм."
              details="Бройлер — мясная птица на откорм. Несушка — птица на яйцо. Родительское — племенное стадо. От направления зависят целевые показатели и норма кормления."
            />
          </label>
          <select className="input" value={direction} onChange={(e) => setDirection(e.target.value)}>
            <option value="broiler">Бройлер</option>
            <option value="layer">Несушка</option>
            <option value="parent">Родительское</option>
          </select>
        </div>
        <div className="field">
          <label>
            Возраст
            <HelpHint
              text="Возрастной интервал птицы."
              details="Например «0–14 дн» (старт), «15–28 дн» (рост), «29+ дн» (финиш). У бройлеров 3–4 разных корма по возрастам, у несушки — стадии «молодка» / «пик» / «спад»."
            />
          </label>
          <input className="input" value={ageRange} onChange={(e) => setAgeRange(e.target.value)} placeholder="0–14 дн" />
        </div>
        <label style={{ display: 'flex', gap: 6, alignItems: 'center', fontSize: 12 }}>
          <input type="checkbox" checked={isMedicated} onChange={(e) => setIsMedicated(e.target.checked)} />
          Медикаментозная
          <HelpHint
            text="Содержит лекарство."
            details="Если рецепт включает антибиотик/кокцидиостат — все партии этой рецептуры наследуют флаг и требуют каренции перед убоем."
          />
        </label>
        <label style={{ display: 'flex', gap: 6, alignItems: 'center', fontSize: 12 }}>
          <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
          Активна
        </label>
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
