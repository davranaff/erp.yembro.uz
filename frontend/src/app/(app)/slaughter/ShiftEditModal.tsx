'use client';

import { useState } from 'react';

import Modal from '@/components/ui/Modal';
import { ApiError } from '@/lib/api';
import { usePeople } from '@/hooks/usePeople';
import { shiftsCrud } from '@/hooks/useSlaughter';
import type { SlaughterShift } from '@/types/auth';

interface Props {
  shift: SlaughterShift;
  onClose: () => void;
}

/**
 * Редактирование смены убоя. Доступно пока статус ACTIVE/CLOSED
 * (бэк блокирует POSTED/CANCELLED через ImmutableStatusMixin).
 *
 * Редактируемые поля: foreman, notes, end_time. Остальное (источник партии,
 * голов, живой вес) — изменения через отдельные операции (например через reverse).
 */
export default function ShiftEditModal({ shift, onClose }: Props) {
  const update = shiftsCrud.useUpdate();
  const { data: people } = usePeople({ is_active: 'true' });

  const [foreman, setForeman] = useState(shift.foreman);
  const [notes, setNotes] = useState(shift.notes ?? '');
  const [endTime, setEndTime] = useState(
    shift.end_time ? shift.end_time.slice(0, 16) : '',
  );

  const error = update.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, string[]>) ?? {})
    : {};

  const submit = async () => {
    try {
      await update.mutateAsync({
        id: shift.id,
        patch: {
          foreman,
          notes,
          end_time: endTime ? new Date(endTime).toISOString() : null,
        } as Partial<SlaughterShift>,
      });
      onClose();
    } catch { /* */ }
  };

  return (
    <Modal
      title={`Редактировать смену · ${shift.doc_number}`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            onClick={submit}
            disabled={update.isPending}
          >
            {update.isPending ? 'Сохранение…' : 'Сохранить'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
        Изменение источника партии, голов и веса возможно только через откат
        (reverse) и пересоздание смены — это влияет на учёт.
      </div>

      <div className="field">
        <label>Бригадир *</label>
        <select className="input" value={foreman} onChange={(e) => setForeman(e.target.value)}>
          {people?.map((p) => (
            <option key={p.user} value={p.user}>
              {p.user_full_name} · {p.position_title || p.user_email}
            </option>
          ))}
        </select>
        {fieldErrors.foreman && (
          <div style={{ fontSize: 11, color: 'var(--danger)' }}>
            {fieldErrors.foreman.join(' · ')}
          </div>
        )}
      </div>

      <div className="field">
        <label>Конец смены</label>
        <input
          className="input"
          type="datetime-local"
          value={endTime}
          onChange={(e) => setEndTime(e.target.value)}
        />
      </div>

      <div className="field">
        <label>Заметка</label>
        <textarea
          className="input"
          rows={3}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </div>

      {error && error.status !== 400 && (
        <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 12 }}>
          Ошибка: {error.message}
        </div>
      )}
    </Modal>
  );
}
