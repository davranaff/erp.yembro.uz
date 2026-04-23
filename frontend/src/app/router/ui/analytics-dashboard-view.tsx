import { format, startOfDay, startOfMonth, startOfQuarter, subDays } from 'date-fns';
import {
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  Building2,
  CalendarRange,
  Clock3,
  Landmark,
  MapPinned,
  Minus,
  Sparkles,
  TrendingUp,
  Wallet,
  type LucideIcon,
} from 'lucide-react';

import { AnalyticsDateFilter } from '@/app/router/ui/analytics-date-filter';
import { DashboardBreakdownCard, DashboardChartCard } from '@/app/router/ui/dashboard-analytics';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { CustomSelect } from '@/components/ui/custom-select';
import { EmptyState } from '@/components/ui/empty-state';
import type { DashboardMetric, DashboardSection } from '@/shared/api';
import { useI18n } from '@/shared/i18n';
import type { TranslateFn } from '@/shared/i18n/types';
import { cn } from '@/shared/lib/cn';

import type { ReactNode } from 'react';

export type AnalyticsQuickRangePreset = {
  key: string;
  label: string;
  startDate: string;
  endDate: string;
};

export type AnalyticsStatusTone = 'good' | 'warning' | 'bad' | 'neutral';

export type AnalyticsDepartmentOption = {
  id: string;
  label: string;
  depth: number;
};

export type AnalyticsSectionDescriptor = {
  key: string;
  title: string;
  caption: string;
  section: DashboardSection | null;
};

type AnalyticsDashboardLayoutMode = 'default' | 'executive';

type AnalyticsDashboardViewProps = {
  title: string;
  badgeLabel: string;
  badgeTone: AnalyticsStatusTone;
  scopeLabel: string;
  periodLabel: string;
  updatedAtLabel?: string;
  quickRangePresets: AnalyticsQuickRangePreset[];
  activeQuickRangeKey: string;
  onQuickRangeApply: (preset: AnalyticsQuickRangePreset) => void;
  departmentFilter?: {
    value: string;
    options: AnalyticsDepartmentOption[];
    onChange: (departmentId: string) => void;
  };
  startDate: string;
  endDate: string;
  onDateRangeApply: (range: { startDate?: string; endDate?: string }) => void;
  onResetFilters: () => void;
  summaryMetrics: DashboardMetric[];
  sections: AnalyticsSectionDescriptor[];
  minimalMode?: boolean;
  layoutMode?: AnalyticsDashboardLayoutMode;
};

const SUMMARY_ICON_MAP: Record<string, LucideIcon> = {
  cash_balance: Wallet,
  total_revenue: TrendingUp,
  sales_revenue: TrendingUp,
  egg_revenue: TrendingUp,
  shipment_revenue: TrendingUp,
  total_expenses: ArrowDownRight,
  financial_result: Sparkles,
  operating_profit: Sparkles,
  net_cashflow: ArrowUpRight,
  active_departments: Building2,
  health_index: Sparkles,
  value_chain_output: Building2,
  value_chain_loss_rate: ArrowDownRight,
  active_risks: Landmark,
  active_alerts: Landmark,
  net_eggs: Building2,
  grade_1_total: Sparkles,
  grade_2_total: Sparkles,
  eggs_set: ArrowUpRight,
  chicks_hatched: Building2,
  chicks_stock: Building2,
  birds_processed: Building2,
  semi_product_output: Building2,
  product_output: Building2,
  current_stock: Building2,
  shipment_volume: ArrowUpRight,
  product_shipped: ArrowUpRight,
  chicks_dispatched: ArrowUpRight,
  sent_to_slaughter: ArrowUpRight,
  eggs_to_incubation: ArrowUpRight,
  eggs_arrived: ArrowUpRight,
  medicine_consumed: ArrowDownRight,
  client_base: Building2,
  stock_total: Building2,
  hatch_rate: Sparkles,
  process_rate: Sparkles,
  shipment_rate: Sparkles,
  turnover_rate: Sparkles,
  first_sort_share: Sparkles,
  loss_rate: ArrowDownRight,
  critical_stock_items: Landmark,
  expired_batches: Landmark,
  expiring_batches: Landmark,
  bad_eggs: Landmark,
};

const HERO_META_ICON_MAP = {
  scope: MapPinned,
  period: CalendarRange,
  updated: Clock3,
} satisfies Record<string, LucideIcon>;

const formatMetricValue = (value: number, locale: string, unit?: string | null) => {
  const formatter = new Intl.NumberFormat(locale, {
    maximumFractionDigits: Number.isInteger(value) ? 0 : 2,
  });
  const formatted = formatter.format(value);
  return unit ? `${formatted} ${unit}` : formatted;
};

const formatDeltaLabel = (metric: DashboardMetric, locale: string): string | null => {
  if (typeof metric.delta !== 'number') {
    return null;
  }

  const deltaValue = metric.delta;
  const deltaSign = deltaValue > 0 ? '+' : deltaValue < 0 ? '-' : '';
  const baseLabel = `${deltaSign}${formatMetricValue(Math.abs(deltaValue), locale, metric.unit)}`;

  if (typeof metric.deltaPercent === 'number') {
    const percentValue = metric.deltaPercent;
    const percentSign = percentValue > 0 ? '+' : percentValue < 0 ? '-' : '';
    const percentLabel = new Intl.NumberFormat(locale, {
      maximumFractionDigits: Number.isInteger(percentValue) ? 0 : 2,
    }).format(Math.abs(percentValue));
    return `${baseLabel} (${percentSign}${percentLabel}%)`;
  }

  return baseLabel;
};

const resolveMetricTone = (metric: DashboardMetric): AnalyticsStatusTone => {
  if (
    metric.status === 'good' ||
    metric.status === 'warning' ||
    metric.status === 'bad' ||
    metric.status === 'neutral'
  ) {
    return metric.status;
  }

  if (metric.value < 0) {
    return 'bad';
  }

  if (metric.value > 0) {
    return 'good';
  }

  return 'neutral';
};

const hasMeaningfulSectionData = (section: DashboardSection | null): boolean => {
  if (!section) {
    return false;
  }

  return (
    section.metrics.some((metric) => metric.value !== 0) ||
    section.charts.some((chart) => chart.series.some((series) => series.points.length > 0)) ||
    section.breakdowns.some((breakdown) => breakdown.items.length > 0)
  );
};

export const buildAnalyticsQuickRangePresets = (
  t: TranslateFn,
  today: Date,
): AnalyticsQuickRangePreset[] => {
  const todayStart = startOfDay(today);

  return [
    {
      key: 'today',
      label: t('dashboard.quickRangeToday'),
      startDate: format(todayStart, 'yyyy-MM-dd'),
      endDate: format(todayStart, 'yyyy-MM-dd'),
    },
    {
      key: 'last7',
      label: t('dashboard.quickRangeLast7Days'),
      startDate: format(subDays(todayStart, 6), 'yyyy-MM-dd'),
      endDate: format(todayStart, 'yyyy-MM-dd'),
    },
    {
      key: 'last30',
      label: t('dashboard.quickRangeLast30Days'),
      startDate: format(subDays(todayStart, 29), 'yyyy-MM-dd'),
      endDate: format(todayStart, 'yyyy-MM-dd'),
    },
    {
      key: 'month',
      label: t('dashboard.quickRangeMonth'),
      startDate: format(startOfMonth(todayStart), 'yyyy-MM-dd'),
      endDate: format(todayStart, 'yyyy-MM-dd'),
    },
    {
      key: 'quarter',
      label: t('dashboard.quickRangeQuarter'),
      startDate: format(startOfQuarter(todayStart), 'yyyy-MM-dd'),
      endDate: format(todayStart, 'yyyy-MM-dd'),
    },
  ];
};

export const formatAnalyticsPeriodLabel = (
  t: TranslateFn,
  startDate?: string,
  endDate?: string,
): string => {
  if (startDate && endDate) {
    if (startDate === endDate) {
      return format(new Date(`${startDate}T00:00:00`), 'dd.MM.yyyy');
    }

    return `${format(new Date(`${startDate}T00:00:00`), 'dd.MM.yyyy')} - ${format(new Date(`${endDate}T00:00:00`), 'dd.MM.yyyy')}`;
  }

  const singleDate = startDate || endDate;
  if (singleDate) {
    return format(new Date(`${singleDate}T00:00:00`), 'dd.MM.yyyy');
  }

  return t('dashboard.allTime');
};

export const getAnalyticsStatusClasses = (tone: AnalyticsStatusTone) => {
  if (tone === 'good') {
    return 'border-emerald-200/70 bg-emerald-50/90 text-emerald-700';
  }

  if (tone === 'warning') {
    return 'border-amber-200/70 bg-amber-50/90 text-amber-700';
  }

  if (tone === 'bad') {
    return 'border-rose-200/70 bg-rose-50/90 text-rose-700';
  }

  return 'border-primary/24 bg-card text-muted-foreground';
};

const getTrendIcon = (trend?: DashboardMetric['trend']): LucideIcon => {
  if (trend === 'up') {
    return ArrowUpRight;
  }

  if (trend === 'down') {
    return ArrowDownRight;
  }

  return Minus;
};

const buildPreviousValueLabel = (metric: DashboardMetric, locale: string, t: TranslateFn) => {
  if (typeof metric.previous !== 'number') {
    return null;
  }

  return `${t('dashboard.metricPreviousValue', undefined, 'Было')}: ${formatMetricValue(
    metric.previous,
    locale,
    metric.unit,
  )}`;
};

const getSectionCounts = (section: DashboardSection) => ({
  metrics: section.metrics.length,
  charts: section.charts.length,
  breakdowns: section.breakdowns.length,
});

function HeroMetaPill({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string;
  icon: LucideIcon;
}) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <Icon className="h-3.5 w-3.5 text-muted-foreground" />
      <span className="text-muted-foreground">{label}:</span>
      <span className="font-medium text-foreground">{value}</span>
    </span>
  );
}

function FilterPanelBlock({
  label,
  children,
  className,
  dataTour,
}: {
  label: string;
  children: ReactNode;
  className?: string;
  dataTour?: string;
}) {
  return (
    <div data-tour={dataTour} className={cn('space-y-1.5', className)}>
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      {children}
    </div>
  );
}

function SectionJumpBar({
  sections,
}: {
  sections: Array<AnalyticsSectionDescriptor & { index: number }>;
}) {
  const { t } = useI18n();

  if (sections.length <= 1) {
    return null;
  }

  return (
    <div className="space-y-2">
      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
        {t('dashboard.sectionJumpTitle', undefined, 'Разделы')}
      </p>
      <div className="flex flex-wrap gap-2">
        {sections.map((section) => {
          const sectionData = section.section;
          if (!sectionData) {
            return null;
          }

          const counts = getSectionCounts(sectionData);

          return (
            <Button
              key={section.key}
              type="button"
              variant="outline"
              className="border-primary/22 h-auto rounded-full px-4 py-2 text-left"
              onClick={() => {
                document
                  .getElementById(`dashboard-section-${section.key}`)
                  ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
              }}
            >
              <span className="flex items-center gap-2">
                <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-[11px] font-semibold text-primary">
                  {section.index + 1}
                </span>
                <span className="max-w-[14rem] truncate text-sm font-medium text-foreground">
                  {section.title}
                </span>
                <span className="text-xs text-muted-foreground">{counts.metrics} KPI</span>
              </span>
            </Button>
          );
        })}
      </div>
    </div>
  );
}

function SummaryMetricCard({ metric }: { metric: DashboardMetric }) {
  const { locale, t } = useI18n();
  const Icon = SUMMARY_ICON_MAP[metric.key] ?? Landmark;
  const tone = resolveMetricTone(metric);
  const deltaLabel = formatDeltaLabel(metric, locale);
  const TrendIcon = getTrendIcon(metric.trend);
  const previousValueLabel = buildPreviousValueLabel(metric, locale, t);

  const toneBarClass = cn(
    'absolute inset-y-0 left-0 w-0.5',
    tone === 'good' && 'bg-emerald-400/80',
    tone === 'warning' && 'bg-amber-400/80',
    tone === 'bad' && 'bg-rose-400/80',
    tone === 'neutral' && 'bg-primary/30',
  );

  const iconClass = cn(
    'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg',
    tone === 'good' && 'bg-emerald-50 text-emerald-600',
    tone === 'warning' && 'bg-amber-50 text-amber-600',
    tone === 'bad' && 'bg-rose-50 text-rose-600',
    tone === 'neutral' && 'bg-muted/60 text-muted-foreground',
  );

  const deltaClass = cn(
    'inline-flex items-center gap-1 text-xs font-medium',
    tone === 'good' && 'text-emerald-600',
    tone === 'warning' && 'text-amber-600',
    tone === 'bad' && 'text-rose-600',
    tone === 'neutral' && 'text-muted-foreground',
  );

  return (
    <div className="relative overflow-hidden rounded-xl border bg-card p-5 shadow-sm transition hover:shadow-md">
      <span className={toneBarClass} aria-hidden="true" />
      <div className="flex items-start gap-3">
        <span className={iconClass}>
          <Icon className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {metric.label}
          </p>
          <p className="mt-1.5 text-2xl font-semibold tracking-tight text-foreground">
            {formatMetricValue(metric.value, locale, metric.unit)}
          </p>
          {deltaLabel ? (
            <span className={cn('mt-2 flex items-center', deltaClass)}>
              <TrendIcon className="mr-1 h-3.5 w-3.5" />
              {deltaLabel}
              {previousValueLabel ? (
                <span className="ml-1.5 text-muted-foreground">· {previousValueLabel}</span>
              ) : null}
            </span>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function SectionMetricCard({ metric }: { metric: DashboardMetric }) {
  const { locale, t } = useI18n();
  const tone = resolveMetricTone(metric);
  const deltaLabel = formatDeltaLabel(metric, locale);
  const previousValueLabel = buildPreviousValueLabel(metric, locale, t);
  const TrendIcon = getTrendIcon(metric.trend);

  const toneBarClass = cn(
    'absolute inset-y-0 left-0 w-0.5',
    tone === 'good' && 'bg-emerald-400/80',
    tone === 'warning' && 'bg-amber-400/80',
    tone === 'bad' && 'bg-rose-400/80',
    tone === 'neutral' && 'bg-primary/30',
  );

  const deltaClass = cn(
    'mt-1.5 inline-flex items-center gap-1 text-xs font-medium',
    tone === 'good' && 'text-emerald-600',
    tone === 'warning' && 'text-amber-600',
    tone === 'bad' && 'text-rose-600',
    tone === 'neutral' && 'text-muted-foreground',
  );

  return (
    <div className="relative overflow-hidden rounded-xl border bg-card px-4 py-3 shadow-sm transition hover:shadow-md">
      <span className={toneBarClass} aria-hidden="true" />
      <p className="truncate text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {metric.label}
      </p>
      <p className="mt-1 text-xl font-semibold tracking-tight text-foreground">
        {formatMetricValue(metric.value, locale, metric.unit)}
      </p>
      {deltaLabel ? (
        <span className={deltaClass}>
          <TrendIcon className="mr-0.5 h-3.5 w-3.5" />
          {deltaLabel}
        </span>
      ) : null}
      {previousValueLabel ? (
        <p className="mt-0.5 text-xs text-muted-foreground">{previousValueLabel}</p>
      ) : null}
    </div>
  );
}

function EmptySectionCard({
  title,
  caption,
  minimalMode = false,
}: {
  title: string;
  caption: string;
  minimalMode?: boolean;
}) {
  const { t } = useI18n();

  return (
    <Card className="rounded-xl border bg-card shadow-sm">
      <CardHeader className="space-y-1 pb-3">
        <CardTitle className="text-lg font-semibold tracking-tight text-foreground">
          {title}
        </CardTitle>
        {!minimalMode && caption ? (
          <CardDescription className="text-sm">{caption}</CardDescription>
        ) : null}
      </CardHeader>
      <CardContent className="flex min-h-[14rem] items-center justify-center pt-0">
        <EmptyState
          icon={BarChart3}
          title={t('dashboard.noDataTitle')}
          description={t(
            'dashboard.noDataHint',
            undefined,
            'Данные появятся здесь, как только в выбранном периоде будут операции.',
          )}
        />
      </CardContent>
    </Card>
  );
}

function AnalyticsOverviewSection({
  title,
  caption,
  section,
  index,
  minimalMode = false,
}: AnalyticsSectionDescriptor & { index: number; minimalMode?: boolean }) {
  if (!section || !hasMeaningfulSectionData(section)) {
    return <EmptySectionCard title={title} caption={caption} minimalMode={minimalMode} />;
  }

  const hasPrimaryChart = section.charts.length > 0;
  const hasPrimaryBreakdown = section.breakdowns.length > 0;
  const primaryChart = hasPrimaryChart ? section.charts[0] : null;
  const primaryBreakdown = hasPrimaryBreakdown ? section.breakdowns[0] : null;
  const remainingCharts = section.charts.slice(hasPrimaryChart ? 1 : 0);
  const remainingBreakdowns = section.breakdowns.slice(hasPrimaryBreakdown ? 1 : 0);
  const useSeparatedContentLayout =
    section.metrics.length === 0 && section.charts.length > 0 && section.breakdowns.length > 0;

  return (
    <section id={`dashboard-section-${section.key}`} className="space-y-4">
      <div className="flex items-baseline gap-3">
        <span className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-muted text-xs font-semibold text-muted-foreground">
          {index + 1}
        </span>
        <div className="min-w-0">
          <h2 className="text-xl font-semibold tracking-tight text-foreground">{title}</h2>
          {!minimalMode && caption ? (
            <p className="mt-0.5 text-sm text-muted-foreground">{caption}</p>
          ) : null}
        </div>
      </div>

      <div className="space-y-4">
        {section.metrics.length > 0 ? (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {section.metrics.map((metric) => (
              <SectionMetricCard key={metric.key} metric={metric} />
            ))}
          </div>
        ) : null}

        {useSeparatedContentLayout ? (
          <>
            <div className={cn('grid gap-4', section.charts.length > 1 && 'xl:grid-cols-2')}>
              {section.charts.map((chart) => (
                <DashboardChartCard
                  key={chart.key}
                  chart={chart}
                  compact
                  minimalMode={minimalMode}
                />
              ))}
            </div>
            <div className={cn('grid gap-4', section.breakdowns.length > 1 && 'xl:grid-cols-2')}>
              {section.breakdowns.map((breakdown) => (
                <DashboardBreakdownCard
                  key={breakdown.key}
                  breakdown={breakdown}
                  compact
                  minimalMode={minimalMode}
                />
              ))}
            </div>
          </>
        ) : (
          <>
            {hasPrimaryChart || hasPrimaryBreakdown ? (
              <div className={cn('grid gap-4', hasPrimaryBreakdown && 'xl:grid-cols-2')}>
                {hasPrimaryChart && primaryChart ? (
                  <DashboardChartCard chart={primaryChart} compact minimalMode={minimalMode} />
                ) : null}
                {hasPrimaryBreakdown && primaryBreakdown ? (
                  <DashboardBreakdownCard
                    breakdown={primaryBreakdown}
                    compact
                    minimalMode={minimalMode}
                  />
                ) : null}
              </div>
            ) : null}

            {remainingCharts.length > 0 || remainingBreakdowns.length > 0 ? (
              <div className="grid gap-4 xl:grid-cols-2">
                {remainingCharts.map((chart) => (
                  <DashboardChartCard
                    key={chart.key}
                    chart={chart}
                    compact
                    minimalMode={minimalMode}
                  />
                ))}
                {remainingBreakdowns.map((breakdown) => (
                  <DashboardBreakdownCard
                    key={breakdown.key}
                    breakdown={breakdown}
                    compact
                    minimalMode={minimalMode}
                  />
                ))}
              </div>
            ) : null}
          </>
        )}
      </div>
    </section>
  );
}

export function AnalyticsDashboardView({
  title,
  badgeLabel,
  badgeTone,
  scopeLabel,
  periodLabel,
  updatedAtLabel,
  quickRangePresets,
  activeQuickRangeKey,
  onQuickRangeApply,
  departmentFilter,
  startDate,
  endDate,
  onDateRangeApply,
  onResetFilters,
  summaryMetrics,
  sections,
  minimalMode = false,
}: AnalyticsDashboardViewProps) {
  const { t } = useI18n();
  const visibleSections = sections.filter((section) => hasMeaningfulSectionData(section.section));
  const defaultQuickRangePreset = (() => {
    if (quickRangePresets.length === 0) {
      return null;
    }

    const matchingPreset = quickRangePresets.find((preset) => preset.key === 'last30');
    return matchingPreset ?? quickRangePresets[0];
  })();
  const isCustomRangeActive = activeQuickRangeKey === '';

  return (
    <section className="flex w-full flex-col gap-6 py-1 sm:py-2" data-tour="dashboard-page">
      <div className="flex flex-col gap-4 border-b pb-5" data-tour="dashboard-hero">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
            {title}
          </h1>
          <Badge className={cn('text-xs', getAnalyticsStatusClasses(badgeTone))}>
            {badgeLabel}
          </Badge>
        </div>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-muted-foreground">
          <HeroMetaPill
            icon={HERO_META_ICON_MAP.scope}
            label={t('dashboard.scopeTitle', undefined, 'Срез')}
            value={scopeLabel}
          />
          <HeroMetaPill
            icon={HERO_META_ICON_MAP.period}
            label={t('dashboard.periodTitle', undefined, 'Период')}
            value={periodLabel}
          />
          {updatedAtLabel ? (
            <HeroMetaPill
              icon={HERO_META_ICON_MAP.updated}
              label={t('dashboard.updatedAt')}
              value={updatedAtLabel}
            />
          ) : null}
        </div>
      </div>

      <Card className="rounded-xl border bg-card shadow-sm" data-tour="dashboard-filters">
        <CardContent
          className={cn('grid gap-4 p-4', 'xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]')}
        >
          <FilterPanelBlock label={t('dashboard.quickRangesTitle', undefined, 'Быстрый период')}>
            <div className="flex flex-wrap gap-2" data-tour="dashboard-quick-ranges">
              {quickRangePresets.map((preset) => {
                const isActive = activeQuickRangeKey === preset.key;

                return (
                  <Button
                    key={preset.key}
                    type="button"
                    variant={isActive ? 'default' : 'outline'}
                    className={cn(
                      'h-10 rounded-full px-4',
                      isActive
                        ? 'border-primary bg-primary text-primary-foreground shadow-[0_16px_36px_-28px_rgba(234,88,12,0.24)]'
                        : 'border-primary/24 hover:border-primary/36 bg-card text-muted-foreground hover:bg-card',
                    )}
                    onClick={() => onQuickRangeApply(preset)}
                  >
                    {preset.label}
                  </Button>
                );
              })}
            </div>
          </FilterPanelBlock>

          <div
            className={cn(
              'grid gap-3',
              departmentFilter
                ? 'md:grid-cols-2 2xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]'
                : 'md:grid-cols-[minmax(0,1fr)_auto]',
            )}
          >
            {departmentFilter ? (
              <FilterPanelBlock
                label={t('crud.departmentFilter')}
                className="h-full"
                dataTour="dashboard-department-filter"
              >
                <CustomSelect
                  value={departmentFilter.value}
                  onChange={departmentFilter.onChange}
                  options={[
                    {
                      value: '',
                      label: t('common.allDepartments'),
                    },
                    ...departmentFilter.options.map((department) => ({
                      value: department.id,
                      label: `${' '.repeat(department.depth * 2)}${department.label}`,
                      searchText: department.label,
                    })),
                  ]}
                  className="border-primary/24 flex h-11 w-full rounded-full border bg-card px-4 text-sm text-foreground shadow-none outline-none transition focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  placeholder={t('common.allDepartments')}
                  searchPlaceholder={t('common.search', undefined, 'Поиск')}
                  emptySearchLabel={t(
                    'crud.referenceNoOptions',
                    undefined,
                    'Подходящие варианты не найдены.',
                  )}
                />
              </FilterPanelBlock>
            ) : null}

            <FilterPanelBlock
              label={t('dashboard.dateRangeTitle', undefined, 'Период')}
              className="h-full"
            >
              <div data-tour="dashboard-date-filter">
                <AnalyticsDateFilter
                  startDate={startDate}
                  endDate={endDate}
                  onApply={onDateRangeApply}
                  resetRange={
                    defaultQuickRangePreset === null
                      ? undefined
                      : {
                          startDate: defaultQuickRangePreset.startDate,
                          endDate: defaultQuickRangePreset.endDate,
                        }
                  }
                  triggerClassName={cn(
                    'h-11 w-full justify-start border-primary/24 bg-card px-4 text-left shadow-none',
                    isCustomRangeActive && 'border-primary/45 bg-primary/5 text-foreground',
                  )}
                />
              </div>
            </FilterPanelBlock>

            <FilterPanelBlock
              label={t('dashboard.filterActionsTitle', undefined, 'Сброс')}
              className="h-full min-w-[11rem]"
            >
              <Button
                type="button"
                variant="outline"
                className="h-11 w-full rounded-full px-5"
                onClick={onResetFilters}
              >
                {t('common.reset')}
              </Button>
            </FilterPanelBlock>
          </div>
        </CardContent>
      </Card>

      {!minimalMode ? (
        <SectionJumpBar
          sections={visibleSections.map((section, index) => ({
            ...section,
            index,
          }))}
        />
      ) : null}

      {summaryMetrics.length > 0 ? (
        <div
          className="grid gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-5"
          data-tour="dashboard-summary"
        >
          {summaryMetrics.map((metric) => (
            <SummaryMetricCard key={metric.key} metric={metric} />
          ))}
        </div>
      ) : null}

      <div className="space-y-6" data-tour="dashboard-sections">
        {sections.map((section, index) => (
          <AnalyticsOverviewSection
            key={section.key}
            title={section.title}
            caption={section.caption}
            section={section.section}
            index={index}
            minimalMode={minimalMode}
          />
        ))}
      </div>
    </section>
  );
}
