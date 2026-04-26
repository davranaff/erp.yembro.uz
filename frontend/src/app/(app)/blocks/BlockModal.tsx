'use client';

import { useEffect, useState } from 'react';

import Modal from '@/components/ui/Modal';
import { ApiError } from '@/lib/api';
import { useCreateBlock, useUpdateBlock } from '@/hooks/useBlocks';
import { useModules } from '@/hooks/useModules';
import { useUnits } from '@/hooks/useNomenclature';
import type { BlockKind, ProductionBlock } from '@/types/auth';

const KIND_OPTIONS: { value: BlockKind; label: string }[] = [
  { value: 'matochnik',      label: 'Корпус маточника' },
  { value: 'incubation',     label: 'Инкубационный шкаф' },
  { value: 'hatcher',        label: 'Выводной шкаф' },
  { value: 'feedlot',        label: 'Птичник откорма' },
  { value: 'slaughter_line', label: 'Линия разделки' },
  { value: 'warehouse',      label: 'Склад' },
  { value: 'vet_storage',    label: 'Склад ветпрепаратов' },
  { value: 'mixer_line',     label: 'Линия замеса' },
  { value: 'storage_bin',    label: 'Бункер / ёмкость' },
  { value: 'other',          label: 'Прочее' },
];

interface Props {
  initial?: ProductionBlock | null;
  onClose: () => void;
  onSaved?: (b: ProductionBlock) => void;
}

export default function BlockModal({ initial, onClose, onSaved }: Props) {
  const { data: modules } = useModules();
  const { data: units } = useUnits();
  const create = useCreateBlock();
  const update = useUpdateBlock();
  const saving = create.isPending || update.isPending;
  const error = (initial ? update.error : create.error) ?? null;
  const isEdit = !!initial;

  const [code, setCode] = useState(initial?.code ?? '');
  const [name, setName] = useState(initial?.name ?? '');
  const [moduleId, setModuleId] = useState(initial?.module ?? '');
  const [kind, setKind] = useState<BlockKind>(initial?.kind ?? 'feedlot');
  const [area, setArea] = useState(initial?.area_m2 ?? '');
  const [capacity, setCapacity] = useState(initial?.capacity ?? '');
  const [capacityUnit, setCapacityUnit] = useState(initial?.capacity_unit ?? '');
  const [isActive, setIsActive] = useState(initial?.is_active ?? true);

  useEffect(() => {
    if (!initial) return;
    setCode(initial.code);
    setName(initial.name);
    setModuleId(initial.module);
    setKind(initial.kind);
    setArea(initial.area_m2 ?? '');
    setCapacity(initial.capacity ?? '');
    setCapacityUnit(initial.capacity_unit ?? '');
    setIsActive(initial.is_active);
  }, [initial]);

  const fieldErrors =
    error instanceof ApiError && error.status === 400
      ? ((error.data as Record<string, string[]>) ?? {})
      : {};

  const handleSave = async () => {
    const payload = {
      code,
      name,
      module: moduleId,
      kind,
      area_m2: area ? area : null,
      capacity: capacity ? capacity : null,
      capacity_unit: capacityUnit || null,
      is_active: isActive,
    };
    try {
      if (isEdit && initial) {
        const res = await update.mutateAsync({ id: initial.id, patch: payload });
        onSaved?.(res);
      } else {
        const res = await create.mutateAsync(payload);
        onSaved?.(res);
      }
      onClose();
    } catch {
      /* */
    }
  };

  return (
    <Modal
      title={isEdit ? `Блок · ${initial?.code}` : 'Новый блок'}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>
            Отмена
          </button>
          <button
            className="btn btn-primary"
            disabled={saving || !code || !name || !moduleId}
            onClick={handleSave}
          >
            {saving ? 'Сохранение…' : 'Сохранить'}
          </button>
        </>
      }
    >
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>Код *</label>
          <input
            className="input mono"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            disabled={isEdit}
            placeholder="ПТ-А1"
          />
          {fieldErrors.code && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>
              {fieldErrors.code.join(' · ')}
            </div>
          )}
        </div>
        <div className="field">
          <label>Название *</label>
          <input
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div className="field">
          <label>Модуль *</label>
          <select
            className="input"
            value={moduleId}
            onChange={(e) => setModuleId(e.target.value)}
            disabled={isEdit}
          >
            <option value="">— выберите —</option>
            {modules?.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
          {fieldErrors.module && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>
              {fieldErrors.module.join(' · ')}
            </div>
          )}
        </div>
        <div className="field">
          <label>Тип *</label>
          <select
            className="input"
            value={kind}
            onChange={(e) => setKind(e.target.value as BlockKind)}
          >
            {KIND_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Площадь, м²</label>
          <input
            className="input mono"
            type="number"
            step="0.01"
            value={area}
            onChange={(e) => setArea(e.target.value)}
          />
        </div>
        <div className="field">
          <label>Ёмкость</label>
          <input
            className="input mono"
            type="number"
            step="0.001"
            value={capacity}
            onChange={(e) => setCapacity(e.target.value)}
          />
        </div>
        <div className="field">
          <label>Ед. ёмкости</label>
          <select
            className="input"
            value={capacityUnit}
            onChange={(e) => setCapacityUnit(e.target.value)}
          >
            <option value="">—</option>
            {units?.map((u) => (
              <option key={u.id} value={u.id}>
                {u.code} · {u.name}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Статус</label>
          <select
            className="input"
            value={isActive ? '1' : '0'}
            onChange={(e) => setIsActive(e.target.value === '1')}
          >
            <option value="1">Активен</option>
            <option value="0">Отключён</option>
          </select>
        </div>
      </div>

      {error && error.status !== 400 && (
        <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 12 }}>
          Ошибка: {error.message}
        </div>
      )}
    </Modal>
  );
}
