'use client';

import type { Batch } from '@/types/auth';

/**
 * Маленький inline-бейдж «партия в пути → <модуль> · <doc>».
 *
 * Появляется когда у партии есть открытая InterModuleTransfer
 * (AWAITING_ACCEPTANCE или UNDER_REVIEW). Это происходит после того как
 * sender нажал «Отправить в …», но receiver ещё не принял (и не выбрал
 * склад приёмки). Раньше передачи проводились моментально, теперь —
 * двухфазно, и партия может «висеть» какое-то время.
 *
 * Стиль — оранжевая капсула в линию с doc-number / именем партии.
 */
export default function PendingTransferBadge({ batch }: { batch: Pick<Batch, 'pending_transfer'> }) {
  const t = batch.pending_transfer;
  if (!t) return null;
  const target = t.to_module_name ?? t.to_module_code ?? '?';
  const stateLabel =
    t.state === 'under_review' ? 'на проверке' : 'в пути';
  return (
    <span
      title={`${t.doc_number}: ждёт приёма в модуле ${target}`}
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
      ↗ {stateLabel} → {target}
    </span>
  );
}
