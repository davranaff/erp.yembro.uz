import type { DashboardAnalyticsResponse, DashboardOverviewResponse } from '@/shared/api';

import type { TranslateFn } from './types';

const UNIT_KEYS: Record<string, string> = {
  шт: 'units.pcs',
  клиентов: 'units.clients',
  кг: 'units.kg',
  'ед.': 'units.units',
};

const BACKEND_MODULE_LABEL_KEYS: Record<string, string> = {
  Маточник: 'modules.egg.label',
  Инкубация: 'modules.incubation.label',
  Фабрика: 'modules.factory.label',
  Корма: 'modules.feed.label',
  Ветаптека: 'modules.medicine.label',
  Убойня: 'modules.slaughter.label',
  Модуль: 'dashboard.moduleLabel',
};

const EXECUTIVE_DEPARTMENT_CHART_KEYS = new Set([
  'department_contribution',
  'department_revenue',
  'department_operations',
  'department_loss_rate',
]);

function translateIfExists(
  t: TranslateFn,
  key: string,
  params?: Record<string, string | number>,
): string | undefined {
  const translated = t(key, params);
  return translated === key ? undefined : translated;
}

function translateGenericFinanceSeriesLabel(seriesKey: string, fallback: string, t: TranslateFn) {
  if (seriesKey === 'revenue') {
    return t('dashboard.summaryMetrics.sales_revenue.label', undefined, fallback);
  }
  if (seriesKey === 'expenses' || seriesKey === 'amount') {
    return t('dashboard.summaryMetrics.total_expenses.label', undefined, fallback);
  }
  if (seriesKey === 'profit' || seriesKey === 'result') {
    return t('dashboard.summaryMetrics.financial_result.label', undefined, fallback);
  }
  if (seriesKey === 'cashflow') {
    return t('dashboard.summaryMetrics.net_cashflow.label', undefined, fallback);
  }

  return fallback;
}

function resolveGenericModuleChartText(chartKey: string, t: TranslateFn) {
  if (chartKey.endsWith('_finance_overview')) {
    return {
      title: t('dashboard.moduleFinanceOverviewChartTitle', undefined, 'Деньги отдела'),
      description: t(
        'dashboard.moduleFinanceOverviewChartDescription',
        undefined,
        'Выручка, расходы, финрезультат и денежный поток по дням.',
      ),
    };
  }

  if (chartKey.endsWith('_expense_categories')) {
    return {
      title: t('dashboard.moduleExpenseCategoriesChartTitle', undefined, 'Куда уходят деньги'),
      description: t(
        'dashboard.moduleExpenseCategoriesChartDescription',
        undefined,
        'Самые тяжёлые категории расходов за выбранный период.',
      ),
    };
  }

  return null;
}

function resolveGenericModuleBreakdownText(breakdownKey: string, t: TranslateFn) {
  if (breakdownKey.endsWith('_expense_categories_table')) {
    return {
      title: t('dashboard.moduleExpenseCategoriesTableTitle', undefined, 'Главные категории расходов'),
      description: t(
        'dashboard.moduleExpenseCategoriesTableDescription',
        undefined,
        'Какие статьи расходов сильнее всего влияют на деньги отдела.',
      ),
    };
  }

  if (breakdownKey.endsWith('_cash_accounts')) {
    return {
      title: t('dashboard.moduleCashAccountsTableTitle', undefined, 'Кассы отдела'),
      description: t(
        'dashboard.moduleCashAccountsTableDescription',
        undefined,
        'Текущий баланс по кассам и счетам внутри отдела.',
      ),
    };
  }

  if (breakdownKey.endsWith('_recent_expenses')) {
    return {
      title: t('dashboard.moduleRecentExpensesTableTitle', undefined, 'Последние расходы'),
      description: t(
        'dashboard.moduleRecentExpensesTableDescription',
        undefined,
        'Последние расходные операции за выбранный период.',
      ),
    };
  }

  return null;
}

function resolveGenericModuleAlertText(alertKey: string, t: TranslateFn) {
  if (alertKey === 'module_financial_result_negative') {
    return {
      title: t('dashboard.moduleFinancialResultNegativeTitle', undefined, 'Отдел работает в минус'),
      message: t(
        'dashboard.moduleFinancialResultNegativeMessage',
        undefined,
        'Расходы оказались выше собственной выручки за период.',
      ),
    };
  }

  if (alertKey === 'module_expense_concentration') {
    return {
      title: t(
        'dashboard.moduleExpenseConcentrationTitle',
        undefined,
        'Расходы сосредоточены в одной категории',
      ),
      message: t(
        'dashboard.moduleExpenseConcentrationMessage',
        undefined,
        'Одна категория занимает слишком большую долю расходов отдела.',
      ),
    };
  }

  if (alertKey === 'module_cash_balance_negative') {
    return {
      title: t('dashboard.moduleCashBalanceNegativeTitle', undefined, 'Касса ушла в минус'),
      message: t(
        'dashboard.moduleCashBalanceNegativeMessage',
        undefined,
        'Баланс касс отдела стал отрицательным.',
      ),
    };
  }

  return null;
}

function translateUnit(unit: string | null | undefined, t: TranslateFn) {
  if (!unit) {
    return unit;
  }

  const key = UNIT_KEYS[unit];
  return key ? t(key, undefined, unit) : unit;
}

function translateModuleLabel(label: string, t: TranslateFn) {
  const key = BACKEND_MODULE_LABEL_KEYS[label];
  return key ? t(key, undefined, label) : label;
}

function translateChartPointLabel(
  sectionKey: string,
  chartKey: string,
  label: string,
  t: TranslateFn,
) {
  if (sectionKey === 'executive_dashboard' && EXECUTIVE_DEPARTMENT_CHART_KEYS.has(chartKey)) {
    return translateModuleLabel(label, t);
  }

  return label;
}

function translateDepartmentStatus(status: string, t: TranslateFn) {
  const normalized = status.trim().toLowerCase();

  if (normalized === 'good') {
    return t('common.good');
  }
  if (normalized === 'warning') {
    return t('common.warning');
  }
  if (normalized === 'bad') {
    return t('common.bad');
  }

  return t('common.neutral');
}

function translateBreakdownCaption(
  sectionKey: string,
  breakdownKey: string,
  itemLabel: string,
  caption: string | null | undefined,
  t: TranslateFn,
) {
  if (!caption) {
    return caption;
  }

  if (sectionKey === 'executive_dashboard' && breakdownKey === 'departments_performance') {
    const statusMatch = caption.match(
      /^\s*Статус\s+([^·]+?)\s*·\s*Потери\s+(.+)\s*·\s*Выручка\s+(.+)\s*·\s*Выпуск\s+(.+)\s*$/,
    );

    if (statusMatch) {
      const [, status, losses, revenue, output] = statusMatch;

      return t(
        'dashboard.departmentResultCaptionWithStatus',
        {
          module: translateModuleLabel(itemLabel, t),
          status: translateDepartmentStatus(status, t),
          losses,
          revenue,
          output,
          lossesLabel: t('dashboard.lossesLabel', undefined, 'Потери'),
          revenueLabel: t('dashboard.revenueLabel', undefined, 'Выручка'),
          outputLabel: t('dashboard.outputLabel', undefined, 'Выпуск'),
        },
        caption,
      );
    }

    const legacyMatch = caption.match(/^(.*?) · Выручка (.+) · Расходы (.+)$/);

    if (legacyMatch) {
      const [, moduleLabel, revenue, expenses] = legacyMatch;

      return t(
        'dashboard.departmentResultCaption',
        {
          module: translateModuleLabel(moduleLabel, t),
          revenue,
          expenses,
        },
        caption,
      );
    }

    return translateModuleLabel(caption, t);
  }

  return caption;
}

function translateModuleDashboard(module: any, t: TranslateFn, sectionPrefix: string): any {
  const sectionKey = module.key;
  return {
    ...module,
    title: t(`${sectionPrefix}.${sectionKey}.title`, undefined, module.title),
    description: module.description
      ? t(`${sectionPrefix}.${sectionKey}.description`, undefined, module.description)
      : module.description,
    kpis: module.kpis.map((metric: any) => ({
      ...metric,
      label: t(
        `${sectionPrefix}.${sectionKey}.metrics.${metric.key}.label`,
        undefined,
        t(`dashboard.summaryMetrics.${metric.key}.label`, undefined, metric.label),
      ),
      unit: translateUnit(metric.unit, t),
    })),
    charts: module.charts.map((chart: any) => ({
      ...chart,
      title:
        translateIfExists(t, `${sectionPrefix}.${sectionKey}.charts.${chart.key}.title`) ||
        resolveGenericModuleChartText(chart.key, t)?.title ||
        chart.title,
      description: chart.description
        ? translateIfExists(t, `${sectionPrefix}.${sectionKey}.charts.${chart.key}.description`) ||
          resolveGenericModuleChartText(chart.key, t)?.description ||
          chart.description
        : chart.description,
      unit: translateUnit(chart.unit, t),
      series: chart.series.map((series: any) => ({
        ...series,
        label:
          translateIfExists(t, `${sectionPrefix}.${sectionKey}.charts.${chart.key}.series.${series.key}`) ||
          translateGenericFinanceSeriesLabel(series.key, series.label, t),
        points: series.points.map((point: any) => ({
          ...point,
          label: translateChartPointLabel(sectionKey, chart.key, point.label, t),
        })),
      })),
    })),
    tables: module.tables.map((table: any) => ({
      ...table,
      title:
        translateIfExists(t, `${sectionPrefix}.${sectionKey}.breakdowns.${table.key}.title`) ||
        resolveGenericModuleBreakdownText(table.key, t)?.title ||
        table.title,
      description: table.description
        ? translateIfExists(t, `${sectionPrefix}.${sectionKey}.breakdowns.${table.key}.description`) ||
          resolveGenericModuleBreakdownText(table.key, t)?.description ||
          table.description
        : table.description,
      items: table.items.map((item: any) => ({
        ...item,
        unit: translateUnit(item.unit, t),
        label: translateModuleLabel(item.label, t),
        caption: translateBreakdownCaption(sectionKey, table.key, item.label, item.caption, t),
      })),
    })),
    alerts: (module.alerts ?? []).map((alert: any) => ({
      ...alert,
      title:
        translateIfExists(t, `${sectionPrefix}.${sectionKey}.alerts.${alert.key}.title`) ||
        resolveGenericModuleAlertText(alert.key, t)?.title ||
        alert.title,
      message:
        translateIfExists(t, `${sectionPrefix}.${sectionKey}.alerts.${alert.key}.message`) ||
        resolveGenericModuleAlertText(alert.key, t)?.message ||
        alert.message,
      unit: translateUnit(alert.unit, t),
    })),
  };
}

export function translateDashboardAnalytics(
  data: DashboardAnalyticsResponse,
  t: TranslateFn,
): DashboardAnalyticsResponse {
  return {
    ...data,
    department_dashboard: data.department_dashboard
      ? {
          modules: data.department_dashboard.modules.map((module) =>
            translateModuleDashboard(module, t, 'dashboardData.sections'),
          ),
        }
      : data.department_dashboard,
    executive_dashboard: data.executive_dashboard
      ? translateModuleDashboard(
          {
            key: 'executive_dashboard',
            title: 'Executive dashboard',
            description: null,
            ...data.executive_dashboard,
          },
          t,
          'dashboardData.sections',
        )
      : data.executive_dashboard,
  };
}

export function translateDashboardOverview(
  data: DashboardOverviewResponse,
  t: TranslateFn,
): DashboardOverviewResponse {
  return {
    ...data,
    executive_dashboard: data.executive_dashboard
      ? {
          ...translateModuleDashboard(
            {
              key: 'executive_dashboard',
              title: 'Executive dashboard',
              description: null,
              ...data.executive_dashboard,
            },
            t,
            'dashboardData.sections',
          ),
          kpis: data.executive_dashboard.kpis.map((metric) => ({
            ...metric,
            label: t(`dashboard.summaryMetrics.${metric.key}.label`, undefined, metric.label),
            unit: translateUnit(metric.unit, t),
          })),
        }
      : data.executive_dashboard,
  };
}
