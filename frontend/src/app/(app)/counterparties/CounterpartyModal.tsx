'use client';

import { useEffect, useState } from 'react';

import AmountInput from '@/components/ui/AmountInput';
import Modal from '@/components/ui/Modal';
import { ApiError } from '@/lib/api';
import { uppercaseChange } from '@/lib/forms';
import {
  useCreateCounterparty,
  useUpdateCounterparty,
} from '@/hooks/useCounterparties';
import type { Counterparty, CounterpartyKind } from '@/types/auth';

interface Props {
  initial?: Counterparty | null;
  onClose: () => void;
  onSaved?: (c: Counterparty) => void;
}

const KIND_OPTIONS: { value: CounterpartyKind; label: string }[] = [
  { value: 'supplier', label: 'Поставщик' },
  { value: 'buyer',    label: 'Покупатель' },
  { value: 'other',    label: 'Прочее' },
];

export default function CounterpartyModal({ initial, onClose, onSaved }: Props) {
  const create = useCreateCounterparty();
  const update = useUpdateCounterparty();
  const saving = create.isPending || update.isPending;
  const error = (initial ? update.error : create.error) ?? null;
  const isEdit = !!initial;

  const [code, setCode] = useState(initial?.code ?? '');
  const [kind, setKind] = useState<CounterpartyKind>(initial?.kind ?? 'supplier');
  const [name, setName] = useState(initial?.name ?? '');
  const [inn, setInn] = useState(initial?.inn ?? '');
  const [specialization, setSpecialization] = useState(initial?.specialization ?? '');
  const [phone, setPhone] = useState(initial?.phone ?? '');
  const [email, setEmail] = useState(initial?.email ?? '');
  const [address, setAddress] = useState(initial?.address ?? '');
  const [isActive, setIsActive] = useState(initial?.is_active ?? true);
  const [creditLimit, setCreditLimit] = useState(initial?.credit_limit_uzs ?? '');
  const [maxOverdue, setMaxOverdue] = useState(
    initial?.max_overdue_days != null ? String(initial.max_overdue_days) : '',
  );
  const [openingDebt, setOpeningDebt] = useState(initial?.opening_debt_uzs ?? '');
  const [openingDate, setOpeningDate] = useState(initial?.opening_balance_date ?? '');

  useEffect(() => {
    if (!initial) return;
    setCode(initial.code);
    setKind(initial.kind);
    setName(initial.name);
    setInn(initial.inn ?? '');
    setSpecialization(initial.specialization ?? '');
    setPhone(initial.phone ?? '');
    setEmail(initial.email ?? '');
    setAddress(initial.address ?? '');
    setIsActive(initial.is_active);
    setCreditLimit(initial.credit_limit_uzs ?? '');
    setMaxOverdue(
      initial.max_overdue_days != null ? String(initial.max_overdue_days) : '',
    );
    setOpeningDebt(initial.opening_debt_uzs ?? '');
    setOpeningDate(initial.opening_balance_date ?? '');
  }, [initial]);

  const fieldErrors =
    error instanceof ApiError && error.status === 400
      ? ((error.data as Record<string, string[]>) ?? {})
      : {};

  const handleSave = async () => {
    const payload = {
      code,
      kind,
      name,
      inn,
      specialization,
      phone,
      email,
      address,
      is_active: isActive,
      credit_limit_uzs: creditLimit.trim() ? creditLimit.trim() : null,
      max_overdue_days: maxOverdue.trim() ? Number(maxOverdue.trim()) : null,
      opening_debt_uzs: openingDebt.trim() || '0',
      opening_balance_date: openingDate || null,
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
      /* error visible via fieldErrors */
    }
  };

  return (
    <Modal
      title={isEdit ? `Редактирование · ${initial?.name}` : 'Новый контрагент'}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>
            Отмена
          </button>
          <button
            className="btn btn-primary"
            disabled={saving || !code || !name}
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
            className="input mono upper"
            value={code}
            onChange={uppercaseChange(setCode)}
            disabled={isEdit}
            placeholder="К-001"
          />
          {fieldErrors.code && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>
              {fieldErrors.code.join(' · ')}
            </div>
          )}
        </div>
        <div className="field">
          <label>Тип *</label>
          <select
            className="input"
            value={kind}
            onChange={(e) => setKind(e.target.value as CounterpartyKind)}
          >
            {KIND_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
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
          <label>ИНН</label>
          <input
            className="input mono"
            value={inn}
            onChange={(e) => setInn(e.target.value)}
            placeholder="302 845 128"
          />
          {fieldErrors.inn && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>
              {fieldErrors.inn.join(' · ')}
            </div>
          )}
        </div>
        <div className="field">
          <label>Телефон</label>
          <input
            className="input"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+998 …"
          />
        </div>
        <div className="field">
          <label>Email</label>
          <input
            className="input"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="field">
          <label>Статус</label>
          <select
            className="input"
            value={isActive ? '1' : '0'}
            onChange={(e) => setIsActive(e.target.value === '1')}
          >
            <option value="1">Активен</option>
            <option value="0">Заблокирован</option>
          </select>
        </div>
        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>Специализация</label>
          <input
            className="input"
            value={specialization}
            onChange={(e) => setSpecialization(e.target.value)}
            placeholder="Корма · пшеница, соя"
          />
        </div>
        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>Адрес</label>
          <input
            className="input"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
          />
        </div>

        {kind === 'buyer' && (
          <>
            <div style={{
              gridColumn: '1/3', marginTop: 8, paddingTop: 12,
              borderTop: '1px solid var(--border)',
            }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
                Кредитная политика
              </div>
              <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
                Если задано — система автоматически блокирует confirm новых
                продаж при превышении лимита или просрочке. Пусто = без
                ограничения. sales:admin может обойти блок при confirm.
              </div>
            </div>
            <div className="field">
              <label>Кредитный лимит, сум</label>
              <AmountInput
                className="input mono"
                value={creditLimit}
                onChange={setCreditLimit}
                placeholder="например 50 000 000"
              />
              {fieldErrors.credit_limit_uzs && (
                <div style={{ fontSize: 11, color: 'var(--danger)' }}>
                  {fieldErrors.credit_limit_uzs.join(' · ')}
                </div>
              )}
            </div>
            <div className="field">
              <label>Макс. просрочка, дн</label>
              <input
                className="input mono"
                type="number"
                value={maxOverdue}
                onChange={(e) => setMaxOverdue(e.target.value)}
                placeholder="например 30"
                min={0}
              />
              {fieldErrors.max_overdue_days && (
                <div style={{ fontSize: 11, color: 'var(--danger)' }}>
                  {fieldErrors.max_overdue_days.join(' · ')}
                </div>
              )}
            </div>
          </>
        )}

        {/* Стартовый долг (миграция из другой ERP) — для всех kind. */}
        <div style={{
          gridColumn: '1 / -1',
          marginTop: 6, paddingTop: 10,
          borderTop: '1px solid var(--border)',
        }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
            Стартовый долг (миграция)
          </div>
          <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
            Заполняется один раз при переносе данных с другой системы.
            Прибавляется к live-долгу в отчётах и debt-проверках.
            Знак: <b>+</b> — должны нам, <b>−</b> — мы должны (предоплата).
          </div>
        </div>
        <div className="field">
          <label>Стартовый долг, сум</label>
          <AmountInput
            className="input mono"
            value={openingDebt}
            onChange={setOpeningDebt}
            placeholder="0"
          />
          {fieldErrors.opening_debt_uzs && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>
              {(fieldErrors.opening_debt_uzs as unknown as string[]).join(' · ')}
            </div>
          )}
        </div>
        <div className="field">
          <label>Дата стартового долга</label>
          <input
            className="input"
            type="date"
            value={openingDate}
            onChange={(e) => setOpeningDate(e.target.value)}
          />
          {fieldErrors.opening_balance_date && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>
              {(fieldErrors.opening_balance_date as unknown as string[]).join(' · ')}
            </div>
          )}
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
