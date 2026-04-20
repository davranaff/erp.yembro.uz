import { Loader2 } from 'lucide-react';
import { useMemo } from 'react';

import { ErrorNotice } from '@/components/ui/error-notice';
import {
  getDebtsAging,
  type DebtsAgingBuckets,
  type DebtsAgingResponse,
} from '@/shared/api/finance';
import { useApiQuery } from '@/shared/api/react-query';
import { useI18n } from '@/shared/i18n';
import { cn } from '@/shared/lib/cn';

type DebtsAgingPanelProps = {
  variant: 'receivables' | 'payables';
  departmentId?: string | null;
  departmentIds?: readonly string[] | null;
};

const formatAmount = (value: number): string =>
  new Intl.NumberFormat('ru-RU', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value || 0);

const bucketTone = (key: keyof DebtsAgingBuckets): string => {
  switch (key) {
    case 'not_due':
      return 'text-emerald-700 bg-emerald-500/10 ring-emerald-500/20';
    case 'bucket_0_30':
      return 'text-sky-700 bg-sky-500/10 ring-sky-500/20';
    case 'bucket_31_60':
      return 'text-amber-700 bg-amber-500/10 ring-amber-500/25';
    case 'bucket_61_90':
      return 'text-orange-700 bg-orange-500/10 ring-orange-500/25';
    case 'bucket_90_plus':
      return 'text-rose-700 bg-rose-500/10 ring-rose-500/25';
    default:
      return 'text-foreground bg-muted ring-border/50';
  }
};

const BUCKETS: ReadonlyArray<{ key: keyof DebtsAgingBuckets; labelKey: string; fallback: string }> =
  [
    { key: 'not_due', labelKey: 'finance.aging.notDue', fallback: 'Не просрочено' },
    { key: 'bucket_0_30', labelKey: 'finance.aging.0_30', fallback: '0–30 дн.' },
    { key: 'bucket_31_60', labelKey: 'finance.aging.31_60', fallback: '31–60 дн.' },
    { key: 'bucket_61_90', labelKey: 'finance.aging.61_90', fallback: '61–90 дн.' },
    { key: 'bucket_90_plus', labelKey: 'finance.aging.90_plus', fallback: '90+ дн.' },
  ];

export function DebtsAgingPanel({ variant, departmentId, departmentIds }: DebtsAgingPanelProps) {
  const { t } = useI18n();
  const normalizedIds = useMemo(() => {
    const source =
      departmentIds && departmentIds.length > 0
        ? Array.from(departmentIds)
        : departmentId
          ? [departmentId]
          : [];
    return source
      .map((id) => id.trim())
      .filter((id) => id.length > 0)
      .sort();
  }, [departmentIds, departmentId]);
  const scopeKey = normalizedIds.length > 0 ? normalizedIds.join(',') : 'all';
  const query = useApiQuery<DebtsAgingResponse>({
    queryKey: ['finance', 'debts', 'aging', scopeKey],
    queryFn: () =>
      getDebtsAging(normalizedIds.length > 0 ? { departmentIds: normalizedIds } : undefined),
  });

  const buckets = query.data?.[variant];
  const title =
    variant === 'receivables'
      ? t('finance.aging.receivablesTitle', undefined, 'Старение дебиторки')
      : t('finance.aging.payablesTitle', undefined, 'Старение кредиторки');

  return (
    <section className="space-y-3">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <h3 className="text-sm font-semibold tracking-tight text-foreground">{title}</h3>
        {query.data?.as_of ? (
          <span className="text-xs text-muted-foreground">
            {t('finance.aging.asOf', undefined, 'на дату')}: {query.data.as_of}
          </span>
        ) : null}
      </div>
      {query.isLoading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          {t('common.loadingLabel', undefined, 'Загружаем…')}
        </div>
      ) : null}
      {query.error ? <ErrorNotice error={query.error} /> : null}
      {buckets ? (
        <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
          {BUCKETS.map(({ key, labelKey, fallback }) => (
            <div
              key={key}
              className={cn(
                'flex flex-col gap-1 rounded-2xl px-3 py-2 ring-1 ring-inset',
                bucketTone(key),
              )}
            >
              <span className="text-[11px] font-medium uppercase tracking-wide opacity-80">
                {t(labelKey, undefined, fallback)}
              </span>
              <span className="text-lg font-semibold tracking-tight">
                {formatAmount(buckets[key])}
              </span>
            </div>
          ))}
          <div className="flex flex-col gap-1 rounded-2xl bg-foreground/5 px-3 py-2 ring-1 ring-inset ring-border/60">
            <span className="text-[11px] font-medium uppercase tracking-wide opacity-80">
              {t('finance.aging.total', undefined, 'Итого')}
            </span>
            <span className="text-lg font-semibold tracking-tight">
              {formatAmount(buckets.total)}
            </span>
          </div>
        </div>
      ) : null}
    </section>
  );
}
