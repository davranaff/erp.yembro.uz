import { format, startOfDay, subDays } from 'date-fns';
import { RefreshCw } from 'lucide-react';
import { useEffect, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import {
  AnalyticsDashboardView,
  buildAnalyticsQuickRangePresets,
  formatAnalyticsPeriodLabel,
  type AnalyticsSectionDescriptor,
  type AnalyticsQuickRangePreset,
  type AnalyticsStatusTone,
} from '@/app/router/ui/analytics-dashboard-view';
import { RouteStatusScreen } from '@/app/router/ui/route-status-screen';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { ErrorNotice } from '@/components/ui/error-notice';
import {
  baseQueryKeys,
  getDashboardOverview,
  useApiQuery,
  type DashboardBreakdown,
  type DashboardChart,
} from '@/shared/api';
import {
  listVisibleDepartments,
  type CrudListResponse,
  type CrudRecord,
} from '@/shared/api/backend-crud';
import { canAccessDashboard, useAuthStore } from '@/shared/auth';
import { useI18n } from '@/shared/i18n';
import { translateDashboardOverview } from '@/shared/i18n/dashboard';
import { buildDepartmentTree, flattenDepartmentTree } from '@/shared/lib/departments';
import { isValidUuid } from '@/shared/lib/uuid';
import { useWorkspaceStore, type BackendModuleConfig } from '@/shared/workspace';

const EXECUTIVE_SUMMARY_METRIC_ORDER = ['operating_profit', 'net_cashflow', 'health_index'];

const EXECUTIVE_DEPARTMENT_BREAKDOWN_KEYS = ['departments_performance'];
const EXECUTIVE_RISK_BREAKDOWN_KEYS = ['top_risk_summary'];

type DepartmentRecord = CrudRecord & {
  id?: string;
  name?: string;
  code?: string;
  module_key?: string;
  parent_department_id?: string | null;
};

const EMPTY_AUTH_LIST: string[] = [];
const dateParamPattern = /^\d{4}-\d{2}-\d{2}$/;

const getWorkspaceModuleConfig = (
  moduleMap: Record<string, BackendModuleConfig>,
  moduleKey: string,
): BackendModuleConfig | null =>
  moduleKey && Object.prototype.hasOwnProperty.call(moduleMap, moduleKey)
    ? moduleMap[moduleKey]
    : null;

const isValidDateParam = (value: string): boolean => {
  if (!dateParamPattern.test(value)) {
    return false;
  }

  return !Number.isNaN(new Date(`${value}T00:00:00`).getTime());
};

const normalizeDateRangeValues = (range: { startDate?: string; endDate?: string }) => {
  const singleDate = range.startDate || range.endDate;

  if (singleDate && (!range.startDate || !range.endDate)) {
    return {
      startDate: singleDate,
      endDate: singleDate,
    };
  }

  if (range.startDate && range.endDate && range.startDate > range.endDate) {
    return {
      startDate: range.endDate,
      endDate: range.startDate,
    };
  }

  return range;
};

const resolveActiveQuickRangeKey = (
  presets: AnalyticsQuickRangePreset[],
  startDate: string,
  endDate: string,
  preferredKey?: string,
) => {
  const matchingPresetKeys = presets
    .filter((preset) => preset.startDate === startDate && preset.endDate === endDate)
    .map((preset) => preset.key);

  if (preferredKey && matchingPresetKeys.includes(preferredKey)) {
    return preferredKey;
  }

  return matchingPresetKeys.length === 1 ? matchingPresetKeys[0] : '';
};

const getDepartmentLabel = (department: DepartmentRecord | null): string => {
  if (!department) {
    return '';
  }

  if (typeof department.name === 'string' && department.name) {
    return department.name;
  }

  if (typeof department.code === 'string' && department.code) {
    return department.code;
  }

  if (typeof department.id === 'string' && department.id) {
    return department.id;
  }

  return '';
};

const buildStatusSummary = (
  summaryMetrics: { key: string; value: number; status?: string | null }[],
  t: (key: string, params?: Record<string, string | number>, fallback?: string) => string,
): { tone: AnalyticsStatusTone; label: string } => {
  const healthMetric = summaryMetrics.find((metric) => metric.key === 'health_index');
  if (healthMetric) {
    if (healthMetric.status === 'good' || healthMetric.value >= 75) {
      return { tone: 'good', label: t('dashboard.statusPositiveFlow') };
    }
    if (healthMetric.status === 'warning' || healthMetric.value >= 55) {
      return { tone: 'warning', label: t('dashboard.statusNeedsAttention') };
    }
    if (healthMetric.status === 'bad') {
      return { tone: 'bad', label: t('dashboard.statusLoss') };
    }
    return { tone: 'warning', label: t('dashboard.statusNeedsAttention') };
  }

  const getValue = (key: string) => summaryMetrics.find((metric) => metric.key === key)?.value ?? 0;

  const revenue = getValue('total_revenue');
  const expenses = getValue('total_expenses');
  const profit = getValue('operating_profit');
  const netCashflow = getValue('net_cashflow');

  if (revenue <= 0 && expenses <= 0) {
    return { tone: 'neutral', label: t('dashboard.statusNoMovement') };
  }

  if (profit < 0) {
    return { tone: 'bad', label: t('dashboard.statusLoss') };
  }

  if (netCashflow < 0) {
    return { tone: 'warning', label: t('dashboard.statusCashDown') };
  }

  if (profit > 0 && netCashflow > 0) {
    return { tone: 'good', label: t('dashboard.statusPositiveFlow') };
  }

  return { tone: 'warning', label: t('dashboard.statusNeedsAttention') };
};

export function DashboardPage() {
  const { locale, t } = useI18n();
  const navigate = useNavigate();
  const sessionEmployeeId = useAuthStore((state) => state.session?.employeeId ?? '');
  const storedSessionRoles = useAuthStore((state) => state.session?.roles);
  const storedSessionPermissions = useAuthStore((state) => state.session?.permissions);
  const sessionRoles = storedSessionRoles ?? EMPTY_AUTH_LIST;
  const sessionPermissions = storedSessionPermissions ?? EMPTY_AUTH_LIST;
  const workspaceStatus = useWorkspaceStore((state) => state.status);
  const workspaceError = useWorkspaceStore((state) => state.error);
  const workspaceLoaded = useWorkspaceStore((state) => state.isLoaded);
  const requestWorkspaceReload = useWorkspaceStore((state) => state.requestReload);
  const workspaceModuleMap = useWorkspaceStore((state) => state.moduleMap);
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedStartDate = searchParams.get('startDate') ?? '';
  const requestedEndDate = searchParams.get('endDate') ?? '';
  const requestedDepartmentId = searchParams.get('department') ?? '';
  const requestedPeriodKey = searchParams.get('period') ?? '';
  const today = useMemo(() => startOfDay(new Date()), []);
  const todayDate = format(today, 'yyyy-MM-dd');
  const defaultStartDate = format(subDays(today, 29), 'yyyy-MM-dd');
  const sanitizedRequestedStartDate = isValidDateParam(requestedStartDate)
    ? requestedStartDate
    : '';
  const sanitizedRequestedEndDate = isValidDateParam(requestedEndDate) ? requestedEndDate : '';
  const hasInvalidRequestedDateRange =
    Boolean(sanitizedRequestedStartDate && sanitizedRequestedEndDate) &&
    sanitizedRequestedStartDate > sanitizedRequestedEndDate;
  const effectiveStartDate = hasInvalidRequestedDateRange
    ? defaultStartDate
    : sanitizedRequestedStartDate || defaultStartDate;
  const effectiveEndDate = hasInvalidRequestedDateRange
    ? todayDate
    : sanitizedRequestedEndDate || todayDate;
  const canOpenDashboard = canAccessDashboard(sessionRoles, sessionPermissions);

  const departmentQuery = useApiQuery<CrudListResponse>({
    queryKey: baseQueryKeys.crud.resource('core', 'visible-dashboard-departments'),
    queryFn: () => listVisibleDepartments(),
    enabled: canOpenDashboard && sessionEmployeeId.length > 0,
  });
  const allDepartments = useMemo(
    () =>
      ((departmentQuery.data?.items ?? []) as DepartmentRecord[])
        .filter((department) => {
          const moduleKey = typeof department.module_key === 'string' ? department.module_key : '';
          const departmentId = typeof department.id === 'string' ? department.id : '';
          return (
            isValidUuid(departmentId) &&
            moduleKey !== '' &&
            Boolean(getWorkspaceModuleConfig(workspaceModuleMap, moduleKey)?.isDepartmentAssignable)
          );
        })
        .sort((leftDepartment, rightDepartment) =>
          getDepartmentLabel(leftDepartment).localeCompare(getDepartmentLabel(rightDepartment)),
        ),
    [departmentQuery.data, workspaceModuleMap],
  );
  const departmentOptions = useMemo(
    () => flattenDepartmentTree(buildDepartmentTree(allDepartments, getDepartmentLabel)),
    [allDepartments],
  );
  const availableDepartmentIds = useMemo(
    () => new Set(departmentOptions.map((department) => department.id)),
    [departmentOptions],
  );
  const selectedDepartmentId =
    isValidUuid(requestedDepartmentId) && availableDepartmentIds.has(requestedDepartmentId)
      ? requestedDepartmentId
      : '';
  const selectedDepartment = useMemo(
    () =>
      selectedDepartmentId
        ? (allDepartments.find(
            (department) =>
              typeof department.id === 'string' && department.id === selectedDepartmentId,
          ) ?? null)
        : null,
    [allDepartments, selectedDepartmentId],
  );

  const quickRangePresets = useMemo(() => buildAnalyticsQuickRangePresets(t, today), [t, today]);
  const validQuickRangeKeys = useMemo(
    () => new Set(quickRangePresets.map((preset) => preset.key)),
    [quickRangePresets],
  );
  const activeQuickRangeKey = resolveActiveQuickRangeKey(
    quickRangePresets,
    effectiveStartDate,
    effectiveEndDate,
    validQuickRangeKeys.has(requestedPeriodKey) ? requestedPeriodKey : undefined,
  );

  const { data, error, isLoading, refetch } = useApiQuery({
    queryKey: [
      ...baseQueryKeys.dashboard.overview,
      effectiveStartDate,
      effectiveEndDate,
      selectedDepartmentId,
    ],
    queryFn: () =>
      getDashboardOverview({
        startDate: effectiveStartDate,
        endDate: effectiveEndDate,
        departmentId: selectedDepartmentId || undefined,
      }),
    enabled: canOpenDashboard,
  });

  useEffect(() => {
    const unsupportedKeys = ['resource', 'view', 'department_id'];
    const hasUnsupportedKeys = unsupportedKeys.some((key) => searchParams.has(key));

    if (!hasUnsupportedKeys) {
      return;
    }

    const next = new URLSearchParams(searchParams);
    unsupportedKeys.forEach((key) => next.delete(key));
    if (next.toString() === searchParams.toString()) {
      return;
    }

    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    const hasInvalidStartDate = Boolean(requestedStartDate && !sanitizedRequestedStartDate);
    const hasInvalidEndDate = Boolean(requestedEndDate && !sanitizedRequestedEndDate);

    if (!hasInvalidStartDate && !hasInvalidEndDate && !hasInvalidRequestedDateRange) {
      return;
    }

    const next = new URLSearchParams(searchParams);

    if (hasInvalidRequestedDateRange) {
      next.set('startDate', defaultStartDate);
      next.set('endDate', todayDate);
    } else {
      if (sanitizedRequestedStartDate) {
        next.set('startDate', sanitizedRequestedStartDate);
      } else {
        next.delete('startDate');
      }

      if (sanitizedRequestedEndDate) {
        next.set('endDate', sanitizedRequestedEndDate);
      } else {
        next.delete('endDate');
      }
    }

    if (next.toString() === searchParams.toString()) {
      return;
    }

    setSearchParams(next, { replace: true });
  }, [
    defaultStartDate,
    hasInvalidRequestedDateRange,
    requestedEndDate,
    requestedStartDate,
    sanitizedRequestedEndDate,
    sanitizedRequestedStartDate,
    searchParams,
    setSearchParams,
    todayDate,
  ]);

  useEffect(() => {
    if (!requestedPeriodKey) {
      return;
    }

    if (requestedPeriodKey === activeQuickRangeKey) {
      return;
    }

    const next = new URLSearchParams(searchParams);
    next.delete('period');
    if (next.toString() === searchParams.toString()) {
      return;
    }

    setSearchParams(next, { replace: true });
  }, [activeQuickRangeKey, requestedPeriodKey, searchParams, setSearchParams]);

  useEffect(() => {
    if (!requestedDepartmentId || selectedDepartmentId) {
      return;
    }

    const next = new URLSearchParams(searchParams);
    next.delete('department');
    if (next.toString() === searchParams.toString()) {
      return;
    }

    setSearchParams(next, { replace: true });
  }, [requestedDepartmentId, searchParams, selectedDepartmentId, setSearchParams]);

  if (!canOpenDashboard) {
    return (
      <RouteStatusScreen
        label={t('nav.dashboard', undefined, 'Дашборд')}
        title={t('route.forbiddenTitle', undefined, 'Доступ ограничен')}
        description={t('route.dashboardForbiddenDescription')}
        status="forbidden"
        actionLabel={t('common.back')}
        onAction={() => navigate(-1)}
      />
    );
  }

  if (!workspaceLoaded && workspaceStatus === 'error') {
    return (
      <RouteStatusScreen
        label={t('nav.dashboard', undefined, 'Дашборд')}
        title={t(
          'route.workspaceErrorTitle',
          undefined,
          'Не удалось подготовить рабочее пространство',
        )}
        description={
          workspaceError ||
          t(
            'route.workspaceErrorDescription',
            undefined,
            'Не удалось загрузить конфигурацию модулей и прав. Повторите попытку.',
          )
        }
        status="error"
        actionLabel={t('common.retry')}
        onAction={requestWorkspaceReload}
      />
    );
  }

  if (!workspaceLoaded) {
    return (
      <RouteStatusScreen
        label={t('common.loadingLabel')}
        title={t('route.sessionTitle')}
        description={t('route.sessionDescription')}
      />
    );
  }

  const applySearchParams = (nextValues: {
    startDate?: string;
    endDate?: string;
    departmentId?: string;
    quickRangeKey?: string | null;
  }) => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);

      if (nextValues.startDate) {
        next.set('startDate', nextValues.startDate);
      } else {
        next.delete('startDate');
      }

      if (nextValues.endDate) {
        next.set('endDate', nextValues.endDate);
      } else {
        next.delete('endDate');
      }

      if (nextValues.departmentId) {
        next.set('department', nextValues.departmentId);
      } else {
        next.delete('department');
      }

      if ('quickRangeKey' in nextValues) {
        if (nextValues.quickRangeKey) {
          next.set('period', nextValues.quickRangeKey);
        } else {
          next.delete('period');
        }
      }

      if (next.toString() === current.toString()) {
        return current;
      }

      return next;
    });
  };

  const handleStatsDateRangeApply = (range: { startDate?: string; endDate?: string }) => {
    const normalizedRange = normalizeDateRangeValues(range);

    applySearchParams({
      startDate: normalizedRange.startDate,
      endDate: normalizedRange.endDate,
      departmentId: selectedDepartmentId || undefined,
      quickRangeKey: null,
    });
  };

  const handleDepartmentApply = (departmentId: string) => {
    applySearchParams({
      startDate: effectiveStartDate,
      endDate: effectiveEndDate,
      departmentId: departmentId || undefined,
    });
  };

  const handleQuickRangeApply = (preset: AnalyticsQuickRangePreset) => {
    applySearchParams({
      startDate: preset.startDate,
      endDate: preset.endDate,
      departmentId: selectedDepartmentId || undefined,
      quickRangeKey: preset.key,
    });
  };

  const handleResetFilters = () => {
    applySearchParams({
      startDate: defaultStartDate,
      endDate: todayDate,
      departmentId: undefined,
      quickRangeKey: 'last30',
    });
  };

  if (isLoading) {
    return (
      <RouteStatusScreen
        label={t('dashboard.label')}
        title={t('dashboard.loadingTitle')}
        description={t('dashboard.loadingDescription')}
      />
    );
  }

  if (error || !data) {
    return (
      <section className="flex min-h-[60vh] w-full items-center justify-center py-8">
        <Card className="bg-card/99 w-full max-w-2xl rounded-[32px] border-border/70 shadow-[0_24px_80px_-40px_rgba(15,23,42,0.18)]">
          <CardHeader className="space-y-3 pb-5 text-center">
            <CardTitle className="text-3xl tracking-[-0.05em] text-foreground">
              {t('dashboard.errorTitle')}
            </CardTitle>
            <CardDescription className="mx-auto max-w-xl text-sm leading-6">
              {t('dashboard.loadingDescription')}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {error ? <ErrorNotice error={error} className="mx-auto max-w-xl text-left" /> : null}
            <div className="flex justify-center">
              <Button
                variant="outline"
                className="rounded-full px-6"
                onClick={() => {
                  void refetch();
                }}
              >
                <RefreshCw className="h-4 w-4" />
                {t('common.retry')}
              </Button>
            </div>
          </CardContent>
        </Card>
      </section>
    );
  }

  const translatedOverview = translateDashboardOverview(data, t);
  const executiveDashboard = translatedOverview.executive_dashboard;
  const executiveAlerts = executiveDashboard?.alerts ?? [];
  const executiveMetrics = executiveDashboard?.kpis ?? [];
  const executiveAlertsTable =
    executiveDashboard && executiveAlerts.length > 0
      ? {
          key: 'executive_alerts',
          title: t(
            'dashboardData.sections.executive_dashboard.breakdowns.executive_alerts.title',
            undefined,
            'Что требует внимания',
          ),
          description: t(
            'dashboardData.sections.executive_dashboard.breakdowns.executive_alerts.description',
            undefined,
            'Какие направления и проблемы нельзя откладывать.',
          ),
          items: executiveAlerts.map((alert, index) => ({
            key: `${alert.key}-${index}`,
            label: alert.title,
            value: alert.value ?? 0,
            unit: alert.unit ?? null,
            caption: alert.message,
          })),
        }
      : null;
  const summaryMetrics = [
    ...EXECUTIVE_SUMMARY_METRIC_ORDER.map((metricKey) =>
      executiveMetrics.find((metric) => metric.key === metricKey),
    ).filter((metric): metric is (typeof executiveMetrics)[number] => Boolean(metric)),
    ...executiveMetrics.filter((metric) => !EXECUTIVE_SUMMARY_METRIC_ORDER.includes(metric.key)),
  ].slice(0, EXECUTIVE_SUMMARY_METRIC_ORDER.length);
  const executiveChartMap = new Map(
    (executiveDashboard?.charts ?? []).map((chart) => [chart.key, chart] as const),
  );
  const executiveBreakdownMap = new Map(
    (executiveDashboard?.tables ?? []).map((table) => [table.key, table] as const),
  );
  const buildExecutiveSection = (
    key: string,
    title: string,
    description: string,
    chartKeys: string[],
    breakdownKeys: string[],
    extraBreakdowns: DashboardBreakdown[] = [],
  ): AnalyticsSectionDescriptor | null => {
    if (!executiveDashboard) {
      return null;
    }

    const charts = chartKeys
      .map((chartKey) => executiveChartMap.get(chartKey))
      .filter((chart): chart is DashboardChart => Boolean(chart));
    const breakdowns = [
      ...breakdownKeys
        .map((breakdownKey) => executiveBreakdownMap.get(breakdownKey))
        .filter((breakdown): breakdown is DashboardBreakdown => Boolean(breakdown)),
      ...extraBreakdowns,
    ].filter((breakdown) => breakdown.items.length > 0);

    return {
      key,
      title,
      caption: description,
      section: {
        key,
        title,
        description,
        metrics: [],
        charts,
        breakdowns,
      },
    };
  };
  const statusSummary = buildStatusSummary(executiveMetrics, t);
  const selectedScopeLabel = selectedDepartment
    ? getDepartmentLabel(selectedDepartment)
    : translatedOverview.scope.departmentLabel;
  const selectedPeriodLabel = formatAnalyticsPeriodLabel(t, effectiveStartDate, effectiveEndDate);
  const updatedAtLabel = new Intl.DateTimeFormat(locale, {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(new Date(translatedOverview.generatedAt));
  const sections = [
    buildExecutiveSection(
      'executive_departments',
      t('dashboard.executiveDepartmentsTitle', undefined, 'Отделы'),
      t(
        'dashboard.executiveDepartmentsDescription',
        undefined,
        'Сравнение отделов по оценке, выручке, выпуску и потерям.',
      ),
      [],
      EXECUTIVE_DEPARTMENT_BREAKDOWN_KEYS,
    ),
    buildExecutiveSection(
      'executive_risks',
      t('dashboard.executiveRisksTitle', undefined, 'Риски и расходы'),
      t(
        'dashboard.executiveRisksDescription',
        undefined,
        'Куда уходят деньги и какие сигналы требуют реакции в первую очередь.',
      ),
      [],
      EXECUTIVE_RISK_BREAKDOWN_KEYS,
      executiveAlertsTable ? [executiveAlertsTable] : [],
    ),
  ].filter((section): section is AnalyticsSectionDescriptor => Boolean(section));

  return (
    <AnalyticsDashboardView
      title={t('nav.dashboard', undefined, 'Дашборд')}
      badgeLabel={statusSummary.label}
      badgeTone={statusSummary.tone}
      scopeLabel={selectedScopeLabel}
      periodLabel={selectedPeriodLabel}
      updatedAtLabel={updatedAtLabel}
      quickRangePresets={quickRangePresets}
      activeQuickRangeKey={activeQuickRangeKey}
      onQuickRangeApply={handleQuickRangeApply}
      departmentFilter={
        departmentOptions.length > 0
          ? {
              value: selectedDepartmentId,
              options: departmentOptions,
              onChange: handleDepartmentApply,
            }
          : undefined
      }
      startDate={effectiveStartDate}
      endDate={effectiveEndDate}
      onDateRangeApply={handleStatsDateRangeApply}
      onResetFilters={handleResetFilters}
      summaryMetrics={summaryMetrics}
      sections={sections}
      layoutMode="executive"
    />
  );
}
