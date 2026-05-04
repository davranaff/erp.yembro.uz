'use client';

import type { Batch } from '@/types/auth';

/**
 * Inline-бейдж «🩺 vet: <препарат>, каренция до DD.MM».
 *
 * Появляется когда у партии есть проведённое (есть JE) но не подтверждённое
 * менеджером модуля-цели ветлечение. Снимается через
 * `IncomingVetTreatmentsPanel` → «Подтвердить».
 */
export default function PendingVetTreatmentBadge({
  batch,
}: {
  batch: Pick<Batch, 'pending_vet_acknowledgement'>;
}) {
  const v = batch.pending_vet_acknowledgement;
  if (!v) return null;

  const drug = v.drug_name ?? '—';
  const ends = v.withdrawal_period_ends
    ? new Date(v.withdrawal_period_ends).toLocaleDateString('ru-RU', {
        day: '2-digit', month: '2-digit',
      })
    : null;

  return (
    <span
      title={`${v.doc_number}: применён ${drug}${ends ? `, каренция до ${ends}` : ''}. Менеджер модуля ещё не подтвердил.`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        padding: '2px 8px',
        borderRadius: 10,
        fontSize: 11,
        fontWeight: 500,
        background: 'color-mix(in srgb, var(--brand-orange) 15%, transparent)',
        color: 'var(--brand-orange)',
        border: '1px solid var(--brand-orange)',
        whiteSpace: 'nowrap',
      }}
    >
      🩺 vet: {drug}{ends ? ` · до ${ends}` : ''}
    </span>
  );
}
