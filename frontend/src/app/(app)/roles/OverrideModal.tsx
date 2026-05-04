'use client';

import { useState } from 'react';

import Modal from '@/components/ui/Modal';
import { useModules } from '@/hooks/useModules';
import {
  useCreateOverride,
  useMemberships,
  useUpdateOverride,
  type UserModuleAccessOverride,
} from '@/hooks/useRbac';
import { ApiError } from '@/lib/api';
import type { ModuleLevel } from '@/types/auth';

const LEVELS: { value: ModuleLevel; label: string; help: string }[] = [
  { value: 'none',  label: 'Нет доступа',     help: 'Перекрывает любые права роли в этом модуле.' },
  { value: 'r',     label: 'Просмотр (R)',    help: 'Только чтение.' },
  { value: 'rw',    label: 'Ввод (RW)',       help: 'Чтение + создание/изменение документов.' },
  { value: 'admin', label: 'Администратор',   help: 'Полный доступ к модулю.' },
];

interface Props {
  initial?: UserModuleAccessOverride | null;
  onClose: () => void;
}

export default function OverrideModal({ initial, onClose }: Props) {
  const isEdit = Boolean(initial);
  const create = useCreateOverride();
  const update = useUpdateOverride();
  const saving = create.isPending || update.isPending;
  const error = (isEdit ? update.error : create.error) ?? null;

  const { data: memberships } = useMemberships();
  const { data: modules } = useModules();

  const [membership, setMembership] = useState(initial?.membership ?? '');
  const [moduleId, setModuleId] = useState(initial?.module ?? '');
  const [level, setLevel] = useState<ModuleLevel>(initial?.level ?? 'r');
  const [reason, setReason] = useState(initial?.reason ?? '');

  const fieldErrors =
    error instanceof ApiError && error.status === 400
      ? ((error.data as Record<string, string[] | string>) ?? {})
      : {};

  const renderError = (key: string) => {
    const v = fieldErrors[key];
    if (!v) return null;
    const txt = Array.isArray(v) ? v.join(' · ') : v;
    return <div style={{ fontSize: 11, color: 'var(--danger)' }}>{txt}</div>;
  };

  const handleSave = async () => {
    try {
      if (isEdit && initial) {
        await update.mutateAsync({
          id: initial.id,
          patch: { level, reason },
        });
      } else {
        await create.mutateAsync({
          membership,
          module: moduleId,
          level,
          reason,
        });
      }
      onClose();
    } catch {
      /* errors surfaced inline */
    }
  };

  return (
    <Modal
      title={isEdit ? 'Изменить исключение' : 'Новое исключение'}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>
            Отмена
          </button>
          <button
            className="btn btn-primary"
            disabled={saving || !membership || !moduleId}
            onClick={handleSave}
          >
            {saving ? 'Сохранение…' : isEdit ? 'Сохранить' : 'Создать'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
        Исключение перекрывает уровень доступа к модулю для конкретного
        пользователя — независимо от его ролей. Используется для интерим-замен,
        ограничений или временного расширения прав.
      </div>

      <div className="field">
        <label>Пользователь *</label>
        <select
          className="input"
          value={membership}
          onChange={(e) => setMembership(e.target.value)}
          disabled={isEdit}
        >
          <option value="">— выберите —</option>
          {memberships?.map((m) => (
            <option key={m.id} value={m.id}>
              {m.user_full_name} · {m.user_email}
            </option>
          ))}
        </select>
        {renderError('membership')}
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
              {m.name} ({m.code})
            </option>
          ))}
        </select>
        {renderError('module')}
      </div>

      <div className="field">
        <label>Уровень *</label>
        <select
          className="input"
          value={level}
          onChange={(e) => setLevel(e.target.value as ModuleLevel)}
        >
          {LEVELS.map((l) => (
            <option key={l.value} value={l.value}>
              {l.label}
            </option>
          ))}
        </select>
        <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
          {LEVELS.find((l) => l.value === level)?.help}
        </div>
        {renderError('level')}
      </div>

      <div className="field">
        <label>Причина</label>
        <input
          className="input"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Например: интерим-замена технолога на отпуске"
        />
        {renderError('reason')}
      </div>

      {error && error.status !== 400 && (
        <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 12 }}>
          Ошибка: {error.message}
        </div>
      )}
    </Modal>
  );
}
