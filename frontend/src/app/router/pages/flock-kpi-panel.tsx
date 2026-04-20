import { Gauge, Loader2 } from 'lucide-react';

import { ErrorNotice } from '@/components/ui/error-notice';
import { type CrudRecord } from '@/shared/api/backend-crud';
import { getFactoryFlockKpi, type FactoryFlockKpi } from '@/shared/api/factory';
import { baseQueryKeys } from '@/shared/api/query-keys';
import { useApiQuery } from '@/shared/api/react-query';
import { useI18n } from '@/shared/i18n';
import { cn } from '@/shared/lib/cn';

type FlockKpiPanelProps = {
  flock: CrudRecord;
};

const getFlockId = (flock: CrudRecord): string => {
  const id = (flock as { id?: unknown }).id;
  return typeof id === 'string' ? id : '';
};

const formatNumber = (value: number, fractionDigits = 0): string =>
  new Intl.NumberFormat('ru-RU', {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(value);

const formatPercent = (value: number | null | undefined): string => {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return '—';
  }
  return `${formatNumber(value * 100, 2)}%`;
};

const formatRatio = (value: number | null | undefined, fractionDigits = 2): string => {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return '—';
  }
  return formatNumber(value, fractionDigits);
};

type KpiTone = 'good' | 'warning' | 'bad' | 'neutral';

const toneClass: Record<KpiTone, string> = {
  good: 'bg-emerald-500/10 text-emerald-700 ring-emerald-500/25',
  warning: 'bg-amber-500/10 text-amber-700 ring-amber-500/25',
  bad: 'bg-rose-500/10 text-rose-700 ring-rose-500/25',
  neutral: 'bg-muted text-muted-foreground ring-border/40',
};

const fcrTone = (value: number | null | undefined): KpiTone => {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return 'neutral';
  }
  if (value <= 1.7) {
    return 'good';
  }
  if (value <= 2.0) {
    return 'warning';
  }
  return 'bad';
};

const mortalityTone = (value: number | null | undefined): KpiTone => {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return 'neutral';
  }
  if (value <= 0.04) {
    return 'good';
  }
  if (value <= 0.07) {
    return 'warning';
  }
  return 'bad';
};

type KpiCardProps = {
  label: string;
  value: string;
  tone?: KpiTone;
  hint?: string;
};

function KpiCard({ label, value, tone = 'neutral', hint }: KpiCardProps) {
  return (
    <div
      className={cn('flex flex-col gap-1 rounded-2xl px-4 py-3 ring-1 ring-inset', toneClass[tone])}
    >
      <div className="text-xs font-medium uppercase tracking-wide opacity-80">{label}</div>
      <div className="text-xl font-semibold tracking-tight">{value}</div>
      {hint ? <div className="text-xs opacity-70">{hint}</div> : null}
    </div>
  );
}

export function FlockKpiPanel({ flock }: FlockKpiPanelProps) {
  const { t } = useI18n();
  const flockId = getFlockId(flock);

  const kpiQuery = useApiQuery<FactoryFlockKpi>({
    queryKey: [...baseQueryKeys.crud.item('factory', 'flocks', flockId || 'unknown'), 'kpi'],
    queryFn: () => getFactoryFlockKpi(flockId),
    enabled: Boolean(flockId),
  });

  if (!flockId) {
    return null;
  }

  return (
    <section className="space-y-4 rounded-2xl border border-border/70 bg-background/60 p-5 shadow-[0_16px_48px_-32px_rgba(15,23,42,0.14)]">
      <header className="flex items-center gap-2 text-sm font-semibold text-foreground">
        <Gauge className="h-4 w-4 text-primary" />
        {t('factory.flockKpi.title', undefined, 'KPI стада')}
      </header>
      <div className="space-y-3">
        {kpiQuery.isLoading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            {t('common.loadingLabel', undefined, 'Загружаем…')}
          </div>
        ) : null}
        {kpiQuery.error ? <ErrorNotice error={kpiQuery.error} /> : null}
        {kpiQuery.data ? (
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            <KpiCard
              label={t('factory.flockKpi.fcr', undefined, 'FCR (корм/прирост)')}
              value={formatRatio(kpiQuery.data.fcr, 2)}
              tone={fcrTone(kpiQuery.data.fcr)}
              hint={`${formatNumber(kpiQuery.data.feed_kg_total, 1)} kg / ${formatNumber(
                kpiQuery.data.live_weight_total_kg,
                1,
              )} kg`}
            />
            <KpiCard
              label={t('factory.flockKpi.mortality', undefined, 'Смертность')}
              value={formatPercent(kpiQuery.data.mortality_pct)}
              tone={mortalityTone(kpiQuery.data.mortality_pct)}
              hint={`${formatNumber(kpiQuery.data.mortality_total)} / ${formatNumber(kpiQuery.data.initial_count)}`}
            />
            <KpiCard
              label={t('factory.flockKpi.avgWeight', undefined, 'Ср. вес (kg)')}
              value={formatRatio(kpiQuery.data.latest_avg_weight_kg, 3)}
              hint={
                kpiQuery.data.last_log_date
                  ? `${t('factory.flockKpi.lastLog', undefined, 'Последний лог')}: ${kpiQuery.data.last_log_date}`
                  : undefined
              }
            />
            <KpiCard
              label={t('factory.flockKpi.costAlive', undefined, 'Себест. на живую птицу')}
              value={formatRatio(kpiQuery.data.cost_per_chick_alive, 2)}
              hint={`${t('factory.flockKpi.alive', undefined, 'В наличии')}: ${formatNumber(kpiQuery.data.current_count)}`}
            />
            <KpiCard
              label={t('factory.flockKpi.costShipped', undefined, 'Себест. на отгруж.')}
              value={formatRatio(kpiQuery.data.cost_per_chick_shipped, 2)}
              hint={`${t('factory.flockKpi.shipped', undefined, 'Отгружено')}: ${formatNumber(kpiQuery.data.birds_shipped)}`}
            />
            <KpiCard
              label={t('factory.flockKpi.totalCost', undefined, 'Итого затрат')}
              value={formatNumber(kpiQuery.data.total_cost, 2)}
              hint={`${t('factory.flockKpi.feed', undefined, 'Корм')}: ${formatNumber(kpiQuery.data.feed_cost_total, 2)} · ${t('factory.flockKpi.medicine', undefined, 'Лекарства')}: ${formatNumber(kpiQuery.data.medicine_cost_total, 2)}`}
            />
          </div>
        ) : null}
      </div>
    </section>
  );
}
