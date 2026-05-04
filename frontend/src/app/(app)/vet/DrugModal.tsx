'use client';

import { useMemo, useState } from 'react';

import HelpHint from '@/components/ui/HelpHint';
import Modal from '@/components/ui/Modal';
import { useModules } from '@/hooks/useModules';
import {
  useCategories,
  useCreateCategory,
  useCreateItem,
  useNomenclatureItems,
  useUnits,
} from '@/hooks/useNomenclature';
import { drugsCrud } from '@/hooks/useVet';
import { ApiError } from '@/lib/api';
import type { DrugRoute, DrugType, VetDrug } from '@/types/auth';

interface Props {
  initial?: VetDrug | null;
  onClose: () => void;
}

const DRUG_TYPES: Array<{ value: DrugType; label: string }> = [
  { value: 'vaccine', label: 'Вакцина' },
  { value: 'antibiotic', label: 'Антибиотик' },
  { value: 'vitamin', label: 'Витамин' },
  { value: 'electrolyte', label: 'Электролит' },
  { value: 'other', label: 'Прочее' },
];

const ROUTES: Array<{ value: DrugRoute; label: string }> = [
  { value: 'injection', label: 'Инъекция' },
  { value: 'oral', label: 'Оральное' },
  { value: 'drinking_water', label: 'С водой' },
  { value: 'spray', label: 'Спрей' },
  { value: 'other', label: 'Прочее' },
];

const VET_CATEGORY_NAME = 'Ветпрепараты';

/**
 * Создание/редактирование карточки ветпрепарата.
 *
 * Два режима:
 *   1. Выбрать существующую NomenclatureItem (SKU создан раньше).
 *   2. Создать новую NomenclatureItem прямо здесь — для удобства.
 */
export default function DrugModal({ initial, onClose }: Props) {
  const isEdit = Boolean(initial);
  const create = drugsCrud.useCreate();
  const update = drugsCrud.useUpdate();
  const createItem = useCreateItem();
  const createCategory = useCreateCategory();

  const { data: modules } = useModules();
  // Категории модуля vet (теперь скоупим по module_code, а не имени).
  const { data: vetCategories } = useCategories({ module_code: 'vet' });
  const { data: units } = useUnits();
  // SKU модуля vet
  const { data: items } = useNomenclatureItems({
    module_code: 'vet',
    is_active: 'true',
  });
  const vetCategory = useMemo(
    () => vetCategories?.[0] ?? null,
    [vetCategories],
  );

  const vetModuleId = modules?.find((m) => m.code === 'vet')?.id ?? '';

  const [mode, setMode] = useState<'pick' | 'create'>('pick');
  const [pickedNom, setPickedNom] = useState(initial?.nomenclature ?? '');

  // Поля новой номенклатуры
  const [newSku, setNewSku] = useState('');
  const [newName, setNewName] = useState('');
  const [newUnit, setNewUnit] = useState('');

  // Поля VetDrug
  const [drugType, setDrugType] = useState<DrugType>(initial?.drug_type ?? 'vaccine');
  const [route, setRoute] = useState<DrugRoute>(initial?.administration_route ?? 'oral');
  const [withdrawalDays, setWithdrawalDays] = useState(
    String(initial?.default_withdrawal_days ?? 0),
  );
  const [storage, setStorage] = useState(initial?.storage_conditions ?? '');
  const [notes, setNotes] = useState(initial?.notes ?? '');
  const [isActive, setIsActive] = useState(initial?.is_active ?? true);

  const action = isEdit ? update : create;
  const error = action.error || createItem.error || createCategory.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, unknown>) ?? {})
    : {};

  const isPickValid = mode === 'pick' && Boolean(pickedNom);
  const isCreateValid = mode === 'create' && Boolean(newSku && newName && newUnit);
  const canSubmit =
    !action.isPending && !createItem.isPending && !createCategory.isPending
    && (isEdit ? Boolean(pickedNom) : isPickValid || isCreateValid);

  const handleSubmit = async () => {
    if (!vetModuleId) {
      alert('Модуль vet не найден');
      return;
    }
    try {
      let nomenclatureId = pickedNom;

      // Режим «Создать новую SKU» — сначала создаём NomenclatureItem.
      if (!isEdit && mode === 'create') {
        // Гарантируем существование категории модуля vet (создаём с привязкой).
        let catId = vetCategory?.id;
        if (!catId) {
          const cat = await createCategory.mutateAsync({
            name: VET_CATEGORY_NAME,
            module: vetModuleId,
          });
          catId = cat.id;
        }
        const item = await createItem.mutateAsync({
          sku: newSku,
          name: newName,
          category: catId,
          unit: newUnit,
          is_active: true,
        });
        nomenclatureId = item.id;
      }

      const body = {
        module: vetModuleId,
        nomenclature: nomenclatureId,
        drug_type: drugType,
        administration_route: route,
        default_withdrawal_days: Number(withdrawalDays || 0),
        storage_conditions: storage,
        notes,
        is_active: isActive,
      };

      if (isEdit && initial) {
        await update.mutateAsync({ id: initial.id, patch: body } as never);
      } else {
        await create.mutateAsync(body as never);
      }
      onClose();
    } catch {
      /* fieldErrors показываются ниже */
    }
  };

  const renderFieldError = (key: string) => {
    const v = fieldErrors[key];
    if (!v) return null;
    const text = Array.isArray(v) ? v.join(' · ') : String(v);
    return <div style={{ fontSize: 11, color: 'var(--danger)' }}>{text}</div>;
  };

  return (
    <Modal
      title={isEdit ? 'Редактировать препарат' : 'Новый препарат'}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            onClick={handleSubmit}
            disabled={!canSubmit}
          >
            {action.isPending || createItem.isPending
              ? 'Сохранение…'
              : isEdit ? 'Сохранить' : 'Создать'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
        Препарат — это карточка с вет-специфичными параметрами поверх SKU
        номенклатуры.
        <HelpHint
          text="Зачем это нужно?"
          details="Один и тот же SKU может иметь много лотов на складе (разные сроки годности, поставщики). Карточка препарата хранит параметры применения: тип, путь введения, срок каренции по умолчанию."
        />
      </div>

      {!isEdit && (
        <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
          <button
            type="button"
            className={'btn btn-sm ' + (mode === 'pick' ? 'btn-primary' : 'btn-ghost')}
            onClick={() => setMode('pick')}
            style={{ flex: 1 }}
          >
            Выбрать существующую SKU
          </button>
          <button
            type="button"
            className={'btn btn-sm ' + (mode === 'create' ? 'btn-primary' : 'btn-ghost')}
            onClick={() => setMode('create')}
            style={{ flex: 1 }}
          >
            Создать новую SKU
          </button>
        </div>
      )}

      {(isEdit || mode === 'pick') && (
        <div className="field">
          <label>Номенклатура *</label>
          <select
            className="input"
            value={pickedNom}
            onChange={(e) => setPickedNom(e.target.value)}
            disabled={isEdit}
          >
            <option value="">— выберите —</option>
            {items?.map((it) => (
              <option key={it.id} value={it.id}>
                {it.sku} · {it.name}
              </option>
            ))}
          </select>
          {!isEdit && !items?.length && vetCategory && (
            <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
              В категории «Ветпрепараты» нет SKU. Создайте новую через переключатель выше.
            </div>
          )}
          {!isEdit && !vetCategory && (
            <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
              Категория «Ветпрепараты» будет создана автоматически.
            </div>
          )}
          {renderFieldError('nomenclature')}
        </div>
      )}

      {!isEdit && mode === 'create' && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div className="field">
              <label>SKU *</label>
              <input
                className="input mono"
                value={newSku}
                onChange={(e) => setNewSku(e.target.value)}
                placeholder="ВП-АНТ-01"
              />
              {renderFieldError('sku')}
            </div>
            <div className="field">
              <label>Ед. изм. *</label>
              <select
                className="input"
                value={newUnit}
                onChange={(e) => setNewUnit(e.target.value)}
              >
                <option value="">—</option>
                {units?.map((u) => (
                  <option key={u.id} value={u.id}>{u.code} · {u.name}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="field">
            <label>Название *</label>
            <input
              className="input"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Энрофлоксацин 10%"
            />
            {renderFieldError('name')}
          </div>
        </>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>Тип *</label>
          <select
            className="input"
            value={drugType}
            onChange={(e) => setDrugType(e.target.value as DrugType)}
          >
            {DRUG_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Путь введения *</label>
          <select
            className="input"
            value={route}
            onChange={(e) => setRoute(e.target.value as DrugRoute)}
          >
            {ROUTES.map((r) => (
              <option key={r.value} value={r.value}>{r.label}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>
            Каренция, дней
            <HelpHint text="Срок ожидания после применения, в течение которого нельзя забивать птицу. Подставляется по умолчанию при создании нового лечения." />
          </label>
          <input
            className="input mono"
            type="number"
            min="0"
            value={withdrawalDays}
            onChange={(e) => setWithdrawalDays(e.target.value)}
          />
        </div>
        <div className="field">
          <label>Условия хранения</label>
          <input
            className="input"
            value={storage}
            onChange={(e) => setStorage(e.target.value)}
            placeholder="+2…+8 °C, тёмное место"
          />
        </div>
      </div>

      <div className="field">
        <label>Заметка</label>
        <textarea
          className="input"
          rows={2}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </div>

      <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
        <input
          type="checkbox"
          checked={isActive}
          onChange={(e) => setIsActive(e.target.checked)}
        />
        Активный (доступен для применения и приёмки)
      </label>

      {error instanceof ApiError && error.status !== 400 && (
        <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 12 }}>
          Ошибка: {error.message}
        </div>
      )}
    </Modal>
  );
}
