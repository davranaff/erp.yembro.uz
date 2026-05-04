'use client';

import { useState } from 'react';

import Modal from '@/components/ui/Modal';
import { useCreateSubaccount, useUpdateSubaccount } from '@/hooks/useAccounts';
import { useModules } from '@/hooks/useModules';
import { ApiError } from '@/lib/api';
import type { GLAccount, GLSubaccount } from '@/types/auth';

interface Props {
  /** Если задан — режим редактирования. */
  initial?: GLSubaccount | null;
  /** Все счета верхнего уровня (для выбора parent). */
  accounts: GLAccount[];
  /** Pre-selected parent account (из кнопки «+» на строке счёта). */
  defaultAccountId?: string;
  onClose: () => void;
}

export default function SubaccountModal({ initial, accounts, defaultAccountId, onClose }: Props) {
  const isEdit = Boolean(initial);
  const create = useCreateSubaccount();
  const update = useUpdateSubaccount();

  const { data: modules } = useModules();

  const [accountId, setAccountId] = useState(initial?.account ?? defaultAccountId ?? '');
  const [code, setCode] = useState(initial?.code ?? '');
  const [name, setName] = useState(initial?.name ?? '');
  const [moduleId, setModuleId] = useState(initial?.module ?? '');

  const error = create.error ?? update.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, unknown>) ?? {})
    : {};

  const getFieldErr = (k: string): string | null => {
    const v = (fieldErrors as Record<string, unknown>)[k];
    if (Array.isArray(v)) return v.join(' · ');
    if (typeof v === 'string') return v;
    return null;
  };

  const selectedAccount = accounts.find((a) => a.id === accountId);
  const codePlaceholder = selectedAccount ? `${selectedAccount.code}.99` : 'XX.YY';

  const canSubmit = accountId && code.trim() && name.trim() && !create.isPending && !update.isPending;

  const handleSubmit = async () => {
    const payload = {
      account: accountId,
      code: code.trim(),
      name: name.trim(),
      module: moduleId || null,
    };
    try {
      if (isEdit && initial) {
        await update.mutateAsync({ id: initial.id, patch: payload });
      } else {
        await create.mutateAsync(payload);
      }
      onClose();
    } catch {
      /* показываем через error */
    }
  };

  return (
    <Modal
      title={isEdit ? `Редактирование субсчёта ${initial?.code ?? ''}` : 'Новый субсчёт'}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={!canSubmit}
            onClick={handleSubmit}
          >
            {create.isPending || update.isPending ? 'Сохранение…' : 'Сохранить'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
        Субсчёт — это статья (например, «Аренда склада», «Премия сотрудникам»), вложенная
        в счёт верхнего уровня (10, 26, 91 и т.д.). Код формата <span className="mono">XX.YY</span>.
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field" style={{ gridColumn: '1 / 3' }}>
          <label>Родительский счёт *</label>
          <select
            className="input"
            value={accountId}
            onChange={(e) => setAccountId(e.target.value)}
            disabled={isEdit}
          >
            <option value="">—</option>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>{a.code} · {a.name}</option>
            ))}
          </select>
          {getFieldErr('account') && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getFieldErr('account')}</div>
          )}
        </div>

        <div className="field">
          <label>Код *</label>
          <input
            className="input mono"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder={codePlaceholder}
          />
          {getFieldErr('code') && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getFieldErr('code')}</div>
          )}
        </div>

        <div className="field">
          <label>Модуль (опционально)</label>
          <select className="input" value={moduleId} onChange={(e) => setModuleId(e.target.value)}>
            <option value="">— общий —</option>
            {modules?.map((m) => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </select>
        </div>

        <div className="field" style={{ gridColumn: '1 / 3' }}>
          <label>Наименование *</label>
          <input
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Например: Аренда склада А"
          />
          {getFieldErr('name') && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getFieldErr('name')}</div>
          )}
        </div>
      </div>

      {error instanceof ApiError && error.status !== 400 && (
        <div style={{ marginTop: 10, padding: 8, background: '#fef2f2', color: 'var(--danger)', borderRadius: 6, fontSize: 12 }}>
          {error.message}
        </div>
      )}
    </Modal>
  );
}
