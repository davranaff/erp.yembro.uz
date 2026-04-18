import {
  AnalyticsDashboardView,
  type AnalyticsQuickRangePreset,
} from '@/app/router/ui/analytics-dashboard-view';
import { ErrorNotice } from '@/components/ui/error-notice';
import { InlineLoader } from '@/components/ui/inline-loader';

import type { ComponentProps } from 'react';

type TranslateFn = (
  key: string,
  params?: Record<string, string | number>,
  fallback?: string,
) => string;

type DashboardProps = ComponentProps<typeof AnalyticsDashboardView>;

export interface AnalyticsStatsViewProps {
  t: TranslateFn;
  isLoading: boolean;
  error: unknown;
  hasSection: boolean;
  dashboardProps: Omit<DashboardProps, 'minimalMode' | 'onQuickRangeApply'> & {
    onQuickRangeApply: (preset: AnalyticsQuickRangePreset) => void;
  };
}

export function AnalyticsStatsView({
  t,
  isLoading,
  error,
  hasSection,
  dashboardProps,
}: AnalyticsStatsViewProps) {
  return (
    <div className="space-y-6">
      {isLoading ? (
        <div className="rounded-[28px] border border-border/75 bg-card shadow-[0_24px_72px_-48px_rgba(15,23,42,0.14)]">
          <InlineLoader label={t('dashboard.loadingAnalytics', undefined, 'Готовим аналитику…')} />
        </div>
      ) : null}
      {error ? (
        <ErrorNotice
          error={error}
          className="rounded-[28px] shadow-[0_18px_48px_-34px_rgba(244,63,94,0.16)]"
        />
      ) : null}
      {!isLoading && !error && !hasSection ? (
        <div className="rounded-[28px] border border-border/75 bg-card px-6 py-12 text-center text-sm text-muted-foreground shadow-[0_24px_72px_-48px_rgba(15,23,42,0.14)]">
          {t('dashboard.moduleUnavailable')}
        </div>
      ) : null}
      {!isLoading && !error && hasSection ? (
        <AnalyticsDashboardView {...dashboardProps} minimalMode />
      ) : null}
    </div>
  );
}
