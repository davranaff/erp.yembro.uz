import { type ComponentProps, useEffect, useMemo, useState } from 'react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  XAxis,
  YAxis,
} from 'recharts';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart';
import { Input } from '@/components/ui/input';
import type {
  DashboardBreakdown,
  DashboardChart,
  DashboardChartSeries,
  DashboardMetric,
} from '@/shared/api';
import { useI18n } from '@/shared/i18n';
import { cn } from '@/shared/lib/cn';

const CHART_COLORS = [
  'hsl(12 76% 50%)',
  'hsl(30 84% 52%)',
  'hsl(46 92% 54%)',
  'hsl(160 48% 38%)',
  'hsl(210 58% 48%)',
  'hsl(266 44% 54%)',
  'hsl(342 66% 52%)',
];

const FORCE_BAR_CHART_KEYS = new Set([
  'department_contribution',
  'department_revenue',
  'department_operations',
  'department_loss_rate',
  'expense_category_burn',
]);

export type DashboardHealthLevel = 'good' | 'warning' | 'bad' | 'neutral';

const POSITIVE_PERCENT_METRIC_KEYS = new Set([
  'grade_1_share',
  'hatch_rate',
  'shipment_rate',
  'turnover_rate',
  'process_rate',
  'first_sort_share',
]);

const NEGATIVE_PERCENT_METRIC_KEYS = new Set(['loss_rate']);

type ChartRow = {
  label: string;
} & Record<string, number | string>;

type TooltipFormatter = NonNullable<ComponentProps<typeof ChartTooltipContent>['formatter']>;

function formatValue(value: number, locale: string, unit?: string | null) {
  const formatter = new Intl.NumberFormat(locale, {
    maximumFractionDigits: Number.isInteger(value) ? 0 : 2,
  });
  const formatted = formatter.format(value);
  return unit ? `${formatted} ${unit}` : formatted;
}

function toNumericTooltipValues(value: unknown): number[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.map((entry) => Number(entry)).filter((entry) => Number.isFinite(entry));
}

function normalizeTooltipValue(value: unknown): number {
  const numericValues = toNumericTooltipValues(value);
  if (numericValues.length > 0) {
    return numericValues[numericValues.length - 1];
  }

  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? numericValue : 0;
}

function formatTooltipValue(value: unknown, locale: string, unit?: string | null): string {
  const numericValues = toNumericTooltipValues(value);
  if (numericValues.length > 1) {
    const firstValue = numericValues[0];
    const lastValue = numericValues[numericValues.length - 1];
    return `${formatValue(firstValue, locale, unit)} - ${formatValue(lastValue, locale, unit)}`;
  }

  return formatValue(normalizeTooltipValue(value), locale, unit);
}

function formatTooltipLabel(label: string) {
  if (/^\d{4}-\d{2}-\d{2}$/.test(label)) {
    const [year, month, day] = label.split('-');
    return `${day}.${month}.${year}`;
  }

  if (/^\d{4}-\d{2}$/.test(label)) {
    const [year, month] = label.split('-');
    return `${month}.${year}`;
  }

  return label;
}

function buildTooltipFormatter(
  locale: string,
  unit: string | null | undefined,
  series: DashboardChartSeries[],
): TooltipFormatter {
  const seriesLabelByKey = new Map(series.map((item) => [item.key, item.label]));
  const formatter: TooltipFormatter = (value, name, item, _index, payload) => {
    const safeValue = normalizeTooltipValue(value);
    const payloadRecord =
      typeof payload === 'object' && !Array.isArray(payload)
        ? (payload as Record<string, unknown>)
        : null;
    const itemPayloadCandidate =
      typeof item === 'object' && 'payload' in item
        ? (item as { payload?: unknown }).payload
        : null;
    const itemPayload =
      itemPayloadCandidate &&
      typeof itemPayloadCandidate === 'object' &&
      !Array.isArray(itemPayloadCandidate)
        ? (itemPayloadCandidate as Record<string, unknown>)
        : payloadRecord;

    let totalForShare = 0;
    if (itemPayload && typeof itemPayload.total === 'number') {
      totalForShare = itemPayload.total;
    } else if (payloadRecord) {
      totalForShare = Object.entries(payloadRecord).reduce((sum, [key, entryValue]) => {
        if (key === 'label' || key === 'name' || key === 'key') {
          return sum;
        }
        if (typeof entryValue !== 'number' || Number.isNaN(entryValue)) {
          return sum;
        }
        return sum + entryValue;
      }, 0);
    }

    const share = totalForShare > 0 ? (safeValue / totalForShare) * 100 : null;
    const rawName = typeof name === 'string' || typeof name === 'number' ? String(name) : '';
    const dataKey =
      typeof item === 'object' && 'dataKey' in item
        ? String((item as { dataKey?: unknown }).dataKey ?? '')
        : '';
    const payloadLabel =
      itemPayload && typeof itemPayload.label === 'string' ? itemPayload.label : null;
    const displayName =
      (dataKey ? seriesLabelByKey.get(dataKey) : null) ??
      (rawName ? seriesLabelByKey.get(rawName) : null) ??
      (payloadLabel && rawName.startsWith('slice-') ? payloadLabel : null) ??
      payloadLabel ??
      rawName;

    return (
      <div className="flex min-w-[11rem] max-w-[min(16rem,70vw)] items-center justify-between gap-3">
        <span className="text-muted-foreground">{displayName}</span>
        <span className="font-mono font-medium tabular-nums text-foreground">
          {formatTooltipValue(value, locale, unit)}
          {share !== null ? ` · ${share.toFixed(1)}%` : ''}
        </span>
      </div>
    );
  };

  return formatter;
}

function getMetricHealth(metric: DashboardMetric): DashboardHealthLevel {
  if (
    metric.status === 'good' ||
    metric.status === 'warning' ||
    metric.status === 'bad' ||
    metric.status === 'neutral'
  ) {
    return metric.status;
  }

  if (metric.unit !== '%') {
    return 'neutral';
  }

  if (NEGATIVE_PERCENT_METRIC_KEYS.has(metric.key)) {
    if (metric.value <= 5) {
      return 'good';
    }

    if (metric.value <= 12) {
      return 'warning';
    }

    return 'bad';
  }

  if (POSITIVE_PERCENT_METRIC_KEYS.has(metric.key)) {
    if (metric.value >= 85) {
      return 'good';
    }

    if (metric.value >= 60) {
      return 'warning';
    }

    return 'bad';
  }

  return 'neutral';
}

export function getDashboardHealthLevel(metrics: DashboardMetric[]): DashboardHealthLevel {
  const assessedMetrics = metrics
    .map((metric) => getMetricHealth(metric))
    .filter((level) => level !== 'neutral');

  if (assessedMetrics.length === 0) {
    return 'neutral';
  }

  const score = assessedMetrics.reduce((sum, level) => {
    if (level === 'good') {
      return sum + 2;
    }

    if (level === 'warning') {
      return sum + 1;
    }

    return sum;
  }, 0);
  const averageScore = score / assessedMetrics.length;

  if (averageScore >= 1.6) {
    return 'good';
  }

  if (averageScore >= 0.85) {
    return 'warning';
  }

  return 'bad';
}

function getHealthClasses(level: DashboardHealthLevel): string {
  if (level === 'good') {
    return 'border-emerald-200/80 bg-emerald-50/80 text-emerald-700';
  }

  if (level === 'warning') {
    return 'border-amber-200/80 bg-amber-50/80 text-amber-700';
  }

  if (level === 'bad') {
    return 'border-rose-200/80 bg-rose-50/80 text-rose-700';
  }

  return 'border-primary/24 bg-card text-muted-foreground';
}

function getUnifiedLabels(series: DashboardChartSeries[]) {
  const labels = new Map<string, number>();

  series.forEach((item) => {
    item.points.forEach((point) => {
      if (!labels.has(point.label)) {
        labels.set(point.label, labels.size);
      }
    });
  });

  return [...labels.keys()];
}

function getSeriesValue(series: DashboardChartSeries, label: string) {
  const match = series.points.find((point) => point.label === label);
  return match?.value ?? 0;
}

function buildChartData(series: DashboardChartSeries[]): ChartRow[] {
  return getUnifiedLabels(series).map((label) => {
    const row: ChartRow = { label };

    series.forEach((item) => {
      row[item.key] = getSeriesValue(item, label);
    });

    return row;
  });
}

function buildChartConfig(series: DashboardChartSeries[]): ChartConfig {
  return series.reduce<ChartConfig>((config, item, index) => {
    config[item.key] = {
      label: item.label,
      color: CHART_COLORS[index % CHART_COLORS.length],
    };

    return config;
  }, {});
}
function formatAxisTick(value: number, unit?: string | null) {
  if (unit === '%') {
    return `${Math.round(value)}%`;
  }

  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)}M`;
  }

  if (value >= 1_000) {
    return `${(value / 1_000).toFixed(0)}k`;
  }

  return String(value);
}

function formatCategoryTick(value: string, maxLength = 14) {
  const normalizedValue = value.trim();

  if (normalizedValue.length <= maxLength) {
    return normalizedValue;
  }

  return `${normalizedValue.slice(0, maxLength - 1)}…`;
}

function getSalesVolumeMetric(metrics: DashboardMetric[]): DashboardMetric | null {
  return (
    metrics.find((metric) => metric.key === 'sales_volume') ??
    metrics.find((metric) => metric.key === 'product_shipped') ??
    metrics.find((metric) => metric.key === 'client_shipments') ??
    null
  );
}

function EmptyChartState({ label }: { label: string }) {
  return (
    <div className="border-primary/32 flex h-[340px] items-center justify-center rounded-[22px] border border-dashed bg-card text-sm text-muted-foreground">
      {label}
    </div>
  );
}

function getChartKindLabel(chart: DashboardChart, t: ReturnType<typeof useI18n>['t']) {
  if (chart.type === 'line') {
    return t('dashboard.chartKindTrend', undefined, 'Тренд');
  }

  if (chart.type === 'stacked-bar') {
    return t('dashboard.chartKindComposition', undefined, 'Состав');
  }

  if (chart.series.length === 1) {
    return t('dashboard.chartKindComparison', undefined, 'Сравнение');
  }

  return t('dashboard.chartKindSnapshot', undefined, 'Срез');
}

function AreaGraph({
  chart,
  locale,
  emptyLabel,
}: {
  chart: DashboardChart;
  locale: string;
  emptyLabel: string;
}) {
  const data = buildChartData(chart.series);
  const config = buildChartConfig(chart.series);

  if (data.length === 0) {
    return <EmptyChartState label={emptyLabel} />;
  }

  return (
    <ChartContainer config={config} className="h-full w-full">
      <AreaChart data={data} margin={{ left: 8, right: 8, top: 12, bottom: 0 }}>
        <defs>
          {chart.series.map((series) => {
            const gradientId = `${chart.key}-${series.key}`.replace(/[^a-zA-Z0-9_-]/g, '-');

            return (
              <linearGradient
                key={`gradient-${series.key}`}
                id={`fill-${gradientId}`}
                x1="0"
                y1="0"
                x2="0"
                y2="1"
              >
                <stop offset="5%" stopColor={`var(--color-${series.key})`} stopOpacity={0.35} />
                <stop offset="95%" stopColor={`var(--color-${series.key})`} stopOpacity={0.03} />
              </linearGradient>
            );
          })}
        </defs>
        <CartesianGrid vertical={false} />
        <XAxis
          dataKey="label"
          tickLine={false}
          axisLine={false}
          tickMargin={10}
          minTickGap={24}
          tick={{ fontSize: 11 }}
          tickFormatter={(value) => formatCategoryTick(String(value))}
        />
        <YAxis
          tickLine={false}
          axisLine={false}
          width={42}
          tick={{ fontSize: 11 }}
          tickFormatter={(value) => formatAxisTick(Number(value), chart.unit)}
        />
        <ChartTooltip
          cursor={false}
          content={
            <ChartTooltipContent
              indicator="line"
              labelFormatter={(value) => formatTooltipLabel(String(value))}
              formatter={buildTooltipFormatter(locale, chart.unit, chart.series)}
            />
          }
        />
        <ChartLegend content={<ChartLegendContent />} />
        {chart.series.map((series) => (
          <Area
            key={series.key}
            dataKey={series.key}
            type="monotone"
            stroke={`var(--color-${series.key})`}
            fill={`url(#fill-${`${chart.key}-${series.key}`.replace(/[^a-zA-Z0-9_-]/g, '-')})`}
            fillOpacity={1}
            strokeWidth={2.5}
            dot={{ r: 2, strokeWidth: 0, fill: `var(--color-${series.key})` }}
            activeDot={{ r: 4 }}
          />
        ))}
      </AreaChart>
    </ChartContainer>
  );
}

function RadarGraph({
  chart,
  locale,
  emptyLabel,
}: {
  chart: DashboardChart;
  locale: string;
  emptyLabel: string;
}) {
  const data = buildChartData(chart.series);
  const config = buildChartConfig(chart.series);

  if (data.length === 0) {
    return <EmptyChartState label={emptyLabel} />;
  }

  return (
    <ChartContainer config={config} className="h-full w-full">
      <RadarChart data={data} outerRadius="70%">
        <PolarGrid />
        <PolarAngleAxis
          dataKey="label"
          tickLine={false}
          tick={{ fontSize: 11 }}
          tickFormatter={(value) => formatCategoryTick(String(value), 10)}
        />
        <PolarRadiusAxis
          tick={{ fontSize: 10 }}
          tickFormatter={(value) => formatAxisTick(Number(value), chart.unit)}
        />
        <ChartTooltip
          cursor={false}
          content={
            <ChartTooltipContent
              indicator="line"
              labelFormatter={(value) => formatTooltipLabel(String(value))}
              formatter={buildTooltipFormatter(locale, chart.unit, chart.series)}
            />
          }
        />
        <ChartLegend content={<ChartLegendContent />} />
        {chart.series.map((series) => (
          <Radar
            key={series.key}
            dataKey={series.key}
            stroke={`var(--color-${series.key})`}
            fill={`var(--color-${series.key})`}
            fillOpacity={0.16}
            strokeWidth={2}
          />
        ))}
      </RadarChart>
    </ChartContainer>
  );
}

function PieGraph({
  chart,
  locale,
  emptyLabel,
}: {
  chart: DashboardChart;
  locale: string;
  emptyLabel: string;
}) {
  const baseSeries = chart.series.length > 0 ? chart.series[0] : null;
  const total = baseSeries ? baseSeries.points.reduce((sum, point) => sum + point.value, 0) : 0;
  const pieData = (baseSeries?.points ?? []).map((point, index) => ({
    key: `slice-${index}`,
    label: point.label,
    value: point.value,
    total,
  }));

  if (pieData.length === 0) {
    return <EmptyChartState label={emptyLabel} />;
  }

  const pieConfig = pieData.reduce<ChartConfig>((config, slice, index) => {
    config[slice.key] = {
      label: slice.label,
      color: CHART_COLORS[index % CHART_COLORS.length],
    };
    return config;
  }, {});

  return (
    <ChartContainer config={pieConfig} className="h-full w-full">
      <PieChart>
        <ChartTooltip
          cursor={false}
          content={
            <ChartTooltipContent
              nameKey="key"
              labelFormatter={(_, payload) => {
                const firstPayload = payload.length > 0 ? payload[0].payload : null;
                return firstPayload && typeof firstPayload.label === 'string'
                  ? formatTooltipLabel(firstPayload.label)
                  : '';
              }}
              formatter={buildTooltipFormatter(locale, chart.unit, chart.series)}
            />
          }
        />
        <Pie
          data={pieData}
          dataKey="value"
          nameKey="label"
          innerRadius={60}
          outerRadius={112}
          strokeWidth={1.2}
          paddingAngle={1.5}
        >
          {pieData.map((slice) => (
            <Cell key={slice.key} fill={`var(--color-${slice.key})`} />
          ))}
        </Pie>
        <ChartLegend content={<ChartLegendContent nameKey="key" />} />
      </PieChart>
    </ChartContainer>
  );
}

function BarGraph({
  chart,
  locale,
  emptyLabel,
  stacked = false,
}: {
  chart: DashboardChart;
  locale: string;
  emptyLabel: string;
  stacked?: boolean;
}) {
  const data = buildChartData(chart.series);
  const config = buildChartConfig(chart.series);

  if (data.length === 0) {
    return <EmptyChartState label={emptyLabel} />;
  }

  return (
    <ChartContainer config={config} className="h-full w-full">
      <BarChart data={data} margin={{ left: 8, right: 8, top: 12, bottom: 0 }}>
        <CartesianGrid vertical={false} />
        <XAxis
          dataKey="label"
          tickLine={false}
          axisLine={false}
          tickMargin={10}
          minTickGap={24}
          tick={{ fontSize: 11 }}
          tickFormatter={(value) => formatCategoryTick(String(value))}
        />
        <YAxis
          tickLine={false}
          axisLine={false}
          width={42}
          tick={{ fontSize: 11 }}
          tickFormatter={(value) => formatAxisTick(Number(value), chart.unit)}
        />
        <ChartTooltip
          cursor={false}
          content={
            <ChartTooltipContent
              indicator="dot"
              labelFormatter={(value) => formatTooltipLabel(String(value))}
              formatter={buildTooltipFormatter(locale, chart.unit, chart.series)}
            />
          }
        />
        <ChartLegend content={<ChartLegendContent />} />
        {chart.series.map((series) => (
          <Bar
            key={series.key}
            dataKey={series.key}
            fill={`var(--color-${series.key})`}
            radius={stacked ? 0 : 10}
            stackId={stacked ? 'stack' : undefined}
          />
        ))}
      </BarChart>
    </ChartContainer>
  );
}

export function DashboardMetricGrid({ metrics }: { metrics: DashboardMetric[] }) {
  const { locale, t } = useI18n();

  return (
    <div className="grid gap-3 md:grid-cols-3">
      {metrics.map((metric) => {
        const health = getMetricHealth(metric);
        const healthLabel =
          health === 'good'
            ? t('common.good')
            : health === 'warning'
              ? t('common.warning')
              : health === 'bad'
                ? t('common.bad')
                : '';

        return (
          <div
            key={metric.key}
            className={cn(
              'border-primary/22 rounded-2xl border bg-card px-4 py-4 shadow-[0_18px_48px_-36px_rgba(15,23,42,0.16)]',
              health !== 'neutral' && 'ring-1 ring-inset',
              health === 'good' && 'ring-emerald-200/80',
              health === 'warning' && 'ring-amber-200/80',
              health === 'bad' && 'ring-rose-200/80',
            )}
          >
            <div className="flex items-start justify-between gap-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                {metric.label}
              </p>
              {health !== 'neutral' ? (
                <span
                  className={cn(
                    'inline-flex shrink-0 items-center rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em]',
                    getHealthClasses(health),
                  )}
                >
                  {healthLabel}
                </span>
              ) : null}
            </div>
            <p className="mt-3 text-3xl font-semibold tracking-tight text-foreground">
              {formatValue(metric.value, locale, metric.unit)}
            </p>
          </div>
        );
      })}
      <RevenueCalculatorCard metrics={metrics} />
    </div>
  );
}

function RevenueCalculatorCard({ metrics }: { metrics: DashboardMetric[] }) {
  const { locale, t } = useI18n();
  const revenueMetric = useMemo(
    () => metrics.find((metric) => metric.key === 'sales_revenue') ?? null,
    [metrics],
  );
  const averagePriceMetric = useMemo(
    () => metrics.find((metric) => metric.key === 'avg_sale_price') ?? null,
    [metrics],
  );
  const salesVolumeMetric = useMemo(() => getSalesVolumeMetric(metrics), [metrics]);
  const [inputValue, setInputValue] = useState('');

  useEffect(() => {
    if (!salesVolumeMetric) {
      setInputValue('');
      return;
    }

    setInputValue(String(Math.round(salesVolumeMetric.value)));
  }, [salesVolumeMetric]);

  if (!revenueMetric || !averagePriceMetric || !salesVolumeMetric) {
    return null;
  }

  const normalizedQuantity = Number.isFinite(Number(inputValue))
    ? Math.max(Number(inputValue), 0)
    : 0;
  const estimatedRevenue = normalizedQuantity * averagePriceMetric.value;

  return (
    <Card className="border-accent/28 bg-card shadow-[0_24px_64px_-48px_rgba(15,23,42,0.16)] md:col-span-3">
      <CardHeader className="space-y-1">
        <CardTitle className="text-base font-semibold text-foreground">
          {t('dashboard.revenueCalculatorTitle')}
        </CardTitle>
        <CardDescription>{t('dashboard.revenueCalculatorDescription')}</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1fr)]">
        <div className="space-y-2">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            {t('dashboard.calculationVolume')}
          </p>
          <div className="border-primary/22 flex items-center gap-3 rounded-2xl border bg-card px-4 py-3">
            <Input
              type="number"
              min="0"
              step="1"
              value={inputValue}
              onChange={(event) => setInputValue(event.target.value)}
              className="h-11 border-0 bg-transparent px-0 shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
            />
            <span className="shrink-0 text-sm font-medium text-muted-foreground">
              {salesVolumeMetric.unit ?? ''}
            </span>
          </div>
        </div>
        <div className="border-accent/24 rounded-2xl border bg-card px-4 py-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            {t('dashboard.averagePrice')}
          </p>
          <p className="mt-3 text-2xl font-semibold tracking-tight text-foreground">
            {formatValue(averagePriceMetric.value, locale, averagePriceMetric.unit)}
          </p>
        </div>
        <div className="border-primary/24 rounded-2xl border bg-card px-4 py-4 shadow-[0_14px_34px_-28px_rgba(234,88,12,0.14)]">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            {t('dashboard.estimatedRevenue')}
          </p>
          <p className="mt-3 text-2xl font-semibold tracking-tight text-foreground">
            {formatValue(estimatedRevenue, locale, revenueMetric.unit)}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

export function DashboardChartCard({
  chart,
  compact = false,
  minimalMode = false,
}: {
  chart: DashboardChart;
  compact?: boolean;
  minimalMode?: boolean;
}) {
  const { locale, t } = useI18n();
  const pointCount = Math.max(...chart.series.map((series) => series.points.length), 0);
  const shouldForceBars =
    FORCE_BAR_CHART_KEYS.has(chart.key) ||
    chart.key.endsWith('_expense_categories') ||
    chart.key.endsWith('_cash_accounts');
  const shouldUsePie =
    !shouldForceBars && chart.type === 'bar' && chart.series.length === 1 && pointCount <= 10;
  const shouldUseRadar =
    !shouldForceBars &&
    !shouldUsePie &&
    chart.type !== 'line' &&
    chart.series.length >= 2 &&
    chart.series.length <= 6 &&
    pointCount > 0 &&
    pointCount <= 12;
  const shouldSpanWide =
    chart.type === 'stacked-bar' || chart.series.length >= 4 || pointCount >= 7;
  const chartHeightClass = cn(
    'w-full',
    shouldSpanWide ? 'h-[320px] sm:h-[360px] xl:h-[420px]' : 'h-[260px] sm:h-[300px] xl:h-[340px]',
  );
  const chartKindLabel = getChartKindLabel(chart, t);

  let content = <EmptyChartState label={t('common.noData')} />;

  if (shouldUsePie) {
    content = <PieGraph chart={chart} locale={locale} emptyLabel={t('common.noData')} />;
  } else if (chart.type === 'line') {
    content = <AreaGraph chart={chart} locale={locale} emptyLabel={t('common.noData')} />;
  } else if (shouldUseRadar) {
    content = <RadarGraph chart={chart} locale={locale} emptyLabel={t('common.noData')} />;
  } else if (chart.type === 'stacked-bar') {
    content = <BarGraph chart={chart} locale={locale} emptyLabel={t('common.noData')} stacked />;
  } else {
    content = <BarGraph chart={chart} locale={locale} emptyLabel={t('common.noData')} />;
  }

  return (
    <Card
      className={cn(
        'border-primary/24 bg-card shadow-[0_24px_64px_-48px_rgba(15,23,42,0.16)]',
        shouldSpanWide && 'xl:col-span-2',
      )}
    >
      <CardHeader className={cn(compact ? 'space-y-0 pb-4' : 'space-y-1')}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <Badge
                variant="outline"
                className="border-primary/18 rounded-full bg-background px-2.5 py-0.5 text-[10px] text-muted-foreground"
              >
                {chartKindLabel}
              </Badge>
              {chart.series.length > 1 ? (
                <Badge
                  variant="outline"
                  className="border-primary/18 rounded-full bg-background px-2.5 py-0.5 text-[10px] text-muted-foreground"
                >
                  {chart.series.length} {t('dashboard.chartSeriesLabelShort', undefined, 'сер.')}
                </Badge>
              ) : null}
            </div>
            <CardTitle className="text-base font-semibold text-foreground">{chart.title}</CardTitle>
            {!compact && !minimalMode && chart.description ? (
              <CardDescription>{chart.description}</CardDescription>
            ) : null}
          </div>
        </div>
      </CardHeader>
      <CardContent className="px-4 pb-4 pt-0 sm:px-6 sm:pb-6">
        <div className="border-primary/14 rounded-[24px] border bg-background/50 p-2 sm:p-3">
          <div className={chartHeightClass}>{content}</div>
        </div>
      </CardContent>
    </Card>
  );
}

export function DashboardBreakdownCard({
  breakdown,
  compact = false,
  minimalMode = false,
}: {
  breakdown: DashboardBreakdown;
  compact?: boolean;
  minimalMode?: boolean;
}) {
  const { locale, t } = useI18n();
  const breakdownUnit = (breakdown as { unit?: string | null }).unit;
  const hasTopItem = breakdown.items.length > 0;
  const topItem = hasTopItem ? breakdown.items[0] : null;
  const remainingItems = breakdown.items.slice(hasTopItem ? 1 : 0);

  return (
    <Card className="border-accent/28 bg-card shadow-[0_24px_64px_-48px_rgba(15,23,42,0.16)]">
      <CardHeader className={cn(compact ? 'space-y-0 pb-4' : 'space-y-1')}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <Badge
                variant="outline"
                className="border-primary/18 rounded-full bg-background px-2.5 py-0.5 text-[10px] text-muted-foreground"
              >
                {t('dashboard.breakdownKindLabel', undefined, 'Список')}
              </Badge>
              <Badge
                variant="outline"
                className="border-primary/18 rounded-full bg-background px-2.5 py-0.5 text-[10px] text-muted-foreground"
              >
                {breakdown.items.length} {t('dashboard.breakdownLabelShort', undefined, 'поз.')}
              </Badge>
            </div>
            <CardTitle className="text-base font-semibold text-foreground">
              {breakdown.title}
            </CardTitle>
            {!compact && !minimalMode && breakdown.description ? (
              <CardDescription>{breakdown.description}</CardDescription>
            ) : null}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {breakdown.items.length === 0 ? (
          <div className="border-accent/34 rounded-[22px] border border-dashed bg-card px-4 py-8 text-sm text-muted-foreground">
            {t('common.noData')}
          </div>
        ) : (
          <>
            {hasTopItem && topItem ? (
              <div className="border-primary/16 rounded-[22px] border bg-background/60 px-4 py-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                  {t('dashboard.topItemLabel', undefined, 'Главная позиция')}
                </p>
                <div className="mt-2 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0 space-y-1">
                    <p className="text-sm font-medium text-foreground">{topItem.label}</p>
                    {!minimalMode && topItem.caption ? (
                      <p className="text-xs leading-5 text-muted-foreground">{topItem.caption}</p>
                    ) : null}
                  </div>
                  <span className="font-mono text-sm font-medium tabular-nums text-foreground">
                    {formatValue(
                      topItem.value,
                      locale,
                      (topItem as { unit?: string | null }).unit ?? breakdownUnit,
                    )}
                  </span>
                </div>
              </div>
            ) : null}
            {remainingItems.map((item, index) => {
              const itemUnit = (item as { unit?: string | null }).unit ?? breakdownUnit;

              return (
                <div
                  key={`${breakdown.key}-${item.label}-${index}`}
                  className="flex flex-col gap-3 rounded-[22px] border border-primary/20 bg-card px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-[11px] font-semibold text-primary">
                      {index + 2}
                    </span>
                    <div className="min-w-0 space-y-1">
                      <span className="text-sm text-foreground">{item.label}</span>
                      {!minimalMode && item.caption ? (
                        <p className="text-xs leading-5 text-muted-foreground">{item.caption}</p>
                      ) : null}
                    </div>
                  </div>
                  <span className="font-mono text-sm font-medium tabular-nums text-foreground">
                    {formatValue(item.value, locale, itemUnit)}
                  </span>
                </div>
              );
            })}
          </>
        )}
      </CardContent>
    </Card>
  );
}
