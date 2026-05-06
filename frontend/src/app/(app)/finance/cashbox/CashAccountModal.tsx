'use client';

import { useMemo, useState } from 'react';

import Modal from '@/components/ui/Modal';
import {
  useAccounts,
  useCreateSubaccount,
  useSubaccounts,
  useUpdateSubaccount,
} from '@/hooks/useAccounts';
import { useModules } from '@/hooks/useModules';
import { ApiError } from '@/lib/api';
import { uppercaseChange } from '@/lib/forms';
import type { GLSubaccount } from '@/types/auth';

interface Props {
  onClose: () => void;
  /** Дефолтный модуль (например модуль активной страницы). */
  defaultModuleId?: string;
  /** Если задан — режим редактирования. */
  initial?: GLSubaccount | null;
}

type Kind = 'cash' | 'bank';

const KIND_META: Record<Kind, { label: string; parentCode: string; placeholder: string }> = {
  cash: { label: 'Касса',         parentCode: '50', placeholder: 'Касса наличные · вет' },
  bank: { label: 'Расчётный счёт', parentCode: '51', placeholder: 'Hamkor bank · корма'  },
};

/**
 * Создание новой кассы или банковского счёта прямо со страницы /finance/cashbox.
 * По сути — узкий wrapper над SubaccountModal: автоматически выбирает родителем
 * счёт 50 (Касса) или 51 (Расчётные счета), требует модуль для изоляции
 * (vet/feed/feedlot и т.д.).
 *
 * Код субсчёта подсказывается автоматически: 50.NN или 51.NN — следующий
 * свободный номер.
 */
export default function CashAccountModal({ onClose, defaultModuleId, initial }: Props) {
  const isEdit = Boolean(initial);
  const create = useCreateSubaccount();
  const update = useUpdateSubaccount();
  const { data: accounts } = useAccounts();
  const { data: subaccounts } = useSubaccounts();
  const { data: modules } = useModules();

  const initialKind: Kind = initial?.code.startsWith('51.') ? 'bank' : 'cash';
  const [kind, setKind] = useState<Kind>(initialKind);
  const [name, setName] = useState(initial?.name ?? '');
  const [moduleId, setModuleId] = useState(initial?.module ?? defaultModuleId ?? '');
  const [code, setCode] = useState(initial?.code ?? '');

  const parentAccount = useMemo(
    () => accounts?.find((a) => a.code === KIND_META[kind].parentCode),
    [accounts, kind],
  );

  const suggestedCode = useMemo(() => {
    const prefix = KIND_META[kind].parentCode;
    const existing = (subaccounts ?? [])
      .filter((s) => s.code.startsWith(prefix + '.'))
      .map((s) => parseInt(s.code.split('.')[1] ?? '0', 10))
      .filter((n) => !Number.isNaN(n));
    const next = (existing.length ? Math.max(...existing) : 0) + 1;
    return `${prefix}.${String(next).padStart(2, '0')}`;
  }, [subaccounts, kind]);

  const effectiveCode = code.trim() || suggestedCode;

  const error = create.error ?? update.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, unknown>) ?? {})
    : {};
  const getErr = (k: string): string | null => {
    const v = (fieldErrors as Record<string, unknown>)[k];
    if (Array.isArray(v)) return v.join(' · ');
    if (typeof v === 'string') return v;
    return null;
  };

  const canSubmit =
    Boolean(parentAccount) && name.trim() && moduleId
    && !create.isPending && !update.isPending;

  const handleSubmit = async () => {
    if (!parentAccount || !canSubmit) return;
    try {
      if (isEdit && initial) {
        // При edit меняем только name + module (code/parent иммутабельны —
        // на них могут ссылаться существующие платежи).
        await update.mutateAsync({
          id: initial.id,
          patch: { name: name.trim(), module: moduleId },
        });
      } else {
        await create.mutateAsync({
          account: parentAccount.id,
          code: effectiveCode,
          name: name.trim(),
          module: moduleId,
        });
      }
      onClose();
    } catch {
      /* ошибка через fieldErrors */
    }
  };

  return (
    <Modal
      title={
        isEdit
          ? `Редактировать ${kind === 'cash' ? 'кассу' : 'счёт'} ${initial?.code ?? ''}`
          : kind === 'cash' ? 'Новая касса' : 'Новый расчётный счёт'
      }
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button className="btn btn-primary" disabled={!canSubmit} onClick={handleSubmit}>
            {create.isPending || update.isPending
              ? 'Сохранение…'
              : isEdit ? 'Сохранить' : 'Создать'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
        Касса/банк изолируются по модулю: head модуля видит и управляет
        только своими счётами. Под капотом создаётся субсчёт под{' '}
        <span className="mono">{KIND_META[kind].parentCode}</span>{' '}
        ({kind === 'cash' ? 'Касса' : 'Расчётные счета'}).
      </div>

      {!isEdit && (
        <div className="field">
          <label>Тип счёта *</label>
          <div style={{ display: 'flex', gap: 6 }}>
            {(['cash', 'bank'] as Kind[]).map((k) => (
              <button
                key={k}
                type="button"
                className={'btn btn-sm ' + (kind === k ? 'btn-primary' : 'btn-ghost')}
                onClick={() => { setKind(k); setCode(''); }}
                style={{ flex: 1 }}
              >
                {KIND_META[k].label}
              </button>
            ))}
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>Модуль *</label>
          <select
            className="input"
            value={moduleId}
            onChange={(e) => setModuleId(e.target.value)}
          >
            <option value="">— выберите модуль —</option>
            {modules?.filter((m) => m.is_active).map((m) => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </select>
          {getErr('module') && <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getErr('module')}</div>}
        </div>

        <div className="field">
          <label>{isEdit ? 'Код' : `Код (опц., авто-${suggestedCode})`}</label>
          <input
            className="input mono upper"
            value={code}
            onChange={uppercaseChange(setCode)}
            placeholder={suggestedCode}
            disabled={isEdit}
          />
          {getErr('code') && <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getErr('code')}</div>}
        </div>
      </div>

      <div className="field">
        <label>Наименование *</label>
        <input
          className="input"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={KIND_META[kind].placeholder}
        />
        {getErr('name') && <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getErr('name')}</div>}
      </div>

      {!parentAccount && accounts && (
        <div style={{
          marginTop: 10, padding: 8, fontSize: 12,
          background: '#fef2f2', color: 'var(--danger)', borderRadius: 6,
        }}>
          В плане счетов нет счёта <span className="mono">{KIND_META[kind].parentCode}</span> —
          создайте его сначала в /accounts.
        </div>
      )}

      {error instanceof ApiError && error.status !== 400 && (
        <div style={{
          marginTop: 10, padding: 8, fontSize: 12,
          background: '#fef2f2', color: 'var(--danger)', borderRadius: 6,
        }}>
          {error.message}
        </div>
      )}
    </Modal>
  );
}
