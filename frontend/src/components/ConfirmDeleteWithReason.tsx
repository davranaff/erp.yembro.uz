'use client';

import { useState } from 'react';

import Modal from '@/components/ui/Modal';

interface Props {
  /** Заголовок модалки. Например: "Удалить взвешивание?" */
  title: string;
  /** Что именно удаляется — короткое описание для пользователя. */
  subject: string;
  /** Минимальная длина reason. Должна совпадать с backend (default 3). */
  minReasonLength?: number;
  /** Колбэк удаления. Получает reason. */
  onConfirm: (reason: string) => void | Promise<void>;
  onClose: () => void;
  isPending?: boolean;
}

/**
 * Универсальная confirm-модалка для удаления с обязательной причиной.
 * Используется для всех дочерних записей с DeleteReasonMixin на бэке.
 *
 * Пример:
 *   const del = weighingsCrud.useDelete();
 *   const [confirmW, setConfirmW] = useState<DailyWeighing | null>(null);
 *   ...
 *   {confirmW && (
 *     <ConfirmDeleteWithReason
 *       title="Удалить взвешивание?"
 *       subject={`день ${confirmW.day_of_age} · ${confirmW.avg_weight_kg} кг`}
 *       isPending={del.isPending}
 *       onConfirm={(reason) =>
 *         del.mutateAsync({ id: confirmW.id, reason }).then(() => setConfirmW(null))
 *       }
 *       onClose={() => setConfirmW(null)}
 *     />
 *   )}
 */
export default function ConfirmDeleteWithReason({
  title,
  subject,
  minReasonLength = 3,
  onConfirm,
  onClose,
  isPending = false,
}: Props) {
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reasonOk = reason.trim().length >= minReasonLength;

  const handle = async () => {
    if (!reasonOk) return;
    setError(null);
    setSubmitting(true);
    try {
      await onConfirm(reason.trim());
    } catch (e) {
      const err = e as { message?: string };
      setError(err.message ?? 'Не удалось удалить');
    } finally {
      setSubmitting(false);
    }
  };

  const busy = isPending || submitting;

  return (
    <Modal
      title={title}
      onClose={busy ? () => undefined : onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose} disabled={busy}>
            Отмена
          </button>
          <button
            className="btn btn-danger"
            onClick={handle}
            disabled={!reasonOk || busy}
          >
            {busy ? 'Удаление…' : 'Удалить'}
          </button>
        </>
      }
    >
      <div style={{ marginBottom: 12, fontSize: 13 }}>
        Вы собираетесь удалить:{' '}
        <strong>{subject}</strong>
      </div>

      <div className="field">
        <label>
          Причина удаления *
          <span style={{ marginLeft: 6, fontSize: 11, color: 'var(--fg-3)' }}>
            (попадёт в журнал аудита)
          </span>
        </label>
        <textarea
          className="input"
          rows={3}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="например: опечатка в количестве, дублирующая запись"
          autoFocus
        />
        {!reasonOk && reason.length > 0 && (
          <div style={{ fontSize: 11, color: 'var(--warning)' }}>
            Минимум {minReasonLength} символа
          </div>
        )}
      </div>

      <div style={{
        marginTop: 8, padding: 8, fontSize: 12,
        background: 'rgba(239,68,68,.08)',
        border: '1px solid var(--danger)',
        borderRadius: 6, color: 'var(--danger)',
      }}>
        ⚠ Удаление необратимо. Запись пропадёт из списка, но останется в audit log.
      </div>

      {error && (
        <div style={{ marginTop: 10, fontSize: 12, color: 'var(--danger)' }}>
          {error}
        </div>
      )}
    </Modal>
  );
}
