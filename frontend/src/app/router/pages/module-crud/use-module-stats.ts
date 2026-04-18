import { useEffect, useMemo } from 'react';

import {
  buildAnalyticsQuickRangePresets,
  formatAnalyticsPeriodLabel,
} from '@/app/router/ui/analytics-dashboard-view';
import { getDashboardHealthLevel } from '@/app/router/ui/dashboard-analytics';
import { buildModuleAnalyticsPresentation } from '@/app/router/ui/module-analytics-presentation';
import { getDashboardAnalytics } from '@/shared/api/dashboard';
import { baseQueryKeys } from '@/shared/api/query-keys';
import { useApiQuery } from '@/shared/api/react-query';
import { translateDashboardAnalytics } from '@/shared/i18n';
import type { TranslateFn } from '@/shared/i18n/types';

import type { ModuleViewMode } from '../module-crud-page.helpers';

export interface UseModuleStatsOptions {
  t: TranslateFn;
  locale: string;
  today: Date;
  effectiveStartDate: string;
  effectiveEndDate: string;
  requestedPeriodKey: string;
  selectedDepartmentId: string;
  supportsStatistics: boolean;
  activeView: ModuleViewMode;
  canOpenModuleAnalytics: boolean;
  moduleStatsSectionKey: string;
  moduleLabel: string;
  setSearchParams: (updater: (current: URLSearchParams) => URLSearchParams) => void;
}

export function useModuleStats(options: UseModuleStatsOptions) {
  const {
    t,
    locale,
    today,
    effectiveStartDate,
    effectiveEndDate,
    requestedPeriodKey,
    selectedDepartmentId,
    supportsStatistics,
    activeView,
    canOpenModuleAnalytics,
    moduleStatsSectionKey,
    moduleLabel,
    setSearchParams,
  } = options;

  const moduleStatsQuery = useApiQuery({
    queryKey: [
      ...baseQueryKeys.dashboard.stats,
      effectiveStartDate,
      effectiveEndDate,
      selectedDepartmentId,
    ],
    queryFn: () =>
      getDashboardAnalytics({
        startDate: effectiveStartDate,
        endDate: effectiveEndDate,
        departmentId: selectedDepartmentId || undefined,
      }),
    enabled: supportsStatistics && activeView === 'stats' && canOpenModuleAnalytics,
  });

  const translatedModuleStats = useMemo(
    () => (moduleStatsQuery.data ? translateDashboardAnalytics(moduleStatsQuery.data, t) : null),
    [moduleStatsQuery.data, t],
  );

  const moduleStatsModule = useMemo(
    () =>
      moduleStatsSectionKey
        ? (translatedModuleStats?.department_dashboard?.modules.find(
            (module) => module.key === moduleStatsSectionKey,
          ) ?? null)
        : null,
    [moduleStatsSectionKey, translatedModuleStats],
  );

  const moduleStatsSection = useMemo(
    () =>
      moduleStatsModule
        ? {
            key: moduleStatsModule.key,
            title: moduleStatsModule.title,
            description: moduleStatsModule.description ?? null,
            metrics: moduleStatsModule.kpis,
            charts: moduleStatsModule.charts,
            breakdowns:
              (moduleStatsModule.alerts ?? []).length > 0
                ? [
                    ...moduleStatsModule.tables,
                    {
                      key: 'module_alerts',
                      title: t(
                        'dashboardData.sections.module_alerts.breakdowns.module_alerts.title',
                        undefined,
                        'Операционные alerts',
                      ),
                      description: t(
                        'dashboardData.sections.module_alerts.breakdowns.module_alerts.description',
                        undefined,
                        'Ключевые сигналы по выбранному модулю.',
                      ),
                      items: (moduleStatsModule.alerts ?? []).map((alert, index) => ({
                        key: `${alert.key}-${index}`,
                        label: alert.title,
                        value: alert.value ?? 0,
                        unit: alert.unit ?? null,
                        caption: alert.message,
                      })),
                    },
                  ]
                : moduleStatsModule.tables,
          }
        : null,
    [moduleStatsModule, t],
  );

  const quickRangePresets = useMemo(() => buildAnalyticsQuickRangePresets(t, today), [t, today]);
  const validQuickRangeKeys = useMemo(
    () => new Set(quickRangePresets.map((preset) => preset.key)),
    [quickRangePresets],
  );

  const activeQuickRangeKey = useMemo(() => {
    const matchingPresetKeys = quickRangePresets
      .filter(
        (preset) => preset.startDate === effectiveStartDate && preset.endDate === effectiveEndDate,
      )
      .map((preset) => preset.key);

    if (
      validQuickRangeKeys.has(requestedPeriodKey) &&
      matchingPresetKeys.includes(requestedPeriodKey)
    ) {
      return requestedPeriodKey;
    }

    return matchingPresetKeys.length === 1 ? matchingPresetKeys[0] : '';
  }, [
    effectiveEndDate,
    effectiveStartDate,
    quickRangePresets,
    requestedPeriodKey,
    validQuickRangeKeys,
  ]);

  useEffect(() => {
    if (!requestedPeriodKey) {
      return;
    }

    if (requestedPeriodKey === activeQuickRangeKey) {
      return;
    }

    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.delete('period');
      return next;
    });
  }, [activeQuickRangeKey, requestedPeriodKey, setSearchParams]);

  const selectedStatsPeriodLabel = useMemo(
    () => formatAnalyticsPeriodLabel(t, effectiveStartDate, effectiveEndDate),
    [effectiveEndDate, effectiveStartDate, t],
  );

  const moduleStatsHasData = Boolean(
    moduleStatsSection &&
    (moduleStatsSection.metrics.some((metric) => metric.value > 0) ||
      moduleStatsSection.charts.some((chart) =>
        chart.series.some((series) => series.points.length > 0),
      ) ||
      moduleStatsSection.breakdowns.some((breakdown) => breakdown.items.length > 0)),
  );

  const moduleStatsHealth = getDashboardHealthLevel(moduleStatsSection?.metrics ?? []);
  const moduleStatsHealthLabel =
    moduleStatsHealth === 'good'
      ? t('common.good')
      : moduleStatsHealth === 'warning'
        ? t('common.warning')
        : moduleStatsHealth === 'bad'
          ? t('common.bad')
          : t('common.neutral');
  const moduleStatsBadgeTone = moduleStatsHasData ? moduleStatsHealth : 'neutral';
  const moduleStatsBadgeLabel = moduleStatsHasData ? moduleStatsHealthLabel : t('common.neutral');

  const statsUpdatedAtLabel = moduleStatsQuery.data
    ? new Intl.DateTimeFormat(locale, {
        dateStyle: 'short',
        timeStyle: 'short',
      }).format(new Date(moduleStatsQuery.data.generatedAt))
    : '';

  const moduleAnalyticsPresentation = useMemo(
    () =>
      moduleStatsModule
        ? buildModuleAnalyticsPresentation(moduleStatsModule, moduleLabel, t)
        : { summaryMetrics: [], sections: [] },
    [moduleLabel, moduleStatsModule, t],
  );

  return {
    moduleStatsQuery,
    moduleStatsSection,
    moduleStatsHasData,
    moduleStatsBadgeTone,
    moduleStatsBadgeLabel,
    selectedStatsPeriodLabel,
    statsUpdatedAtLabel,
    quickRangePresets,
    activeQuickRangeKey,
    moduleAnalyticsPresentation,
  };
}
