import type {
  DashboardAlert,
  DashboardBreakdown,
  DashboardChart,
  DashboardMetric,
  DashboardModuleDashboard,
  DashboardSection,
} from '@/shared/api';
import type { TranslateFn } from '@/shared/i18n/types';

import type { AnalyticsSectionDescriptor } from './analytics-dashboard-view';

type SectionBlueprint = {
  id: string;
  titleKey: string;
  titleFallback: string;
  descriptionKey: string;
  descriptionFallback: string;
  metricKeys: string[];
  chartKeys: string[];
  breakdownKeys: string[];
};

type ModuleAnalyticsBlueprint = {
  summaryMetricKeys: string[];
  sections: SectionBlueprint[];
};

const HEADLINE_RESULT_KEYS = [
  'net_eggs',
  'chicks_hatched',
  'birds_processed',
  'product_output',
  'chicks_stock',
  'current_stock',
  'semi_product_output',
];

const COMMERCIAL_RESULT_KEYS = [
  'egg_revenue',
  'shipment_revenue',
  'product_shipped',
  'shipment_volume',
];

const FINANCE_KEYS = [
  'financial_result',
  'net_cashflow',
  'total_expenses',
  'cash_balance',
  'sales_revenue',
  'egg_revenue',
  'shipment_revenue',
];

const EFFICIENCY_KEYS = [
  'hatch_rate',
  'process_rate',
  'shipment_rate',
  'turnover_rate',
  'first_sort_share',
  'loss_rate',
];

const RISK_KEYS = [
  'active_alerts',
  'critical_stock_items',
  'expired_batches',
  'expiring_batches',
  'bad_eggs',
  'loss_rate',
];

const HEADLINE_CHART_PATTERN =
  /(output|flow|hatch|product_flow|semi_flow|revenue|dispatch|shipment|chicks|birds)/i;

const FINANCE_CHART_PATTERN = /(finance_overview|expense_categories)$/i;
const EFFICIENCY_CHART_PATTERN = /(loss|quality|yield|rate|stock|expiry)/i;

const FINANCE_BREAKDOWN_PATTERN = /(expense_categories_table|cash_accounts|recent_expenses)$/i;
const STRATEGIC_BREAKDOWN_PATTERN =
  /(client|clients|product|products|parts|mix|formula|supplier|top)/i;
const RISK_BREAKDOWN_PATTERN = /(low|expiry|critical|active)/i;
const RECENT_BREAKDOWN_PATTERN = /(recent|latest|dispatch|shipment|transfer|batch)/i;
const MODULE_SUMMARY_METRIC_LIMIT = 5;

const MODULE_ANALYTICS_BLUEPRINTS: Record<string, ModuleAnalyticsBlueprint> = {
  egg_farm: {
    summaryMetricKeys: ['net_eggs', 'loss_rate', 'financial_result', 'active_alerts'],
    sections: [
      {
        id: 'overview',
        titleKey: 'dashboard.moduleOverviewTitle',
        titleFallback: 'Главное',
        descriptionKey: 'dashboard.moduleOverviewDescription',
        descriptionFallback: '{module}: выпуск, потери, отгрузки и деньги отдела.',
        metricKeys: [
          'net_eggs',
          'loss_rate',
          'shipment_volume',
          'financial_result',
          'total_expenses',
        ],
        chartKeys: ['egg_output_daily'],
        breakdownKeys: ['egg_clients'],
      },
      {
        id: 'alerts',
        titleKey: 'dashboard.moduleAlertsTitle',
        titleFallback: 'Сигналы',
        descriptionKey: 'dashboard.moduleAlertsDescription',
        descriptionFallback: '{module}: автоматические алёрты по ключевым показателям.',
        metricKeys: [],
        chartKeys: [],
        breakdownKeys: ['module_alerts'],
      },
    ],
  },
  incubation: {
    summaryMetricKeys: ['eggs_set', 'chicks_hatched', 'hatch_rate', 'active_alerts'],
    sections: [
      {
        id: 'overview',
        titleKey: 'dashboard.moduleOverviewTitle',
        titleFallback: 'Главное',
        descriptionKey: 'dashboard.moduleOverviewDescription',
        descriptionFallback: '{module}: закладки, вывод, отгрузки и деньги отдела.',
        metricKeys: [
          'eggs_set',
          'chicks_hatched',
          'hatch_rate',
          'chicks_dispatched',
          'financial_result',
          'total_expenses',
        ],
        chartKeys: ['incubation_egg_arrivals', 'incubation_hatch'],
        breakdownKeys: ['incubation_active_batches', 'incubation_clients'],
      },
      {
        id: 'alerts',
        titleKey: 'dashboard.moduleAlertsTitle',
        titleFallback: 'Сигналы',
        descriptionKey: 'dashboard.moduleAlertsDescription',
        descriptionFallback: '{module}: автоматические алёрты по ключевым показателям.',
        metricKeys: [],
        chartKeys: [],
        breakdownKeys: ['module_alerts'],
      },
    ],
  },
  factory: {
    summaryMetricKeys: ['total_birds', 'mortality_rate', 'financial_result', 'active_alerts'],
    sections: [
      {
        id: 'overview',
        titleKey: 'dashboard.moduleOverviewTitle',
        titleFallback: 'Главное',
        descriptionKey: 'dashboard.moduleOverviewDescription',
        descriptionFallback: '{module}: поголовье, падёж, вес, отгрузки и деньги отдела.',
        metricKeys: [
          'total_birds',
          'mortality_rate',
          'fcr',
          'avg_weight_per_bird',
          'total_shipped',
          'financial_result',
          'total_expenses',
        ],
        chartKeys: [
          'factory_mortality_trend',
          'factory_weight_gain',
          'factory_shipments_flow',
        ],
        breakdownKeys: ['factory_flock_performance', 'factory_shipment_clients'],
      },
      {
        id: 'alerts',
        titleKey: 'dashboard.moduleAlertsTitle',
        titleFallback: 'Сигналы',
        descriptionKey: 'dashboard.moduleAlertsDescription',
        descriptionFallback: '{module}: автоматические алёрты по ключевым показателям.',
        metricKeys: [],
        chartKeys: [],
        breakdownKeys: ['module_alerts'],
      },
    ],
  },
  feed_mill: {
    summaryMetricKeys: ['product_output', 'shrinkage_pct', 'financial_result', 'active_alerts'],
    sections: [
      {
        id: 'overview',
        titleKey: 'dashboard.moduleOverviewTitle',
        titleFallback: 'Главное',
        descriptionKey: 'dashboard.moduleOverviewDescription',
        descriptionFallback: '{module}: выпуск, отгрузки, остатки сырья и деньги отдела.',
        metricKeys: [
          'product_output',
          'product_shipped',
          'shrinkage_pct',
          'financial_result',
          'total_expenses',
        ],
        chartKeys: [],
        breakdownKeys: ['feed_low_raw_stock'],
      },
      {
        id: 'alerts',
        titleKey: 'dashboard.moduleAlertsTitle',
        titleFallback: 'Сигналы',
        descriptionKey: 'dashboard.moduleAlertsDescription',
        descriptionFallback: '{module}: автоматические алёрты по ключевым показателям.',
        metricKeys: [],
        chartKeys: [],
        breakdownKeys: ['module_alerts'],
      },
    ],
  },
  vet_pharmacy: {
    summaryMetricKeys: ['expiring_batches', 'expired_batches', 'financial_result', 'active_alerts'],
    sections: [
      {
        id: 'overview',
        titleKey: 'dashboard.moduleOverviewTitle',
        titleFallback: 'Главное',
        descriptionKey: 'dashboard.moduleOverviewDescription',
        descriptionFallback: '{module}: сроки годности партий и деньги отдела.',
        metricKeys: [
          'expiring_batches',
          'expired_batches',
          'financial_result',
          'total_expenses',
        ],
        chartKeys: [],
        breakdownKeys: ['medicine_expiry_batches'],
      },
      {
        id: 'alerts',
        titleKey: 'dashboard.moduleAlertsTitle',
        titleFallback: 'Сигналы',
        descriptionKey: 'dashboard.moduleAlertsDescription',
        descriptionFallback: '{module}: автоматические алёрты по ключевым показателям.',
        metricKeys: [],
        chartKeys: [],
        breakdownKeys: ['module_alerts'],
      },
    ],
  },
  slaughterhouse: {
    summaryMetricKeys: [
      'birds_processed',
      'net_meat_share_pct',
      'financial_result',
      'active_alerts',
    ],
    sections: [
      {
        id: 'overview',
        titleKey: 'dashboard.moduleOverviewTitle',
        titleFallback: 'Главное',
        descriptionKey: 'dashboard.moduleOverviewDescription',
        descriptionFallback: '{module}: переработка, выход, отгрузки и деньги отдела.',
        metricKeys: [
          'birds_processed',
          'net_meat_share_pct',
          'waste_share_pct',
          'shipment_volume',
          'shipment_revenue',
          'financial_result',
          'total_expenses',
        ],
        chartKeys: ['slaughter_semi_flow'],
        breakdownKeys: ['slaughter_clients'],
      },
      {
        id: 'alerts',
        titleKey: 'dashboard.moduleAlertsTitle',
        titleFallback: 'Сигналы',
        descriptionKey: 'dashboard.moduleAlertsDescription',
        descriptionFallback: '{module}: автоматические алёрты по ключевым показателям.',
        metricKeys: [],
        chartKeys: [],
        breakdownKeys: ['module_alerts'],
      },
    ],
  },
  finance: {
    summaryMetricKeys: [
      'net_cashflow',
      'cash_balance',
      'accounts_receivable',
      'accounts_payable',
      'financial_result',
    ],
    sections: [
      {
        id: 'cashflow',
        titleKey: 'dashboard.financeCashflowTitle',
        titleFallback: 'Денежный поток',
        descriptionKey: 'dashboard.financeCashflowDescription',
        descriptionFallback: '{module}: поступления, списания и текущий баланс касс организации.',
        metricKeys: ['cash_inflow', 'cash_outflow', 'net_cashflow', 'cash_balance'],
        chartKeys: ['finance_cashflow_daily', 'finance_cash_balance_by_account'],
        breakdownKeys: ['finance_cash_accounts'],
      },
      {
        id: 'expenses',
        titleKey: 'dashboard.financeExpensesTitle',
        titleFallback: 'Расходы',
        descriptionKey: 'dashboard.financeExpensesDescription',
        descriptionFallback: '{module}: куда уходят деньги по статьям расходов.',
        metricKeys: ['total_expenses', 'cash_outflow'],
        chartKeys: ['finance_expense_categories'],
        breakdownKeys: ['finance_recent_payments'],
      },
      {
        id: 'debts',
        titleKey: 'dashboard.financeDebtsTitle',
        titleFallback: 'Долги и взаиморасчёты',
        descriptionKey: 'dashboard.financeDebtsDescription',
        descriptionFallback:
          '{module}: дебиторская и кредиторская задолженность по срокам и контрагентам.',
        metricKeys: ['accounts_receivable', 'accounts_payable', 'financial_result'],
        chartKeys: ['finance_debts_aging'],
        breakdownKeys: ['finance_top_debtors', 'finance_top_creditors', 'module_alerts'],
      },
    ],
  },
  hr: {
    summaryMetricKeys: [
      'active_employees',
      'new_hires',
      'total_payroll',
      'average_salary',
      'without_position',
    ],
    sections: [
      {
        id: 'headcount',
        titleKey: 'dashboard.hrHeadcountTitle',
        titleFallback: 'Численность',
        descriptionKey: 'dashboard.hrHeadcountDescription',
        descriptionFallback: '{module}: распределение сотрудников по отделам, должностям и ролям.',
        metricKeys: [
          'active_employees',
          'total_employees',
          'without_position',
          'without_department',
        ],
        chartKeys: ['hr_employees_by_department', 'hr_employees_by_position'],
        breakdownKeys: ['hr_top_departments', 'hr_top_positions', 'hr_role_distribution'],
      },
      {
        id: 'hiring',
        titleKey: 'dashboard.hrHiringTitle',
        titleFallback: 'Найм',
        descriptionKey: 'dashboard.hrHiringDescription',
        descriptionFallback: '{module}: динамика найма и последние принятые сотрудники.',
        metricKeys: ['new_hires', 'active_employees'],
        chartKeys: ['hr_hires_monthly'],
        breakdownKeys: ['hr_recent_hires'],
      },
      {
        id: 'payroll',
        titleKey: 'dashboard.hrPayrollTitle',
        titleFallback: 'Зарплатный фонд',
        descriptionKey: 'dashboard.hrPayrollDescription',
        descriptionFallback: '{module}: зарплатный фонд, средняя зарплата и распределение.',
        metricKeys: ['total_payroll', 'average_salary'],
        chartKeys: ['hr_salary_distribution'],
        breakdownKeys: ['module_alerts'],
      },
    ],
  },
  core: {
    summaryMetricKeys: [
      'clients_total',
      'new_clients',
      'departments_total',
      'audit_events',
      'unique_actors',
    ],
    sections: [
      {
        id: 'directories',
        titleKey: 'dashboard.coreDirectoriesTitle',
        titleFallback: 'Состояние справочников',
        descriptionKey: 'dashboard.coreDirectoriesDescription',
        descriptionFallback: '{module}: клиентская база, отделы и склады в организации.',
        metricKeys: ['clients_total', 'new_clients', 'departments_total', 'warehouses_total'],
        chartKeys: ['core_clients_growth', 'core_departments_by_module'],
        breakdownKeys: ['core_recent_clients'],
      },
      {
        id: 'audit',
        titleKey: 'dashboard.coreAuditTitle',
        titleFallback: 'Активность пользователей',
        descriptionKey: 'dashboard.coreAuditDescription',
        descriptionFallback: '{module}: события аудита, кто и какие сущности меняет в системе.',
        metricKeys: ['audit_events', 'unique_actors'],
        chartKeys: ['core_audit_activity_daily', 'core_audit_by_action'],
        breakdownKeys: ['core_top_actors', 'core_top_entities'],
      },
    ],
  },
};

function dedupeByKey<T extends { key: string }>(items: T[]): T[] {
  const seen = new Set<string>();

  return items.filter((item) => {
    if (seen.has(item.key)) {
      return false;
    }

    seen.add(item.key);
    return true;
  });
}

function hasChartData(chart: DashboardChart | null | undefined) {
  if (!chart) {
    return false;
  }

  return chart.series.some((series) => series.points.length > 0);
}

function hasBreakdownData(breakdown: DashboardBreakdown | null | undefined) {
  return Boolean(breakdown && breakdown.items.length > 0);
}

function hasSectionData(section: DashboardSection) {
  return (
    section.metrics.some((metric) => metric.value !== 0) ||
    section.charts.some((chart) => hasChartData(chart)) ||
    section.breakdowns.some((breakdown) => hasBreakdownData(breakdown))
  );
}

function buildAlertMetric(
  alerts: DashboardAlert[] | undefined,
  t: TranslateFn,
): DashboardMetric | null {
  if (!alerts || alerts.length === 0) {
    return null;
  }

  const tone = alerts.some((alert) => alert.level === 'critical')
    ? 'bad'
    : alerts.some((alert) => alert.level === 'warning')
      ? 'warning'
      : 'neutral';

  return {
    key: 'active_alerts',
    label: t('dashboard.moduleAlertsSummary', undefined, 'Активные сигналы'),
    value: alerts.length,
    unit: 'шт',
    status: tone,
  };
}

function pickMetricsByKeys(
  metricsByKey: Map<string, DashboardMetric>,
  keys: string[],
): DashboardMetric[] {
  const seen = new Set<string>();
  const result: DashboardMetric[] = [];

  for (const key of keys) {
    const metric = metricsByKey.get(key);
    if (!metric || seen.has(metric.key)) {
      continue;
    }

    result.push(metric);
    seen.add(metric.key);
  }

  return result;
}

function pickChartsByKeys(
  chartsByKey: Map<string, DashboardChart>,
  keys: string[],
): DashboardChart[] {
  const result: DashboardChart[] = [];
  const seen = new Set<string>();

  for (const key of keys) {
    const chart = chartsByKey.get(key);
    if (!chart || seen.has(chart.key)) {
      continue;
    }

    result.push(chart);
    seen.add(chart.key);
  }

  return result;
}

function pickBreakdownsByKeys(
  breakdownsByKey: Map<string, DashboardBreakdown>,
  keys: string[],
): DashboardBreakdown[] {
  const result: DashboardBreakdown[] = [];
  const seen = new Set<string>();

  for (const key of keys) {
    const breakdown = breakdownsByKey.get(key);
    if (!breakdown || seen.has(breakdown.key)) {
      continue;
    }

    result.push(breakdown);
    seen.add(breakdown.key);
  }

  return result;
}

function pickMetricByKeys(
  metricsByKey: Map<string, DashboardMetric>,
  selectedKeys: Set<string>,
  keys: string[],
  take: number,
) {
  const picked: DashboardMetric[] = [];

  for (const key of keys) {
    if (picked.length >= take) {
      break;
    }

    const metric = metricsByKey.get(key);
    if (!metric || selectedKeys.has(metric.key)) {
      continue;
    }

    picked.push(metric);
    selectedKeys.add(metric.key);
  }

  return picked;
}

function buildSummaryMetrics(module: DashboardModuleDashboard, t: TranslateFn): DashboardMetric[] {
  const syntheticAlertMetric = buildAlertMetric(module.alerts, t);
  const allMetrics = syntheticAlertMetric
    ? [...module.kpis, syntheticAlertMetric]
    : [...module.kpis];
  const metricsByKey = new Map(allMetrics.map((metric) => [metric.key, metric] as const));
  const selectedKeys = new Set<string>();
  const summary: DashboardMetric[] = [];

  summary.push(...pickMetricByKeys(metricsByKey, selectedKeys, HEADLINE_RESULT_KEYS, 2));
  summary.push(...pickMetricByKeys(metricsByKey, selectedKeys, COMMERCIAL_RESULT_KEYS, 1));
  summary.push(...pickMetricByKeys(metricsByKey, selectedKeys, FINANCE_KEYS, 1));
  summary.push(...pickMetricByKeys(metricsByKey, selectedKeys, EFFICIENCY_KEYS, 1));
  summary.push(...pickMetricByKeys(metricsByKey, selectedKeys, RISK_KEYS, 1));

  for (const metric of allMetrics) {
    if (summary.length >= MODULE_SUMMARY_METRIC_LIMIT) {
      break;
    }

    if (selectedKeys.has(metric.key)) {
      continue;
    }

    summary.push(metric);
    selectedKeys.add(metric.key);
  }

  return summary.slice(0, MODULE_SUMMARY_METRIC_LIMIT);
}

function buildAlertsBreakdown(
  alerts: DashboardAlert[] | undefined,
  t: TranslateFn,
): DashboardBreakdown | null {
  if (!alerts || alerts.length === 0) {
    return null;
  }

  return {
    key: 'module_alerts',
    title: t('dashboard.moduleAlertsTitle', undefined, 'Операционные сигналы'),
    description: t(
      'dashboard.moduleAlertsDescription',
      undefined,
      'Сигналы, которые требуют внимания до следующего операционного цикла.',
    ),
    items: alerts.map((alert, index) => ({
      key: `${alert.key}-${index}`,
      label: alert.title,
      value: alert.value ?? 0,
      unit: alert.unit ?? null,
      caption: alert.message,
    })),
  };
}

function pickBreakdown(
  breakdowns: DashboardBreakdown[],
  predicate: (breakdown: DashboardBreakdown) => boolean,
  excludedKeys: Set<string>,
) {
  return (
    breakdowns.find(
      (breakdown) =>
        hasBreakdownData(breakdown) && !excludedKeys.has(breakdown.key) && predicate(breakdown),
    ) ?? null
  );
}

function pickChart(
  charts: DashboardChart[],
  predicate: (chart: DashboardChart) => boolean,
  excludedKeys: Set<string>,
) {
  return (
    charts.find(
      (chart) => hasChartData(chart) && !excludedKeys.has(chart.key) && predicate(chart),
    ) ?? null
  );
}

function getBreakdownSearchText(breakdown: DashboardBreakdown) {
  return `${breakdown.key} ${breakdown.title} ${breakdown.description ?? ''}`.toLowerCase();
}

function getChartSearchText(chart: DashboardChart) {
  return `${chart.key} ${chart.title} ${chart.description ?? ''}`.toLowerCase();
}

function createSection(
  key: string,
  title: string,
  description: string,
  metrics: DashboardMetric[],
  charts: Array<DashboardChart | null>,
  breakdowns: Array<DashboardBreakdown | null>,
): AnalyticsSectionDescriptor | null {
  const section: DashboardSection = {
    key,
    title,
    description,
    metrics: dedupeByKey(metrics),
    charts: dedupeByKey(charts.filter((chart): chart is DashboardChart => Boolean(chart))),
    breakdowns: dedupeByKey(
      breakdowns.filter((breakdown): breakdown is DashboardBreakdown => Boolean(breakdown)),
    ),
  };

  if (!hasSectionData(section)) {
    return null;
  }

  return {
    key,
    title,
    caption: description,
    section,
  };
}

export function buildModuleAnalyticsPresentation(
  module: DashboardModuleDashboard,
  moduleLabel: string,
  t: TranslateFn,
): {
  summaryMetrics: DashboardMetric[];
  sections: AnalyticsSectionDescriptor[];
} {
  const syntheticAlertMetric = buildAlertMetric(module.alerts, t);
  const allMetrics = syntheticAlertMetric
    ? [...module.kpis, syntheticAlertMetric]
    : [...module.kpis];
  const metricsByKey = new Map(allMetrics.map((metric) => [metric.key, metric] as const));
  const alertsBreakdown = buildAlertsBreakdown(module.alerts, t);
  const blueprint = Object.prototype.hasOwnProperty.call(MODULE_ANALYTICS_BLUEPRINTS, module.key)
    ? MODULE_ANALYTICS_BLUEPRINTS[module.key]
    : null;

  if (blueprint) {
    const chartsByKey = new Map(
      module.charts
        .filter((chart) => hasChartData(chart))
        .map((chart) => [chart.key, chart] as const),
    );
    const breakdowns = alertsBreakdown ? [...module.tables, alertsBreakdown] : [...module.tables];
    const breakdownsByKey = new Map(
      breakdowns
        .filter((breakdown) => hasBreakdownData(breakdown))
        .map((breakdown) => [breakdown.key, breakdown] as const),
    );
    const summaryMetrics = dedupeByKey([
      ...pickMetricsByKeys(metricsByKey, blueprint.summaryMetricKeys),
      ...buildSummaryMetrics(module, t),
    ]).slice(0, MODULE_SUMMARY_METRIC_LIMIT);
    const sections = blueprint.sections
      .map((section) =>
        createSection(
          `${module.key}_${section.id}`,
          t(section.titleKey, undefined, section.titleFallback),
          t(
            section.descriptionKey,
            { module: moduleLabel },
            section.descriptionFallback.replace('{module}', moduleLabel),
          ),
          pickMetricsByKeys(metricsByKey, section.metricKeys),
          pickChartsByKeys(chartsByKey, section.chartKeys),
          pickBreakdownsByKeys(breakdownsByKey, section.breakdownKeys),
        ),
      )
      .filter((section): section is AnalyticsSectionDescriptor => Boolean(section));

    return {
      summaryMetrics,
      sections,
    };
  }

  const summaryMetrics = buildSummaryMetrics(module, t);
  const usedChartKeys = new Set<string>();
  const usedBreakdownKeys = new Set<string>();
  const financeCharts = module.charts.filter(
    (chart) =>
      hasChartData(chart) && !usedChartKeys.has(chart.key) && FINANCE_CHART_PATTERN.test(chart.key),
  );
  financeCharts.forEach((chart) => usedChartKeys.add(chart.key));
  const financeBreakdowns = module.tables.filter(
    (breakdown) =>
      hasBreakdownData(breakdown) &&
      !usedBreakdownKeys.has(breakdown.key) &&
      FINANCE_BREAKDOWN_PATTERN.test(breakdown.key),
  );
  financeBreakdowns.forEach((breakdown) => usedBreakdownKeys.add(breakdown.key));
  const strategicBreakdown = pickBreakdown(
    module.tables,
    (breakdown) => STRATEGIC_BREAKDOWN_PATTERN.test(getBreakdownSearchText(breakdown)),
    usedBreakdownKeys,
  );
  if (strategicBreakdown) {
    usedBreakdownKeys.add(strategicBreakdown.key);
  }

  const riskBreakdown = pickBreakdown(
    module.tables,
    (breakdown) => RISK_BREAKDOWN_PATTERN.test(getBreakdownSearchText(breakdown)),
    usedBreakdownKeys,
  );
  if (riskBreakdown) {
    usedBreakdownKeys.add(riskBreakdown.key);
  }

  const recentBreakdown = pickBreakdown(
    module.tables,
    (breakdown) => RECENT_BREAKDOWN_PATTERN.test(getBreakdownSearchText(breakdown)),
    usedBreakdownKeys,
  );
  if (recentBreakdown) {
    usedBreakdownKeys.add(recentBreakdown.key);
  }
  const remainingBreakdowns = module.tables.filter(
    (breakdown) => hasBreakdownData(breakdown) && !usedBreakdownKeys.has(breakdown.key),
  );

  const headlineChart = pickChart(
    module.charts,
    (chart) => HEADLINE_CHART_PATTERN.test(getChartSearchText(chart)),
    usedChartKeys,
  );
  if (headlineChart) {
    usedChartKeys.add(headlineChart.key);
  }

  const efficiencyChart = pickChart(
    module.charts,
    (chart) => EFFICIENCY_CHART_PATTERN.test(getChartSearchText(chart)),
    usedChartKeys,
  );
  if (efficiencyChart) {
    usedChartKeys.add(efficiencyChart.key);
  }

  const remainingCharts = module.charts.filter(
    (chart) => hasChartData(chart) && !usedChartKeys.has(chart.key),
  );

  const efficiencyMetrics = module.kpis.filter(
    (metric) => EFFICIENCY_KEYS.includes(metric.key) || RISK_KEYS.includes(metric.key),
  );
  const financeMetrics = module.kpis.filter((metric) => FINANCE_KEYS.includes(metric.key));
  const operationsMetrics = module.kpis.filter(
    (metric) =>
      !summaryMetrics.some((summaryMetric) => summaryMetric.key === metric.key) &&
      !financeMetrics.some((financeMetric) => financeMetric.key === metric.key) &&
      !efficiencyMetrics.some((efficiencyMetric) => efficiencyMetric.key === metric.key),
  );

  const sections = [
    createSection(
      `${module.key}_overview`,
      t('dashboard.moduleOverviewTitle', undefined, 'Главное'),
      module.description ??
        t(
          'dashboard.moduleOverviewDescription',
          { module: moduleLabel },
          `${moduleLabel}: самые важные показатели и текущая динамика.`,
        ),
      summaryMetrics.slice(0, 3),
      [headlineChart],
      [strategicBreakdown],
    ),
    createSection(
      `${module.key}_finance`,
      t('dashboard.moduleFinanceTitle', undefined, 'Финансы'),
      t(
        'dashboard.moduleFinanceDescription',
        { module: moduleLabel },
        `${moduleLabel}: деньги отдела, расходы, касса и финансовый результат.`,
      ),
      dedupeByKey(financeMetrics),
      financeCharts,
      financeBreakdowns,
    ),
    createSection(
      `${module.key}_efficiency`,
      t('dashboard.moduleEfficiencyTitle', undefined, 'Риски и эффективность'),
      t(
        'dashboard.moduleEfficiencyDescription',
        { module: moduleLabel },
        `${moduleLabel}: где есть отклонения и что требует реакции.`,
      ),
      dedupeByKey([
        ...summaryMetrics.filter((metric) => RISK_KEYS.includes(metric.key)),
        ...efficiencyMetrics,
      ]),
      [efficiencyChart],
      [alertsBreakdown, riskBreakdown],
    ),
    createSection(
      `${module.key}_operations`,
      t('dashboard.moduleOperationsTitle', undefined, 'Детали и операции'),
      t(
        'dashboard.moduleOperationsDescription',
        { module: moduleLabel },
        `${moduleLabel}: расшифровка по клиентам, партиям и последним операциям.`,
      ),
      dedupeByKey(operationsMetrics),
      remainingCharts,
      [recentBreakdown, ...remainingBreakdowns],
    ),
  ].filter((section): section is AnalyticsSectionDescriptor => Boolean(section));

  return {
    summaryMetrics,
    sections,
  };
}
