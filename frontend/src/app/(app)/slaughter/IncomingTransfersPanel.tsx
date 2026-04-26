'use client';

import Badge from '@/components/ui/Badge';
import Icon from '@/components/ui/Icon';
import { useAcceptTransfer, useIncomingTransfers } from '@/hooks/useSlaughter';
import type { InterModuleTransfer } from '@/types/auth';

const STATE_LABEL: Record<string, string> = {
  awaiting_acceptance: 'Ожидает приёма',
  under_review: 'На проверке',
};

const STATE_TONE: Record<string, 'warn' | 'info'> = {
  awaiting_acceptance: 'warn',
  under_review: 'info',
};

export default function IncomingTransfersPanel() {
  const { data: transfers, isLoading, error } = useIncomingTransfers();
  const accept = useAcceptTransfer();

  const handleAccept = (t: InterModuleTransfer) => {
    if (!window.confirm(
      `Принять партию ${t.batch_doc_number ?? t.doc_number}? ` +
      `${t.quantity} ${t.unit_code ?? ''} → склад убойни`,
    )) return;
    accept.mutate(t.id, {
      onSuccess: () => {
        alert(
          `Партия ${t.batch_doc_number ?? t.doc_number} принята. ` +
          `Теперь видна в форме «Новая смена» (BatchSelector).`,
        );
      },
      onError: (err) => alert(`Не удалось принять: ${err.message}`),
    });
  };

  if (isLoading) return null;
  if (error) {
    return (
      <div style={{
        padding: 12, marginBottom: 12, borderRadius: 6,
        background: 'var(--bg-soft)', border: '1px solid var(--border)',
        fontSize: 12, color: 'var(--danger)',
      }}>
        Ошибка загрузки входящих: {error.message}
      </div>
    );
  }
  if (!transfers || transfers.length === 0) return null;

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
        Входящие партии ({transfers.length}) — ждут приёма из откорма
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {transfers.map((t) => (
          <div
            key={t.id}
            style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: 8, background: 'var(--bg-card, #fff)',
              border: '1px solid var(--border)', borderRadius: 4,
              fontSize: 12,
            }}
          >
            <Badge tone={STATE_TONE[t.state] ?? 'neutral'}>
              {STATE_LABEL[t.state] ?? t.state}
            </Badge>
            <span className="mono" style={{ fontWeight: 600 }}>
              {t.doc_number}
            </span>
            <span style={{ color: 'var(--fg-3)' }}>·</span>
            <span className="mono">
              {t.batch_doc_number ?? '—'}
            </span>
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
