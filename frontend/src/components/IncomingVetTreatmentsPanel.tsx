'use client';

import { useState } from 'react';

import Modal from '@/components/ui/Modal';
import Badge from '@/components/ui/Badge';
import Icon from '@/components/ui/Icon';
import { ApiError } from '@/lib/api';
import {
  useAcknowledgeTreatment,
  useIncomingVetTreatments,
  useRejectTreatment,
} from '@/hooks/useVet';
import type { VetTreatmentLog } from '@/types/auth';

interface Props {
  /** Код модуля-цели: 'feedlot', 'incubation', 'matochnik'. */
  module: string;
  subtitle?: string;
}

const INDICATION_LABEL: Record<string, string> = {
  routine: 'Плановая',
  prophylaxis: 'Профилактика',
  therapy: 'Лечение',
  emergency: 'Экстренно',
};

const INDICATION_TONE: Record<string, 'info' | 'warn' | 'danger' | 'neutral'> = {
  routine: 'info',
  prophylaxis: 'info',
  therapy: 'warn',
  emergency: 'danger',
};

/**
 * Inbox менеджера модуля-цели для ветобработок.
 *
 * Soft-acknowledgement: ветеринар уже применил препарат (стоксы списаны,
 * JE проведён, каренция на партии выставлена). Здесь менеджер модуля-цели
 * только видит факт применения и подтверждает «принял к сведению».
 *
 * Скрывается если нет неподтверждённых treatment'ов или у юзера нет r+
 * к этому модулю (запрос вернёт 403, query.error → панель не рендерится).
 */
export default function IncomingVetTreatmentsPanel({
  module,
  subtitle,
}: Props) {
  const { data, isLoading, error } = useIncomingVetTreatments(module);
  const ack = useAcknowledgeTreatment();
  const reject = useRejectTreatment();

  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState('');

  const rejecting = rejectingId
    ? data?.find((t) => t.id === rejectingId) ?? null
    : null;

  const closeReject = () => {
    setRejectingId(null);
    setRejectReason('');
    reject.reset();
  };

  const submitReject = async () => {
    if (!rejectingId || rejectReason.trim().length < 3) return;
    try {
      await reject.mutateAsync({ id: rejectingId, reason: rejectReason.trim() });
      closeReject();
    } catch {
      /* error shown inline */
    }
  };

  const rejectFieldErrors =
    reject.error instanceof ApiError && reject.error.status === 400
      ? ((reject.error.data as Record<string, unknown>) ?? {})
      : {};
  const rejectErrorDetail =
    reject.error instanceof ApiError && reject.error.status === 403
      ? (((reject.error.data as Record<string, unknown>)?.detail as string | undefined) ?? reject.error.message)
      : null;

  if (isLoading) return null;
  if (error || !data || data.length === 0) return null;

  return (
    <div
      style={{
        padding: 12, marginBottom: 12, borderRadius: 6,
        background: 'var(--bg-soft, #FFF7ED)',
        border: '1px solid var(--brand-orange, #E8751A)',
        borderLeft: '3px solid var(--brand-orange, #E8751A)',
      }}
    >
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8,
        fontSize: 13, fontWeight: 600,
      }}>
        <Icon name="bag" size={14} />
        Новые ветобработки ({data.length}) — {subtitle ?? 'требуют подтверждения'}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {data.map((t) => {
          const target = t.target_batch_doc
            ? `партия ${t.target_batch_doc}`
            : t.target_herd_doc
              ? `стадо ${t.target_herd_doc}`
              : '—';
          return (
            <div
              key={t.id}
              style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: 8, background: 'var(--bg-card, #fff)',
                border: '1px solid var(--border)', borderRadius: 4,
                fontSize: 12, flexWrap: 'wrap',
              }}
            >
              <Badge tone={INDICATION_TONE[t.indication] ?? 'neutral'}>
                {INDICATION_LABEL[t.indication] ?? t.indication}
              </Badge>
              <span className="mono" style={{ fontWeight: 600 }}>
                {t.doc_number}
              </span>
              <span style={{ color: 'var(--fg-3)' }}>·</span>
              <span>{t.drug_name ?? t.drug_sku ?? '—'}</span>
              <span style={{ color: 'var(--fg-3)' }}>·</span>
              <span className="mono">
                {parseFloat(t.dose_quantity).toLocaleString('ru-RU')} {t.unit_code ?? ''}
              </span>
              <span style={{ color: 'var(--fg-3)' }}>·</span>
              <span>{target}</span>
              {t.withdrawal_period_days > 0 && (
                <>
                  <span style={{ color: 'var(--fg-3)' }}>·</span>
                  <span style={{ color: 'var(--brand-orange)' }}>
                    каренция {t.withdrawal_period_days} дн
                  </span>
                </>
              )}
              <span style={{ color: 'var(--fg-3)' }}>·</span>
              <span style={{ color: 'var(--fg-2)' }}>
                {t.veterinarian_name ?? '—'} · {new Date(t.treatment_date).toLocaleDateString('ru-RU')}
              </span>
              <div style={{ flex: 1 }} />
              <button
                className="btn btn-ghost btn-sm"
                style={{ color: 'var(--danger)' }}
                disabled={ack.isPending || reject.isPending}
                onClick={() => {
                  setRejectingId(t.id);
                  setRejectReason('');
                  reject.reset();
                }}
                title="Отклонить применение (реверс проводок + возврат остатка на лот). Доступно 24ч после применения."
              >
                Отклонить
              </button>
              <button
                className="btn btn-primary btn-sm"
                disabled={ack.isPending}
                onClick={() => ack.mutate({ id: t.id })}
              >
                {ack.isPending && ack.variables?.id === t.id ? 'Подтверждение…' : 'Подтвердить'}
              </button>
            </div>
          );
        })}
      </div>

      {ack.error && (
        <div style={{
          marginTop: 8, padding: 6,
          fontSize: 11, color: 'var(--danger)',
          background: '#fef2f2', borderRadius: 4,
        }}>
          {ack.error.message}
        </div>
      )}

      {rejecting && (
        <RejectModal
          treatment={rejecting}
          reason={rejectReason}
          setReason={setRejectReason}
          onSubmit={submitReject}
          onClose={closeReject}
          isPending={reject.isPending}
          fieldErrors={rejectFieldErrors}
          permissionError={rejectErrorDetail}
        />
      )}
    </div>
  );
}

interface RejectModalProps {
  treatment: VetTreatmentLog;
  reason: string;
  setReason: (s: string) => void;
  onSubmit: () => void;
  onClose: () => void;
  isPending: boolean;
  fieldErrors: Record<string, unknown>;
  permissionError: string | null;
}

function RejectModal({
  treatment,
  reason,
  setReason,
  onSubmit,
  onClose,
  isPending,
  fieldErrors,
  permissionError,
}: RejectModalProps) {
  const target = treatment.target_batch_doc
    ? `партия ${treatment.target_batch_doc}`
    : treatment.target_herd_doc
      ? `стадо ${treatment.target_herd_doc}`
      : '—';
  const reasonErr = fieldErrors.reason;
  const reasonErrText = Array.isArray(reasonErr)
    ? reasonErr.join(' · ')
    : typeof reasonErr === 'string'
      ? reasonErr
      : null;

  return (
    <Modal
      title="Отклонить применение препарата"
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose} disabled={isPending}>
            Отмена
          </button>
          <button
            className="btn btn-primary"
            style={{ background: 'var(--danger)' }}
            disabled={isPending || reason.trim().length < 3}
            onClick={onSubmit}
          >
            {isPending ? 'Отклонение…' : 'Отклонить и реверснуть'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-2)', marginBottom: 12 }}>
        Применение <strong className="mono">{treatment.doc_number}</strong> ·{' '}
        {treatment.drug_name ?? treatment.drug_sku ?? '—'} ·{' '}
        {parseFloat(treatment.dose_quantity).toLocaleString('ru-RU')}{' '}
        {treatment.unit_code ?? ''} → {target}
      </div>

      <div
        style={{
          fontSize: 12, color: 'var(--fg-3)', marginBottom: 12,
          padding: 8, background: 'var(--bg-soft)', borderRadius: 4,
        }}
      >
        После отклонения произойдёт:<br />
        • Сторно бухпроводок (Дт 10.03 / Кт 20.XX)<br />
        • Возврат дозы на лот {treatment.stock_batch_lot ?? ''}<br />
        • Снятие vet-затрат с партии<br />
        • Пересчёт каренции на основе оставшихся лечений<br />
        <br />
        ⚠ Окно отклонения — 24ч после применения. Если птица уже продана/убита,
        обратитесь к ветеринару (только он может откатить позже).
      </div>

      <div className="field">
        <label>Причина отклонения *</label>
        <textarea
          className="input"
          rows={3}
          autoFocus
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Опечатка в дозе, не та партия, ошибочный препарат…"
        />
        {reasonErrText && (
          <div style={{ fontSize: 11, color: 'var(--danger)' }}>{reasonErrText}</div>
        )}
        <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
          Минимум 3 символа. Будет сохранено в audit-log и видно ветеринару.
        </div>
      </div>

      {permissionError && (
        <div style={{
          marginTop: 10, padding: 8,
          background: '#fef2f2', color: 'var(--danger)',
          borderRadius: 6, fontSize: 12,
        }}>
          {permissionError}
        </div>
      )}
    </Modal>
  );
}
