'use client';

import { useState } from 'react';

import Modal from '@/components/ui/Modal';
import { ApiError } from '@/lib/api';
import { useCreatePerson, useUpdatePerson } from '@/hooks/usePeople';
import type { MembershipRow } from '@/types/auth';

interface Props {
  initial?: MembershipRow | null;
  onClose: () => void;
  onSaved?: (m: MembershipRow) => void;
}

const WORK_STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: 'active',      label: 'Активен' },
  { value: 'vacation',    label: 'Отпуск' },
  { value: 'sick_leave',  label: 'Больничный' },
  { value: 'terminated',  label: 'Уволен' },
];

export default function PersonModal({ initial, onClose, onSaved }: Props) {
  const create = useCreatePerson();
  const update = useUpdatePerson();
  const saving = create.isPending || update.isPending;
  const error = (initial ? update.error : create.error) ?? null;
  const isEdit = !!initial;

  const [email, setEmail] = useState(initial?.user_email ?? '');
  const [fullName, setFullName] = useState(initial?.user_full_name ?? '');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [positionTitle, setPositionTitle] = useState(initial?.position_title ?? '');
  const [workPhone, setWorkPhone] = useState(initial?.work_phone ?? '');
  const [workStatus, setWorkStatus] = useState(initial?.work_status ?? 'active');

  const fieldErrors =
    error instanceof ApiError && error.status === 400
      ? ((error.data as Record<string, string[]>) ?? {})
      : {};

  const handleSave = async () => {
    try {
      if (isEdit && initial) {
        const res = await update.mutateAsync({
          id: initial.id,
          patch: {
            position_title: positionTitle,
            work_phone: workPhone,
            work_status: workStatus,
          },
        });
        onSaved?.(res);
      } else {
        const res = await create.mutateAsync({
          email,
          full_name: fullName,
          phone,
          password: password || undefined,
          position_title: positionTitle,
          work_phone: workPhone,
          work_status: workStatus,
        });
        onSaved?.(res);
      }
      onClose();
    } catch {
      /* field errors */
    }
  };

  return (
    <Modal
      title={isEdit ? `Сотрудник · ${initial?.user_full_name}` : 'Новый сотрудник'}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>
            Отмена
          </button>
          <button
            className="btn btn-primary"
            disabled={saving || (!isEdit && (!email || !fullName))}
            onClick={handleSave}
          >
            {saving ? 'Сохранение…' : isEdit ? 'Сохранить' : 'Добавить'}
          </button>
        </>
      }
    >
      {!isEdit && (
        <>
          <div className="field">
            <label>Email *</label>
            <input
              className="input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="ivanov@example.com"
            />
            {fieldErrors.email && (
              <div style={{ fontSize: 11, color: 'var(--danger)' }}>
                {fieldErrors.email.join(' · ')}
              </div>
            )}
          </div>
          <div className="field">
            <label>ФИО *</label>
            <input
              className="input"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
            {fieldErrors.full_name && (
              <div style={{ fontSize: 11, color: 'var(--danger)' }}>
                {fieldErrors.full_name.join(' · ')}
              </div>
            )}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
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
              <label>Начальный пароль</label>
              <input
                className="input"
                type="text"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="оставьте пустым — вход заблокирован"
              />
            </div>
          </div>
          <div
            style={{
              fontSize: 11,
              color: 'var(--fg-3)',
              marginBottom: 8,
              padding: 6,
              background: 'var(--bg-soft)',
              borderRadius: 4,
            }}
          >
            Если email уже зарегистрирован в системе — будет использован существующий
            аккаунт (только добавится membership в текущей компании).
          </div>
        </>
      )}

      {isEdit && (
        <div className="field">
          <label>Пользователь</label>
          <input
            className="input"
            value={`${initial?.user_full_name ?? ''} · ${initial?.user_email ?? ''}`}
            disabled
          />
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>Должность</label>
          <input
            className="input"
            value={positionTitle}
            onChange={(e) => setPositionTitle(e.target.value)}
            placeholder="Технолог"
          />
        </div>
        <div className="field">
          <label>Рабочий телефон</label>
          <input
            className="input"
            value={workPhone}
            onChange={(e) => setWorkPhone(e.target.value)}
          />
        </div>
        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>Статус</label>
          <select
            className="input"
            value={workStatus}
            onChange={(e) => setWorkStatus(e.target.value)}
          >
            {WORK_STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
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
