'use client';

import { useEffect, useState } from 'react';

import HelpHint from '@/components/ui/HelpHint';
import Modal from '@/components/ui/Modal';
import { ApiError } from '@/lib/api';
import {
  useCategories,
  useCreateCategory,
  useCreateItem,
  useCreateUnit,
  useUnits,
  useUpdateItem,
} from '@/hooks/useNomenclature';
import type { NomenclatureItem } from '@/types/auth';

interface Props {
  initial?: NomenclatureItem | null;
  onClose: () => void;
  onSaved?: (item: NomenclatureItem) => void;
}

export default function NomenclatureModal({ initial, onClose, onSaved }: Props) {
  const { data: categories } = useCategories();
  const { data: units } = useUnits();

  const create = useCreateItem();
  const update = useUpdateItem();
  const createUnit = useCreateUnit();
  const createCategory = useCreateCategory();

  const saving = create.isPending || update.isPending;
  const error = (initial ? update.error : create.error) ?? null;
  const isEdit = !!initial;

  const [sku, setSku] = useState(initial?.sku ?? '');
  const [name, setName] = useState(initial?.name ?? '');
  const [category, setCategory] = useState(initial?.category ?? '');
  const [unit, setUnit] = useState(initial?.unit ?? '');
  const [barcode, setBarcode] = useState(initial?.barcode ?? '');
  const [isActive, setIsActive] = useState(initial?.is_active ?? true);
  const [notes, setNotes] = useState(initial?.notes ?? '');
  const [baseMoisture, setBaseMoisture] = useState(initial?.base_moisture_pct ?? '');

  // quick-create
  const [newCatName, setNewCatName] = useState('');
  const [newUnitCode, setNewUnitCode] = useState('');
  const [newUnitName, setNewUnitName] = useState('');

  useEffect(() => {
    if (!initial) return;
    setSku(initial.sku);
    setName(initial.name);
    setCategory(initial.category);
    setUnit(initial.unit);
    setBarcode(initial.barcode ?? '');
    setIsActive(initial.is_active);
    setNotes(initial.notes ?? '');
    setBaseMoisture(initial.base_moisture_pct ?? '');
  }, [initial]);

  const fieldErrors =
    error instanceof ApiError && error.status === 400
      ? ((error.data as Record<string, string[]>) ?? {})
      : {};

  const handleSave = async () => {
    const payload = {
      sku,
      name,
      category,
      unit,
      barcode,
      is_active: isActive,
      notes,
      base_moisture_pct: baseMoisture || null,
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
      /* ошибка через fieldErrors */
    }
  };

  const handleQuickCreateCategory = async () => {
    const n = newCatName.trim();
    if (!n) return;
    try {
      const cat = await createCategory.mutateAsync({ name: n });
      setCategory(cat.id);
      setNewCatName('');
    } catch (err) {
      alert(err instanceof ApiError ? err.message : 'Ошибка создания категории');
    }
  };

  const handleQuickCreateUnit = async () => {
    const code = newUnitCode.trim();
    const nm = newUnitName.trim() || code;
    if (!code) return;
    try {
      const u = await createUnit.mutateAsync({ code, name: nm });
      setUnit(u.id);
      setNewUnitCode('');
      setNewUnitName('');
    } catch (err) {
      alert(err instanceof ApiError ? err.message : 'Ошибка создания единицы');
    }
  };

  return (
    <Modal
      title={isEdit ? `Редактирование · ${initial?.name}` : 'Новая позиция'}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>
            Отмена
          </button>
          <button
            className="btn btn-primary"
            disabled={saving || !sku || !name || !category || !unit}
            onClick={handleSave}
          >
            {saving ? 'Сохранение…' : 'Сохранить'}
          </button>
        </>
      }
    >
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>Артикул (SKU) *</label>
          <input
            className="input mono"
            value={sku}
            onChange={(e) => setSku(e.target.value)}
            disabled={isEdit}
            placeholder="КМ-Ст-01"
          />
          {fieldErrors.sku && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>
              {fieldErrors.sku.join(' · ')}
            </div>
          )}
        </div>
        <div className="field">
          <label>Штрих-код</label>
          <input
            className="input mono"
            value={barcode}
            onChange={(e) => setBarcode(e.target.value)}
          />
        </div>
        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>Наименование *</label>
          <input
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          {fieldErrors.name && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>
              {fieldErrors.name.join(' · ')}
            </div>
          )}
        </div>

        <div className="field">
          <label>Категория *</label>
          <select
            className="input"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            <option value="">— выберите —</option>
            {categories?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <div style={{ display: 'flex', gap: 4, marginTop: 4 }}>
            <input
              className="input"
              placeholder="Новая категория…"
              value={newCatName}
              onChange={(e) => setNewCatName(e.target.value)}
              style={{ flex: 1, fontSize: 12, height: 26 }}
            />
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={handleQuickCreateCategory}
              disabled={!newCatName.trim() || createCategory.isPending}
            >
              +
            </button>
          </div>
        </div>

        <div className="field">
          <label>Ед. измерения *</label>
          <select
            className="input"
            value={unit}
            onChange={(e) => setUnit(e.target.value)}
          >
            <option value="">— выберите —</option>
            {units?.map((u) => (
              <option key={u.id} value={u.id}>
                {u.code} · {u.name}
              </option>
            ))}
          </select>
          <div style={{ display: 'flex', gap: 4, marginTop: 4 }}>
            <input
              className="input mono"
              placeholder="код"
              value={newUnitCode}
              onChange={(e) => setNewUnitCode(e.target.value)}
              style={{ width: 70, fontSize: 12, height: 26 }}
            />
            <input
              className="input"
              placeholder="название"
              value={newUnitName}
              onChange={(e) => setNewUnitName(e.target.value)}
              style={{ flex: 1, fontSize: 12, height: 26 }}
            />
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={handleQuickCreateUnit}
              disabled={!newUnitCode.trim() || createUnit.isPending}
            >
              +
            </button>
          </div>
        </div>

        <div className="field">
          <label>Статус</label>
          <select
            className="input"
            value={isActive ? '1' : '0'}
            onChange={(e) => setIsActive(e.target.value === '1')}
          >
            <option value="1">Активна</option>
            <option value="0">Архивная</option>
          </select>
        </div>

        <div className="field">
          <label>
            Базисная влажность, %
            <HelpHint
              text="Опционально — для сырья, где важен учёт усушки."
              details={
                'Базисная влажность по ГОСТ 13586.5: 14% для пшеницы и кукурузы, '
                + '12% для шрота, 10% для премикса. При приёмке партии сырья '
                + 'фактическая влажность сравнивается с этой и считается зачётный '
                + 'вес по формуле Дюваля: Хв = 100×(A−B)/(100−B). '
                + 'Если поле пустое — учёт усушки для этого SKU не применяется.'
              }
            />
          </label>
          <input
            className="input mono"
            type="number"
            step="0.01"
            value={baseMoisture}
            onChange={(e) => setBaseMoisture(e.target.value)}
            placeholder="14.00"
          />
        </div>

        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>Примечание</label>
          <input
            className="input"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
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
