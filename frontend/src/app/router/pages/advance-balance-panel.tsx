import { HandCoins } from 'lucide-react';

import { ErrorNotice } from '@/components/ui/error-notice';
import { InlineLoader } from '@/components/ui/inline-loader';
import { getAdvanceBalance, type CrudRecord } from '@/shared/api/backend-crud';
import { toQueryKey } from '@/shared/api/query-keys';
import { useApiQuery } from '@/shared/api/react-query';
import { useI18n } from '@/shared/i18n';
import { cn } from '@/shared/lib/cn';

interface AdvanceBalancePanelProps {
  advance: CrudRecord;
}

function formatAmount(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') {
    return '—';
  }
  const parsed = typeof value === 'string' ? Number(value) : value;
  if (Number.isNaN(parsed)) {
    return String(value);
  }
  return parsed.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function AdvanceBalancePanel({ advance }: AdvanceBalancePanelProps) {
  const { t } = useI18n();
  const advanceId = String(advance.id || '').trim();

  const balanceQuery = useApiQuery({
    queryKey: toQueryKey('finance', 'advance-balance', advanceId || 'unknown'),
    queryFn: () => getAdvanceBalance(advanceId),
    enabled: advanceId.length > 0,
  });

  if (!advanceId) {
    return null;
  }

  const data = balanceQuery.data;
  const currencyLabel = data?.currency || '';

  const cards: Array<{ key: string; label: string; value: string; tone: string }> = [
    {
      key: 'issued',
      label: t('crud.advanceIssued', undefined, 'Выдано под отчёт'),
      value: formatAmount(data?.amount_issued),
      tone: 'border-primary/25 bg-primary/5 text-primary',
    },
    {
      key: 'reconciled',
      label: t('crud.advanceReconciled', undefined, 'Отчитались'),
      value: formatAmount(data?.amount_reconciled),
      tone: 'border-emerald-200/70 bg-emerald-50/80 text-emerald-800',
    },
    {
      key: 'returned',
      label: t('crud.advanceReturned', undefined, 'Возвращено в кассу'),
      value: formatAmount(data?.amount_returned),
      tone: 'border-sky-200/70 bg-sky-50/80 text-sky-800',
    },
    {
      key: 'outstanding',
      label: t('crud.advanceOutstanding', undefined, 'Остаток за сотрудником'),
      value: formatAmount(data?.amount_outstanding),
      tone: 'border-amber-200/70 bg-amber-50/80 text-amber-800',
    },
  ];

  return (
    <section className="rounded-2xl border border-border/75 bg-card p-4">
      <header className="flex items-center gap-2 text-sm font-semibold text-foreground">
        <HandCoins className="h-4 w-4 text-primary" />
        <span>{t('crud.advanceBalanceTitle', undefined, 'Баланс подотчёта')}</span>
        {currencyLabel ? (
          <span className="ml-auto text-xs uppercase tracking-[0.14em] text-muted-foreground">
            {currencyLabel}
          </span>
        ) : null}
      </header>

      <div className="mt-3">
        {balanceQuery.isLoading ? (
          <InlineLoader />
        ) : balanceQuery.error ? (
          <ErrorNotice error={balanceQuery.error} />
        ) : (
          <div className="grid gap-2 md:grid-cols-2">
            {cards.map((card) => (
              <div
                key={card.key}
                className={cn(
                  'rounded-xl border px-3 py-3 text-sm shadow-[0_12px_32px_-28px_rgba(15,23,42,0.15)]',
                  card.tone,
                )}
              >
                <div className="text-[11px] font-medium uppercase tracking-[0.14em] opacity-80">
                  {card.label}
                </div>
                <div className="mt-1 text-lg font-semibold tabular-nums">{card.value}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
