'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import Badge from '@/components/ui/Badge';
import Icon from '@/components/ui/Icon';
import { ApiError, apiFetch } from '@/lib/api';
import type { InterModuleTransfer } from '@/types/auth';

const STATE_LABEL: Record<string, string> = {
  awaiting_acceptance: 'Ожидает приёма',
  under_review: 'На проверке',
};

const STATE_TONE: Record<string, 'warn' | 'info'> = {
  awaiting_acceptance: 'warn',
  under_review: 'info',
};

interface Props {
  /** Код целевого модуля для которого показываем inbox: 'feedlot', 'incubation', 'matochnik', 'feed' и т.д. */
  module: string;
  /** Подзаголовок панели (опционально). По умолчанию: «ждут приёма». */
  subtitle?: string;
  /** Что инвалидировать в react-query после accept (помимо transfers + batches). */
  invalidateKeys?: readonly (readonly unknown[])[];
}

/**
 * Универсальная панель «Входящие межмодульные передачи».
 *
 * Показывается на странице каждого модуля сверху списка. Если incoming-
 * транзферов нет (или query 403/empty) — панель не рендерится, шум на
 * пустых страницах не создаём.
 *
 * Бэкенд: GET /api/transfers/incoming/?to_module=<module>.
 * Accept: POST /api/transfers/{id}/accept/.
 */
export default function IncomingTransfersPanel({
  module,
  subtitle,
  invalidateKeys = [],
}: Props) {
  const qc = useQueryClient();

  const { data: transfers, isLoading, error } = useQuery<InterModuleTransfer[], ApiError>({
    queryKey: ['transfers', 'incoming', module],
    queryFn: () =>
      apiFetch<InterModuleTransfer[]>(`/api/transfers/incoming/?to_module=${module}`),
    staleTime: 30_000,
    retry: false,  // 403 не повторяем
  });

  const accept = useMutation<unknown, ApiError, string>({
    mutationFn: (transferId) =>
      apiFetch(`/api/transfers/${transferId}/accept/`, { method: 'POST' }),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ['transfers'], refetchType: 'all' }),
        qc.invalidateQueries({ queryKey: ['batches'], refetchType: 'all' }),
        ...invalidateKeys.map((key) =>
          qc.invalidateQueries({ queryKey: [...key], refetchType: 'all' }),
        ),
      ]);
    },
  });

  const handleAccept = (t: InterModuleTransfer) => {
    if (!window.confirm(
      `Принять партию ${t.batch_doc_number ?? t.doc_number}? ` +
      `${t.quantity} ${t.unit_code ?? ''} → ${t.to_module_name ?? t.to_module_code ?? module}`,
    )) return;
    accept.mutate(t.id, {
      onError: (err) => alert(`Не удалось принять: ${err.message}`),
    });
  };

  // Тихо скрываем при отсутствии данных, ошибке доступа, либо пустом списке.
  if (isLoading) return null;
  if (error || !transfers || transfers.length === 0) return null;

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
        Входящие партии ({transfers.length}) — {subtitle ?? 'ждут приёма'}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {transfers.map((t) => (
          <div
            key={t.id}
            style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: 8, background: 'var(--bg-card, #fff)',
              border: '1px solid var(--border)', borderRadius: 4,
              fontSize: 12, flexWrap: 'wrap',
            }}
          >
            <Badge tone={STATE_TONE[t.state] ?? 'neutral'}>
              {STATE_LABEL[t.state] ?? t.state}
            </Badge>
            <span className="mono" style={{ fontWeight: 600 }}>
              {t.doc_number}
            </span>
            <span style={{ color: 'var(--fg-3)' }}>·</span>
            <span className="mono">{t.batch_doc_number ?? '—'}</span>
            <span style={{ color: 'var(--fg-3)' }}>·</span>
            <span className="mono">
              {parseFloat(t.quantity).toLocaleString('ru-RU')} {t.unit_code ?? ''}
            </span>
            <span style={{ color: 'var(--fg-3)' }}>·</span>
            <span style={{ color: 'var(--fg-2)' }}>
              {t.from_module_name ?? t.from_module_code ?? '—'} → {t.to_module_name ?? t.to_module_code ?? '—'}
            </span>
            <div style={{ flex: 1 }} />
            <button
              className="btn btn-primary btn-sm"
              disabled={accept.isPending}
              onClick={() => handleAccept(t)}
            >
              {accept.isPending ? '…' : 'Принять'}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
