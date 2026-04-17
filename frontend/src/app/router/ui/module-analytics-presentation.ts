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
    summaryMetricKeys: [
      'net_eggs',
      'loss_rate',
      'egg_revenue',
      'financial_result',
      'active_alerts',
    ],
    sections: [
      {
        id: 'overview',
        titleKey: 'dashboard.moduleOverviewTitle',
        titleFallback: 'Главное',
        descriptionKey: 'dashboard.moduleOverviewDescription',
        descriptionFallback: '{module}: выпуск, передача по потоку и коммерческий результат.',
        metricKeys: ['net_eggs', 'eggs_to_incubation', 'shipment_volume'],
        chartKeys: ['egg_output_daily', 'egg_destination_flow'],
        breakdownKeys: ['egg_destination_balance', 'egg_clients'],
      },
      {
        id: 'finance',
        titleKey: 'dashboard.moduleFinanceTitle',
        titleFallback: 'Финансы',
        descriptionKey: 'dashboard.moduleFinanceDescription',
        descriptionFallback: '{module}: деньги отдела, расходы, касса и финансовый результат.',
        metricKeys: ['financial_result', 'total_expenses', 'net_cashflow', 'cash_balance'],
        chartKeys: ['egg_finance_overview', 'egg_expense_categories'],
        breakdownKeys: ['egg_expense_categories_table', 'egg_cash_accounts'],
      },
      {
        id: 'efficiency',
        titleKey: 'dashboard.moduleEfficiencyTitle',
        titleFallback: 'Риски и эффективность',
        descriptionKey: 'dashboard.moduleEfficiencyDescription',
        descriptionFallback: '{module}: потери, остаток и ресурсы, которые требуют внимания.',
        metricKeys: ['loss_rate', 'current_stock', 'medicine_consumed'],
        chartKeys: ['egg_loss_rate'],
        breakdownKeys: ['module_alerts'],
      },
    ],
  },
  incubation: {
    summaryMetricKeys: [
      'chicks_hatched',
      'hatch_rate',
      'fertility_pct',
      'hof_pct',
      'active_alerts',
    ],
    sections: [
      {
        id: 'overview',
        titleKey: 'dashboard.moduleOverviewTitle',
        titleFallback: 'Главное',
        descriptionKey: 'dashboard.moduleOverviewDescription',
        descriptionFallback: '{module}: вход яиц, вывод птенцов и основной сбыт.',
        metricKeys: ['eggs_set', 'chicks_hatched', 'saleable_chick_yield_pct', 'chicks_dispatched'],
        chartKeys: ['incubation_egg_arrivals', 'incubation_hatch'],
        breakdownKeys: ['incubation_sources', 'incubation_clients'],
      },
      {
        id: 'finance',
        titleKey: 'dashboard.moduleFinanceTitle',
        titleFallback: 'Финансы',
        descriptionKey: 'dashboard.moduleFinanceDescription',
        descriptionFallback: '{module}: деньги отдела, расходы, касса и финансовый результат.',
        metricKeys: ['financial_result', 'total_expenses', 'net_cashflow', 'cash_balance'],
        chartKeys: ['incubation_finance_overview', 'incubation_expense_categories'],
        breakdownKeys: ['incubation_expense_categories_table', 'incubation_cash_accounts'],
      },
      {
        id: 'efficiency',
        titleKey: 'dashboard.moduleEfficiencyTitle',
        titleFallback: 'Риски и эффективность',
        descriptionKey: 'dashboard.moduleEfficiencyDescription',
        descriptionFallback: '{module}: выводимость, качество партии и активные циклы.',
        metricKeys: ['hatch_rate', 'fertility_pct', 'hof_pct', 'bad_eggs'],
        chartKeys: ['incubation_yield', 'incubation_quality'],
        breakdownKeys: ['module_alerts', 'incubation_active_batches'],
      },
    ],
  },
  factory: {
    summaryMetricKeys: [
      'total_birds',
      'mortality_rate',
      'total_shipped',
      'shipment_revenue',
      'active_alerts',
    ],
    sections: [
      {
        id: 'overview',
        titleKey: 'dashboard.moduleOverviewTitle',
        titleFallback: 'Главное',
        descriptionKey: 'dashboard.moduleOverviewDescription',
        descriptionFallback: '{module}: поголовье, падёж и набор веса.',
        metricKeys: [
          'total_birds',
          'livability_pct',
          'fcr',
          'avg_weight_per_bird',
          'water_feed_ratio',
          'mortality_rate',
        ],
        chartKeys: ['factory_mortality_trend', 'factory_weight_gain'],
        breakdownKeys: ['factory_flock_performance'],
      },
      {
        id: 'operations',
        titleKey: 'dashboard.moduleOperationsTitle',
        titleFallback: 'Операции',
        descriptionKey: 'dashboard.moduleOperationsDescription',
        descriptionFallback: '{module}: корм, лекарства, отгрузки и вакцинация.',
        metricKeys: [
          'feed_consumed',
          'total_shipped',
          'shipment_revenue',
          'vacc_compliance_pct',
          'vacc_overdue',
        ],
        chartKeys: ['factory_feed_consumption', 'factory_shipments_flow'],
        breakdownKeys: [
          'factory_top_clients',
          'factory_medicine_usage_by_type',
          'factory_shipment_clients',
        ],
      },
      {
        id: 'finance',
        titleKey: 'dashboard.moduleFinanceTitle',
        titleFallback: 'Финансы',
        descriptionKey: 'dashboard.moduleFinanceDescription',
        descriptionFallback: '{module}: деньги отдела, расходы, касса и финансовый результат.',
        metricKeys: ['financial_result', 'total_expenses', 'net_cashflow', 'cash_balance'],
        chartKeys: ['factory_finance_overview', 'factory_expense_categories'],
        breakdownKeys: ['factory_expense_categories_table', 'factory_cash_accounts'],
      },
      {
        id: 'efficiency',
        titleKey: 'dashboard.moduleEfficiencyTitle',
        titleFallback: 'Риски и эффективность',
        descriptionKey: 'dashboard.moduleEfficiencyDescription',
        descriptionFallback: '{module}: падёж, вакцинации и ресурсные сигналы.',
        metricKeys: ['mortality_rate', 'vacc_overdue'],
        chartKeys: [],
        breakdownKeys: ['module_alerts'],
      },
    ],
  },
  feed_mill: {
    summaryMetricKeys: [
      'product_output',
      'shipment_rate',
      'shrinkage_pct',
      'sales_revenue',
      'active_alerts',
    ],
    sections: [
      {
        id: 'overview',
        titleKey: 'dashboard.moduleOverviewTitle',
        titleFallback: 'Главное',
        descriptionKey: 'dashboard.moduleOverviewDescription',
        descriptionFallback: '{module}: выпуск, отгрузка и коммерческий результат по продукту.',
        metricKeys: ['product_output', 'product_shipped', 'shrinkage_pct', 'sales_revenue'],
        chartKeys: ['feed_product_flow', 'feed_revenue'],
        breakdownKeys: ['feed_formulas', 'feed_clients'],
      },
      {
        id: 'finance',
        titleKey: 'dashboard.moduleFinanceTitle',
        titleFallback: 'Финансы',
        descriptionKey: 'dashboard.moduleFinanceDescription',
        descriptionFallback: '{module}: деньги отдела, расходы, касса и финансовый результат.',
        metricKeys: ['financial_result', 'total_expenses', 'net_cashflow', 'cash_balance'],
        chartKeys: ['feed_finance_overview', 'feed_expense_categories'],
        breakdownKeys: ['feed_expense_categories_table', 'feed_cash_accounts'],
      },
      {
        id: 'efficiency',
        titleKey: 'dashboard.moduleEfficiencyTitle',
        titleFallback: 'Риски и эффективность',
        descriptionKey: 'dashboard.moduleEfficiencyDescription',
        descriptionFallback: '{module}: загрузка сырья, реализация выпуска и узкие места склада.',
        metricKeys: ['shipment_rate', 'shrinkage_pct', 'stock_total'],
        chartKeys: ['feed_shipment_rate', 'feed_raw_flow'],
        breakdownKeys: ['module_alerts', 'feed_low_raw_stock'],
      },
    ],
  },
  vet_pharmacy: {
    summaryMetricKeys: [
      'current_stock',
      'stock_value_uzs',
      'value_at_risk_uzs',
      'expired_batches',
      'active_alerts',
    ],
    sections: [
      {
        id: 'overview',
        titleKey: 'dashboard.moduleOverviewTitle',
        titleFallback: 'Главное',
        descriptionKey: 'dashboard.moduleOverviewDescription',
        descriptionFallback: '{module}: остатки, движение лекарств и самые важные партии.',
        metricKeys: ['current_stock', 'stock_value_uzs', 'medicine_consumed'],
        chartKeys: ['medicine_stock', 'medicine_flow'],
        breakdownKeys: ['medicine_expiry_batches'],
      },
      {
        id: 'finance',
        titleKey: 'dashboard.moduleFinanceTitle',
        titleFallback: 'Финансы',
        descriptionKey: 'dashboard.moduleFinanceDescription',
        descriptionFallback: '{module}: деньги отдела, расходы, касса и финансовый результат.',
        metricKeys: ['financial_result', 'total_expenses', 'net_cashflow', 'cash_balance'],
        chartKeys: ['medicine_finance_overview', 'medicine_expense_categories'],
        breakdownKeys: ['medicine_expense_categories_table', 'medicine_cash_accounts'],
      },
      {
        id: 'efficiency',
        titleKey: 'dashboard.moduleEfficiencyTitle',
        titleFallback: 'Риски и эффективность',
        descriptionKey: 'dashboard.moduleEfficiencyDescription',
        descriptionFallback:
          '{module}: сроки годности, оборачиваемость и проблемные сигналы склада.',
        metricKeys: [
          'expired_batches',
          'expiring_batches',
          'value_at_risk_uzs',
          'expired_value_uzs',
          'turnover_rate',
        ],
        chartKeys: ['medicine_expiry', 'medicine_turnover_rate'],
        breakdownKeys: ['module_alerts'],
      },
    ],
  },
  slaughterhouse: {
    summaryMetricKeys: [
      'birds_processed',
      'dressing_yield_pct',
      'first_sort_weight_share_pct',
      'shipment_revenue',
      'active_alerts',
    ],
    sections: [
      {
        id: 'overview',
        titleKey: 'dashboard.moduleOverviewTitle',
        titleFallback: 'Главное',
        descriptionKey: 'dashboard.moduleOverviewDescription',
        descriptionFallback: '{module}: переработка птицы, выпуск полуфабриката и основной сбыт.',
        metricKeys: [
          'birds_processed',
          'dressing_yield_pct',
          'first_sort_weight_share_pct',
          'semi_product_output',
        ],
        chartKeys: ['slaughter_flow', 'slaughter_semi_flow'],
        breakdownKeys: ['slaughter_top_products', 'slaughter_clients'],
      },
      {
        id: 'finance',
        titleKey: 'dashboard.moduleFinanceTitle',
        titleFallback: 'Финансы',
        descriptionKey: 'dashboard.moduleFinanceDescription',
        descriptionFallback: '{module}: деньги отдела, расходы, касса и финансовый результат.',
        metricKeys: ['financial_result', 'total_expenses', 'net_cashflow', 'cash_balance'],
        chartKeys: ['slaughter_finance_overview', 'slaughter_expense_categories'],
        breakdownKeys: ['slaughter_expense_categories_table', 'slaughter_cash_accounts'],
      },
      {
        id: 'efficiency',
        titleKey: 'dashboard.moduleEfficiencyTitle',
        titleFallback: 'Риски и эффективность',
        descriptionKey: 'dashboard.moduleEfficiencyDescription',
        descriptionFallback: '{module}: качество сортировки, переработка и проблемные сигналы.',
        metricKeys: [
          'process_rate',
          'first_sort_weight_share_pct',
          'bad_weight_share_pct',
          'shipment_volume',
        ],
        chartKeys: ['slaughter_quality', 'slaughter_process_rate'],
        breakdownKeys: ['module_alerts'],
      },
      {
        id: 'quality',
        titleKey: 'dashboard.moduleQualityTitle',
        titleFallback: 'Контроль качества и тренд',
        descriptionKey: 'dashboard.moduleQualityDescription',
        descriptionFallback: '{module}: статус контроля качества и помесячный тренд выпуска.',
        metricKeys: [
          'quality_checks_passed',
          'quality_checks_failed',
          'quality_checks_pending',
          'quality_pass_rate',
        ],
        chartKeys: ['slaughter_monthly_trend'],
        breakdownKeys: ['slaughter_recent_quality_checks'],
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
