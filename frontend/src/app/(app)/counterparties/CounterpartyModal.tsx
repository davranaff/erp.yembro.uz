'use client';

import { useEffect, useState } from 'react';

import Modal from '@/components/ui/Modal';
import { ApiError } from '@/lib/api';
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
            className="input mono"
            value={code}
            onChange={(e) => setCode(e.target.value)}
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
      </div>

      {error && error.status !== 400 && (
        <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 12 }}>
          Ошибка: {error.message}
        </div>
      )}
    </Modal>
  );
}
