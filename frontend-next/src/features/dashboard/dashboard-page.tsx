import { useQuery } from '@tanstack/react-query';
import { ArrowDownRight, ArrowUpRight, BarChart3, RefreshCw } from 'lucide-react';
import { useMemo, useState } from 'react';

import { cn } from '@/lib/cn';
import { getDashboardAnalytics, type DashboardModule } from '@/shared/api/dashboard';
import { useAuthStore } from '@/shared/auth/auth-store';
import { useI18n } from '@/shared/i18n/i18n';
import { Button } from '@/shared/ui/button';
import { EmptyState } from '@/shared/ui/empty-state';
import { Spinner } from '@/shared/ui/spinner';

import { TopBar } from '../shell/top-bar';

type RangePreset = '7d' | '30d' | '90d' | 'ytd';

const PRESETS: { key: RangePreset; labelRu: string }[] = [
  { key: '7d', labelRu: '7д' },
  { key: '30d', labelRu: '30д' },
  { key: '90d', labelRu: '90д' },
  { key: 'ytd', labelRu: 'YTD' },
];

function computeRange(preset: RangePreset): { startDate: string; endDate: string } {
  const today = new Date();
  const end = today.toISOString().slice(0, 10);
  const start = new Date(today);
  if (preset === '7d') start.setDate(today.getDate() - 6);
  else if (preset === '30d') start.setDate(today.getDate() - 29);
  else if (preset === '90d') start.setDate(today.getDate() - 89);
  else start.setMonth(0, 1);
  return { startDate: start.toISOString().slice(0, 10), endDate: end };
}

export function DashboardPage() {
  const { t } = useI18n();
  const hasAnyPermission = useAuthStore((s) => s.hasAnyPermission);
  const [preset, setPreset] = useState<RangePreset>('30d');
  const range = useMemo(() => computeRange(preset), [preset]);

  const canAccess = hasAnyPermission(['dashboard.read']);

  const { data, isLoading, isFetching, refetch, error } = useQuery({
    queryKey: ['dashboard-analytics', range.startDate, range.endDate],
    queryFn: () => getDashboardAnalytics(range),
    enabled: canAccess,
  });

  const modules = data?.department_dashboard?.modules ?? [];

  return (
    <>
      <TopBar
        title={t('dashboard.title')}
        right={
          <div className="flex items-center gap-1">
            <div className="flex h-7 items-center rounded border border-line bg-bg-subtle text-xs">
              {PRESETS.map((p) => (
                <button
                  key={p.key}
                  type="button"
                  onClick={() => setPreset(p.key)}
                  className={cn(
                    'h-7 px-2 text-ink-muted first:rounded-l last:rounded-r hover:text-ink',
                    preset === p.key && 'bg-bg-inset text-ink',
                  )}
                >
                  {p.labelRu}
                </button>
              ))}
            </div>
            <Button variant="ghost" size="sm" onClick={() => refetch()} title={t('common.refresh')}>
              <RefreshCw className={cn('h-3 w-3', isFetching && 'animate-spin')} />
            </Button>
          </div>
        }
      />

      <div className="flex flex-1 min-h-0 overflow-y-auto">
        <div className="flex w-full flex-col gap-4 p-4">
          {!canAccess ? (
            <EmptyState icon={BarChart3} title={t('dashboard.noPermission')} />
          ) : isLoading ? (
            <div className="flex items-center gap-2 text-xs text-ink-muted">
              <Spinner />
              <span>{t('dashboard.loading')}</span>
            </div>
          ) : error ? (
            <EmptyState
              icon={BarChart3}
              title={t('common.error')}
              description={(error as Error).message}
              action={
                <Button size="sm" onClick={() => refetch()}>
                  {t('common.retry')}
                </Button>
              }
            />
          ) : modules.length === 0 ? (
            <EmptyState icon={BarChart3} title={t('dashboard.empty')} />
          ) : (
            modules.map((module) => <ModuleBlock key={module.key} module={module} />)
          )}
        </div>
      </div>
    </>
  );
}

function ModuleBlock({ module }: { module: DashboardModule }) {
  return (
    <section className="overflow-hidden rounded-lg border border-line bg-bg-surface">
      <header className="flex items-center justify-between border-b border-line bg-bg-subtle/50 px-3 py-2">
        <div>
          <h2 className="text-sm font-medium">{module.title}</h2>
          {module.description ? (
            <p className="text-2xs text-ink-muted">{module.description}</p>
          ) : null}
        </div>
      </header>

      {module.kpis.length > 0 ? (
        <div className="grid grid-cols-2 gap-px bg-line sm:grid-cols-3 lg:grid-cols-4">
          {module.kpis.map((kpi) => (
            <div key={kpi.key} className="flex flex-col gap-1 bg-bg-surface p-3">
              <div className="text-2xs uppercase tracking-wide text-ink-muted">{kpi.title}</div>
              <div className="flex items-baseline gap-1.5">
                <span className="font-mono text-xl tabular-nums text-ink">
                  {formatNumber(kpi.value)}
                </span>
                {kpi.unit ? (
                  <span className="text-xs text-ink-muted">{kpi.unit}</span>
                ) : null}
              </div>
              {typeof kpi.change_percent === 'number' ? (
                <div
                  className={cn(
                    'inline-flex items-center gap-1 font-mono text-2xs',
                    kpi.change_percent > 0 ? 'text-ok' : kpi.change_percent < 0 ? 'text-danger' : 'text-ink-muted',
                  )}
                >
                  {kpi.change_percent > 0 ? (
                    <ArrowUpRight className="h-3 w-3" />
                  ) : kpi.change_percent < 0 ? (
                    <ArrowDownRight className="h-3 w-3" />
                  ) : null}
                  <span>{formatChange(kpi.change_percent)}</span>
                </div>
              ) : kpi.caption ? (
                <div className="text-2xs text-ink-muted">{kpi.caption}</div>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}

      {module.charts.length > 0 ? (
        <div className="grid grid-cols-1 gap-px border-t border-line bg-line lg:grid-cols-2">
          {module.charts.map((chart) => (
            <div key={chart.key} className="flex flex-col gap-2 bg-bg-surface p-3">
              <div>
                <div className="text-sm font-medium text-ink">{chart.title}</div>
                {chart.description ? (
                  <div className="text-2xs text-ink-muted">{chart.description}</div>
                ) : null}
              </div>
              <MiniChart chart={chart} />
            </div>
          ))}
        </div>
      ) : null}

      {module.tables.length > 0 ? (
        <div className="grid grid-cols-1 gap-px border-t border-line bg-line lg:grid-cols-2">
          {module.tables.map((table) => (
            <div key={table.key} className="flex flex-col bg-bg-surface">
              <div className="border-b border-line px-3 py-2">
                <div className="text-sm font-medium">{table.title}</div>
                {table.description ? (
                  <div className="text-2xs text-ink-muted">{table.description}</div>
                ) : null}
              </div>
              <div className="flex flex-col">
                {table.items.length === 0 ? (
                  <div className="px-3 py-3 text-xs text-ink-muted">—</div>
                ) : (
                  table.items.slice(0, 8).map((item) => (
                    <div
                      key={item.key}
                      className="flex items-center justify-between border-b border-line-soft px-3 py-1.5 last:border-b-0"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-xs text-ink">{item.label}</div>
                        {item.caption ? (
                          <div className="truncate text-2xs text-ink-muted">{item.caption}</div>
                        ) : null}
                      </div>
                      <div className="ml-3 font-mono text-xs tabular-nums text-ink-soft">
                        {formatNumber(item.value)}
                        {item.unit ? <span className="ml-1 text-ink-faint">{item.unit}</span> : null}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          ))}
        </div>
      ) : null}

      {module.alerts && module.alerts.length > 0 ? (
        <div className="flex flex-col gap-px border-t border-line bg-line">
          {module.alerts.map((alert) => (
            <div
              key={alert.key}
              className={cn(
                'flex items-start gap-2 px-3 py-2 text-xs',
                alert.tone === 'danger' && 'bg-danger-soft/30 text-ink',
                alert.tone === 'warning' && 'bg-warn-soft/30 text-ink',
                (!alert.tone || alert.tone === 'info') && 'bg-bg-surface text-ink-soft',
              )}
            >
              <div className="min-w-0 flex-1">
                <div className="font-medium">{alert.title}</div>
                <div className="text-ink-muted">{alert.message}</div>
              </div>
              {typeof alert.value === 'number' ? (
                <div className="font-mono text-xs tabular-nums">
                  {formatNumber(alert.value)}
                  {alert.unit ? <span className="ml-1 text-ink-faint">{alert.unit}</span> : null}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}

interface MiniChartProps {
  chart: DashboardModule['charts'][number];
}

function MiniChart({ chart }: MiniChartProps) {
  const series = chart.series[0];
  if (!series || series.points.length === 0) {
    return <div className="h-20 rounded border border-dashed border-line-soft text-center text-2xs text-ink-muted flex items-center justify-center">—</div>;
  }
  const max = Math.max(...series.points.map((p) => p.value), 1);

  if (chart.type === 'line') {
    const width = 240;
    const height = 64;
    const step = series.points.length > 1 ? width / (series.points.length - 1) : 0;
    const path = series.points
      .map((p, i) => {
        const x = i * step;
        const y = height - (p.value / max) * height;
        return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
      })
      .join(' ');
    const area = `${path} L ${width} ${height} L 0 ${height} Z`;
    return (
      <svg viewBox={`0 0 ${width} ${height}`} className="h-20 w-full">
        <path d={area} fill="rgb(var(--accent))" opacity={0.12} />
        <path d={path} fill="none" stroke="rgb(var(--accent))" strokeWidth={1.5} />
      </svg>
    );
  }

  // bar or stacked-bar (render top series as bars)
  return (
    <div className="flex h-20 items-end gap-0.5">
      {series.points.map((p, i) => (
        <div key={`${p.label}-${i}`} className="flex-1" style={{ height: `${(p.value / max) * 100}%` }}>
          <div className="h-full w-full rounded-sm bg-accent/60" title={`${p.label}: ${p.value}`} />
        </div>
      ))}
    </div>
  );
}

function formatNumber(value: number): string {
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (Math.abs(value) >= 10_000) return `${(value / 1_000).toFixed(1)}K`;
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 1 }).format(value);
}

function formatChange(value: number): string {
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(1)}%`;
}
