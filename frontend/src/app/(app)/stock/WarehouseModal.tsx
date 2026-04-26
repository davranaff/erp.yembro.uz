'use client';

import { useEffect, useState } from 'react';

import Modal from '@/components/ui/Modal';
import { useSubaccounts } from '@/hooks/useAccounts';
import { useProductionBlocks } from '@/hooks/useBlocks';
import { useModules } from '@/hooks/useModules';
import {
  useCreateWarehouse,
  useUpdateWarehouse,
  type WarehousePayload,
} from '@/hooks/useStockMovements';
import { ApiError } from '@/lib/api';
import type { WarehouseRef } from '@/types/auth';

interface Props {
  initial?: WarehouseRef | null;
  onClose: () => void;
  onSaved?: (w: WarehouseRef) => void;
}

export default function WarehouseModal({ initial, onClose, onSaved }: Props) {
  const { data: modules } = useModules();
  const { data: blocks } = useProductionBlocks({ is_active: 'true' });
  const { data: subaccounts } = useSubaccounts();
  const create = useCreateWarehouse();
  const update = useUpdateWarehouse();
  const isEdit = Boolean(initial);
  const saving = create.isPending || update.isPending;
  const error = (isEdit ? update.error : create.error) ?? null;

  const [code, setCode] = useState(initial?.code ?? '');
  const [name, setName] = useState(initial?.name ?? '');
  const [moduleId, setModuleId] = useState(initial?.module ?? '');
  const [productionBlock, setProductionBlock] = useState(initial?.production_block ?? '');
  const [defaultGl, setDefaultGl] = useState(initial?.default_gl_subaccount ?? '');
  const [isActive, setIsActive] = useState(initial?.is_active ?? true);

  useEffect(() => {
    if (!initial) return;
    setCode(initial.code);
    setName(initial.name);
    setModuleId(initial.module);
    setProductionBlock(initial.production_block ?? '');
    setDefaultGl(initial.default_gl_subaccount ?? '');
    setIsActive(initial.is_active);
  }, [initial]);

  const fieldErrors =
    error instanceof ApiError && error.status === 400
      ? ((error.data as Record<string, string[]>) ?? {})
      : {};

  // Блоки фильтруем по выбранному модулю — это улучшает UX (склад «висит» внутри блока).
  const blocksForModule = blocks?.filter((b) => !moduleId || b.module === moduleId) ?? [];

  const handleSave = async () => {
    const payload: WarehousePayload = {
      code,
      name,
      module: moduleId,
      production_block: productionBlock || null,
      default_gl_subaccount: defaultGl || null,
      is_active: isActive,
    };
    try {
      const res = isEdit && initial
        ? await update.mutateAsync({ id: initial.id, patch: payload })
        : await create.mutateAsync(payload);
      onSaved?.(res);
      onClose();
    } catch {
      /* errors surfaced inline */
    }
  };

  return (
    <Modal
      title={isEdit ? `Склад · ${initial?.code}` : 'Новый склад'}
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
            placeholder="СК-Ф"
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
            placeholder="Склад фабрики"
          />
          {fieldErrors.name && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>
              {fieldErrors.name.join(' · ')}
            </div>
          )}
        </div>
        <div className="field">
          <label>Модуль *</label>
          <select
            className="input"
            value={moduleId}
            onChange={(e) => {
              setModuleId(e.target.value);
              setProductionBlock(''); // сбрасываем блок при смене модуля
            }}
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
          <label>Производственный блок</label>
          <select
            className="input"
            value={productionBlock}
            onChange={(e) => setProductionBlock(e.target.value)}
            disabled={!moduleId}
          >
            <option value="">— не указан —</option>
            {blocksForModule.map((b) => (
              <option key={b.id} value={b.id}>
                {b.code} · {b.name}
              </option>
            ))}
          </select>
          {fieldErrors.production_block && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>
              {fieldErrors.production_block.join(' · ')}
            </div>
          )}
        </div>
        <div className="field" style={{ gridColumn: '1 / -1' }}>
          <label>Субсчёт учёта по умолчанию</label>
          <select
            className="input"
            value={defaultGl}
            onChange={(e) => setDefaultGl(e.target.value)}
          >
            <option value="">— не указан —</option>
            {subaccounts?.map((s) => (
              <option key={s.id} value={s.id}>
                {s.code} · {s.name}
              </option>
            ))}
          </select>
          <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
            Используется как дебет при автоматических приходах через закуп.
          </div>
          {fieldErrors.default_gl_subaccount && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>
              {fieldErrors.default_gl_subaccount.join(' · ')}
            </div>
          )}
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
