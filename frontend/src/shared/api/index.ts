export { apiClient, ApiClient } from './api-client';
export { ApiError } from './error-handler';
export { authLoginRequestSchema, authLoginResponseSchema, loginWithCredentials } from './auth';
export type { AuthLoginRequest, AuthLoginResponse } from './auth';
export {
  dashboardAlertSchema,
  dashboardAnalyticsResponseSchema,
  dashboardDepartmentDashboardSchema,
  dashboardBreakdownItemSchema,
  dashboardBreakdownSchema,
  dashboardChartSchema,
  dashboardChartSeriesSchema,
  dashboardExecutiveDashboardSchema,
  dashboardMetricSchema,
  dashboardModuleSchema,
  dashboardOverviewResponseSchema,
  dashboardOverviewScopeSchema,
  dashboardSectionSchema,
  dashboardSeriesPointSchema,
  getDashboardAnalytics,
  getDashboardOverview,
} from './dashboard';
export {
  createInventoryStockTransfer,
  getInventoryStockBalance,
  inventoryItemTypeSchema,
  inventoryStockBalanceResponseSchema,
  inventoryTransferRequestSchema,
  inventoryTransferResponseSchema,
  stockBalanceItemSchema,
} from './inventory';
export type {
  DashboardAlert,
  DashboardAnalyticsResponse,
  DashboardDepartmentDashboard,
  DashboardBreakdown,
  DashboardBreakdownItem,
  DashboardChart,
  DashboardChartSeries,
  DashboardExecutiveDashboard,
  DashboardMetric,
  DashboardModuleDashboard,
  DashboardOverviewResponse,
  DashboardOverviewScope,
  DashboardSection,
  DashboardSeriesPoint,
} from './dashboard';
export type {
  InventoryItemType,
  InventoryStockBalanceFilters,
  InventoryStockBalanceResponse,
  InventoryTransferRequest,
  InventoryTransferResponse,
  StockBalanceItem,
} from './inventory';
export { factoryFlockKpiSchema, getFactoryFlockKpi } from './factory';
export type { FactoryFlockKpi } from './factory';
export { debtsAgingResponseSchema, getDebtsAging } from './finance';
export type { DebtsAgingBuckets, DebtsAgingResponse } from './finance';
export {
  cbuSyncResponseSchema,
  createManualExchangeRate,
  currencyExchangeRateListResponseSchema,
  currencyExchangeRateSchema,
  getLatestExchangeRate,
  latestRateSchema,
  listExchangeRates,
  resolveExchangeRate,
  resolvedRateSchema,
  syncExchangeRatesFromCbu,
} from './exchange-rates';
export type {
  CbuSyncResponse,
  CreateManualExchangeRatePayload,
  CurrencyExchangeRate,
  CurrencyExchangeRateListResponse,
  LatestRate,
  ListExchangeRatesParams,
  ResolvedRate,
} from './exchange-rates';
export {
  consumeMedicine,
  medicineConsumeRequestSchema,
  medicineConsumeResponseSchema,
} from './medicine';
export type {
  MedicineConsumeAllocation,
  MedicineConsumeRequest,
  MedicineConsumeResponse,
} from './medicine';
export { baseQueryKeys, toQueryKey } from './query-keys';
export {
  getErrorMessage,
  getErrorRetryable,
  mutationDefaultConfig,
  queryDefaultConfig,
  type MutationErrorContext,
  useApiMutation,
  useApiQuery,
} from './react-query';
