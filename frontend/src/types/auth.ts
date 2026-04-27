export type ModuleLevel = 'none' | 'r' | 'rw' | 'admin';

export const LEVEL_ORDER: Record<ModuleLevel, number> = {
  none: 0,
  r: 1,
  rw: 2,
  admin: 3,
};

export interface OrganizationLite {
  id: string;
  code: string;
  name: string;
  direction: 'broiler' | 'egg' | 'mixed';
  timezone: string;
  accounting_currency: string;
}

export interface Membership {
  id: string;
  organization: OrganizationLite;
  position_title: string;
  work_phone: string;
  work_status: 'active' | 'vacation' | 'sick_leave' | 'terminated';
  is_active: boolean;
  joined_at: string;
  module_permissions: Record<string, ModuleLevel>;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  phone: string;
  is_active: boolean;
  is_staff: boolean;
  is_superuser: boolean;
  last_login: string | null;
  memberships: Membership[];
}

export interface Organization extends OrganizationLite {
  legal_name: string;
  inn: string;
  legal_address: string;
  accounting_currency_code: string;
  logo: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface TokenPair {
  access: string;
  refresh: string;
}

// ─── settings-related ─────────────────────────────────────────────────────

export interface ModuleRef {
  id: string;
  code: string;
  name: string;
  kind: string;
  icon: string;
  sort_order: number;
  is_active: boolean;
}

export interface OrganizationModuleRow {
  id: string;
  organization: string;
  module: string;
  module_code: string;
  module_name: string;
  module_kind: string;
  is_enabled: boolean;
  enabled_at: string | null;
  settings_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface GLSubaccount {
  id: string;
  account: string;
  account_code?: string | null;
  account_name?: string | null;
  code: string;
  name: string;
  module: string | null;
  module_code?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface GLAccount {
  id: string;
  code: string;
  name: string;
  type: string;
  subaccounts?: GLSubaccount[];
}

export type ExpenseArticleKind = 'expense' | 'income' | 'salary' | 'transfer';

export interface ExpenseArticle {
  id: string;
  code: string;
  name: string;
  kind: ExpenseArticleKind;

  default_subaccount: string | null;
  default_subaccount_code: string | null;
  default_subaccount_name: string | null;

  default_module: string | null;
  default_module_code: string | null;

  parent: string | null;
  parent_code: string | null;
  parent_name: string | null;

  is_active: boolean;
  notes: string;
  created_at: string;
  updated_at: string;
}

// ─── Payment (apps.payments) ─────────────────────────────────────────────

export type PaymentDirection = 'out' | 'in';
export type PaymentChannel = 'cash' | 'transfer' | 'click' | 'other';
export type PaymentKind = 'counterparty' | 'opex' | 'income' | 'salary' | 'internal';
export type PaymentStatus = 'draft' | 'confirmed' | 'posted' | 'cancelled';

export interface PaymentAllocation {
  id: string;
  target_content_type: number;
  target_model?: string;
  target_object_id: string;
  amount_uzs: string;
  notes: string;
  created_at: string;
}

export interface Payment {
  id: string;
  doc_number: string;
  date: string;

  module: string | null;
  module_code?: string | null;

  direction: PaymentDirection;
  channel: PaymentChannel;
  kind: PaymentKind;
  status: PaymentStatus;

  counterparty: string | null;
  counterparty_name?: string | null;

  currency: string | null;
  currency_code?: string | null;
  exchange_rate: string | null;
  exchange_rate_source: string | null;
  amount_foreign: string | null;
  amount_uzs: string;

  cash_subaccount: string | null;
  cash_subaccount_code?: string | null;
  cash_subaccount_name?: string | null;

  contra_subaccount: string | null;
  contra_subaccount_code?: string | null;
  contra_subaccount_name?: string | null;

  expense_article: string | null;
  expense_article_code?: string | null;
  expense_article_name?: string | null;

  journal_entry: string | null;
  posted_at: string | null;

  notes: string;
  allocations: PaymentAllocation[];

  created_at: string;
  updated_at: string;
}

export interface AuditLogEntry {
  id: string;
  module: string | null;
  module_code?: string | null;
  actor: string | null;
  actor_email?: string | null;
  action: string;
  action_verb: string;
  entity_content_type: number | null;
  entity_object_id: string | null;
  entity_repr: string;
  entity_type?: string | null;
  ip_address: string | null;
  user_agent: string;
  diff: Record<string, unknown> | null;
  occurred_at: string;
}

export interface ExchangeRate {
  id: string;
  currency: string;
  currency_code?: string;
  date: string;
  rate: string;
  nominal: number;
  source: string;
  fetched_at: string;
}

export interface CurrencyRef {
  id: string;
  code: string;
  numeric_code: string;
  name_ru: string;
  name_en: string;
  is_active: boolean;
}

// ─── stock / ledger ───────────────────────────────────────────────────────

export type StockMovementKind = 'incoming' | 'outgoing' | 'transfer' | 'write_off';

export interface StockMovement {
  id: string;
  doc_number: string;
  kind: StockMovementKind;
  date: string;
  module: string | null;
  nomenclature: string;
  quantity: string;
  unit_price_uzs: string;
  amount_uzs: string;
  warehouse_from: string | null;
  warehouse_to: string | null;
  counterparty: string | null;
  batch: string | null;
  module_code: string | null;
  nomenclature_sku: string | null;
  nomenclature_name: string | null;
  warehouse_from_code: string | null;
  warehouse_to_code: string | null;
  counterparty_code: string | null;
  counterparty_name: string | null;
  batch_doc_number: string | null;
  is_manual: boolean;
  created_at: string;
  updated_at: string;
}

export interface WarehouseRef {
  id: string;
  code: string;
  name: string;
  module: string;
  module_code: string;
  module_name: string;
  production_block: string | null;
  production_block_code?: string | null;
  production_block_name?: string | null;
  default_gl_subaccount: string | null;
  default_gl_subaccount_code?: string | null;
  default_gl_subaccount_name?: string | null;
  is_active: boolean;
}

export interface JournalEntry {
  id: string;
  doc_number: string;
  module: string | null;
  entry_date: string;
  description: string;
  debit_subaccount: string;
  credit_subaccount: string;
  amount_uzs: string;
  currency: string | null;
  amount_foreign: string | null;
  exchange_rate: string | null;
  source_content_type: number | null;
  source_object_id: string | null;
  counterparty: string | null;
  batch: string | null;
  debit_code: string | null;
  credit_code: string | null;
  module_code: string | null;
  currency_code: string | null;
  counterparty_name: string | null;
  batch_doc_number: string | null;
  created_at: string;
}

// ─── RBAC ─────────────────────────────────────────────────────────────────

export interface RolePermissionRow {
  id: string;
  role: string;
  module: string;
  level: ModuleLevel;
  module_code: string;
  module_name: string;
  created_at: string;
  updated_at: string;
}

export interface RoleFull {
  id: string;
  code: string;
  name: string;
  description: string;
  is_system: boolean;
  is_active: boolean;
  permissions: RolePermissionRow[];
  created_at: string;
  updated_at: string;
}

export interface UserRoleAssignment {
  id: string;
  membership: string;
  role: string;
  assigned_by: string | null;
  assigned_at: string;
  role_code: string | null;
  role_name: string | null;
  user_email: string | null;
  created_at: string;
  updated_at: string;
}

export interface MembershipRow {
  id: string;
  user: string;
  organization: string;
  is_active: boolean;
  position_title: string;
  work_phone: string;
  work_status: string;
  joined_at: string;
  user_email: string;
  user_full_name: string;
  organization_code: string;
  created_at: string;
  updated_at: string;
}

// ─── holding ──────────────────────────────────────────────────────────────

export interface HoldingCompany {
  id: string;
  code: string;
  name: string;
  direction: 'broiler' | 'egg' | 'mixed';
  accounting_currency: string;
  is_active: boolean;
  purchases_confirmed_uzs: string;
  payments_in_uzs: string;
  payments_out_uzs: string;
  creditor_balance_uzs: string;
  debtor_balance_uzs: string;
  active_batches: number;
  modules_count: number;
  period_from: string;
  period_to: string;
}

export interface HoldingTotals {
  companies: number;
  modules: number;
  active_batches: number;
  purchases_confirmed_uzs: string;
  payments_in_uzs: string;
  payments_out_uzs: string;
  creditor_balance_uzs: string;
  debtor_balance_uzs: string;
}

export interface HoldingPayload {
  companies: HoldingCompany[];
  totals: HoldingTotals;
}

// ─── dashboard ────────────────────────────────────────────────────────────

export interface DashboardKpis {
  period: { from: string; to: string };
  purchases_confirmed_uzs: string;
  creditor_balance_uzs: string;
  debtor_balance_uzs: string;
  payments_in_uzs: string;
  payments_out_uzs: string;
  sales_revenue_uzs: string;
  sales_cost_uzs: string;
  sales_margin_uzs: string;
  active_batches: number;
  transfers_pending: number;
  purchases_drafts: number;
  sales_drafts: number;
  payments_drafts: number;
}

export interface DashboardProduction {
  matochnik_heads: number;
  feedlot_heads: number;
  incubation_runs: number;
  incubation_eggs_loaded: number;
}

export type DashboardCashChannel = { label: string; balance_uzs: string };

export interface DashboardCash {
  /** Сводный остаток по всем каналам. */
  _total_uzs: string;
  /** По channel-коду (cash/transfer/click/other) — баланс этого канала. */
  [channel: string]: DashboardCashChannel | string;
}

export interface DashboardSummary {
  kpis: DashboardKpis;
  production: DashboardProduction;
  cash: DashboardCash;
}

export interface CashflowPoint {
  date: string;
  in_uzs: string;
  out_uzs: string;
}

export interface CashflowPayload {
  days: number;
  points: CashflowPoint[];
}

// ─── core directories (counterparties / nomenclature / blocks) ────────────

export type CounterpartyKind = 'supplier' | 'buyer' | 'other';

export interface Counterparty {
  id: string;
  code: string;
  kind: CounterpartyKind;
  name: string;
  inn: string;
  specialization: string;
  phone: string;
  email: string;
  address: string;
  balance_uzs: string;
  is_active: boolean;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface Unit {
  id: string;
  code: string;
  name: string;
}

export interface Category {
  id: string;
  name: string;
  parent: string | null;
  parent_name?: string | null;
  module: string | null;
  module_code?: string | null;
  module_name?: string | null;
  default_gl_subaccount: string | null;
}

export interface NomenclatureItem {
  id: string;
  sku: string;
  name: string;
  category: string;
  category_name?: string | null;
  /** Из category.module — указывает к какому модулю относится SKU. */
  module_code?: string | null;
  unit: string;
  unit_code?: string | null;
  default_gl_subaccount: string | null;
  default_gl_subaccount_code?: string | null;
  barcode: string;
  is_active: boolean;
  notes: string;
  /** Базисная влажность (для приёмки сырья по формуле Дюваля). null если не применимо. */
  base_moisture_pct: string | null;
  created_at: string;
  updated_at: string;
}

export type RawMaterialBatchStatus = 'quarantine' | 'available' | 'rejected' | 'depleted';

export interface RawMaterialBatch {
  id: string;
  doc_number: string;
  module: string;
  nomenclature: string;
  nomenclature_sku: string | null;
  nomenclature_name: string | null;
  supplier: string | null;
  supplier_name: string | null;
  purchase: string | null;
  warehouse: string;
  warehouse_code: string | null;
  storage_bin: string;
  received_date: string;
  // Веса
  gross_weight_kg: string | null;
  settlement_weight_kg: string | null;
  quantity: string;
  current_quantity: string;
  // Усушка
  moisture_pct_actual: string | null;
  moisture_pct_base: string | null;
  dockage_pct_actual: string | null;
  shrinkage_pct: string | null;
  // Прочее
  unit: string;
  unit_code: string | null;
  price_per_unit_uzs: string;
  total_cost_uzs: string;
  status: RawMaterialBatchStatus;
  quarantine_until: string | null;
  rejection_reason: string;
  notes: string;
  created_at: string;
  updated_at: string;
}

export type BlockKind =
  | 'matochnik'
  | 'incubation'
  | 'hatcher'
  | 'feedlot'
  | 'slaughter_line'
  | 'warehouse'
  | 'vet_storage'
  | 'mixer_line'
  | 'storage_bin'
  | 'other';

export interface ProductionBlock {
  id: string;
  code: string;
  name: string;
  module: string;
  module_code: string;
  module_name: string;
  kind: BlockKind;
  area_m2: string | null;
  capacity: string | null;
  capacity_unit: string | null;
  capacity_unit_code: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// ─── production modules ───────────────────────────────────────────────────

// matochnik
export interface BreedingHerd {
  id: string;
  doc_number: string;
  module: string;
  block: string;
  block_code: string | null;
  direction: 'broiler_parent' | 'layer_parent';
  source_counterparty: string | null;
  source_batch: string | null;
  placed_at: string;
  initial_heads: number;
  current_heads: number;
  age_weeks_at_placement: number;
  current_age_weeks: number | null;
  status: 'growing' | 'producing' | 'depopulated';
  technologist: string;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface DailyEggProduction {
  id: string;
  herd: string;
  herd_doc: string | null;
  date: string;
  eggs_collected: number;
  unfit_eggs: number;
  outgoing_batch: string | null;
  notes: string;
  created_at: string;
}

export type MortalityCause =
  | 'disease' | 'trauma' | 'heat_stress' | 'suffocation'
  | 'culling' | 'other' | 'unknown';

export interface BreedingMortality {
  id: string;
  herd: string;
  date: string;
  dead_count: number;
  cause: MortalityCause;
  cause_detail: string;
  notes: string;
  recorded_by: string | null;
  created_at: string;
}

export interface BreedingFeedConsumption {
  id: string;
  herd: string;
  date: string;
  feed_batch: string | null;
  feed_batch_doc: string | null;
  feed_batch_recipe: string | null;
  unit_cost_uzs: string | null;
  total_cost_uzs: string | null;
  quantity_kg: string;
  per_head_g: string | null;
  notes: string;
  created_at: string;
}

// incubation
export type IncubationStatus = 'incubating' | 'hatching' | 'transferred' | 'cancelled';

export interface IncubationRun {
  id: string;
  doc_number: string;
  module: string;
  incubator_block: string;
  incubator_block_code: string | null;
  hatcher_block: string | null;
  hatcher_block_code: string | null;
  batch: string;
  batch_doc: string | null;
  loaded_date: string;
  expected_hatch_date: string;
  actual_hatch_date: string | null;
  eggs_loaded: number;
  eggs_broken_on_load: number;
  fertile_eggs: number | null;
  hatched_count: number | null;
  discarded_count: number | null;
  days_total: number;
  current_day: number | null;
  days_remaining?: number | null;
  hatchability_pct?: string | null;
  mortality_pct?: string | null;
  status: IncubationStatus;
  technologist: string;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface IncubationRegimeDay {
  id: string;
  run: string;
  day: number;
  temperature_c: string;
  humidity_percent: string;
  egg_turns_per_day: number;
  actual_temperature_c: string | null;
  actual_humidity_percent: string | null;
  observed_at: string | null;
  observed_by: string | null;
  observed_by_name: string | null;
  notes: string;
  created_at: string;
}

export interface MirageInspection {
  id: string;
  run: string;
  inspection_date: string;
  day_of_incubation: number;
  inspected_count: number;
  fertile_count: number;
  discarded_count: number;
  inspector: string | null;
  inspector_name: string | null;
  infertile_pct: string | null;
  notes: string;
  created_at: string;
}

export type IncubationTimelineEventType =
  | 'load' | 'mirage' | 'regime' | 'transfer_to_hatcher' | 'hatch' | 'cancel';

export interface IncubationTimelineEvent {
  type: IncubationTimelineEventType;
  date: string;
  id: string;
  title: string;
  subtitle: string;
  notes: string;
  inspector_name?: string | null;
}

export interface IncubationStats {
  run_id: string;
  status: IncubationStatus;
  current_day: number;
  days_remaining: number;
  hatchability_pct: string | null;
  mortality_pct: string | null;
  eggs_loaded: number;
  eggs_remaining: number;
  hatched_count: number | null;
  discarded_count: number | null;
  regime_days_count: number;
  mirage_inspections_count: number;
  last_regime_temp_c: string | null;
  last_regime_humidity_pct: string | null;
}

// feed
export interface Recipe {
  id: string;
  code: string;
  name: string;
  direction: string;
  age_range: string;
  is_medicated: boolean;
  is_active: boolean;
  notes: string;
  versions_count: number;
  created_at: string;
  updated_at: string;
}

export interface RecipeComponent {
  id: string;
  recipe_version: string;
  nomenclature: string;
  nomenclature_sku: string | null;
  nomenclature_name: string | null;
  share_percent: string;
  min_share_percent: string | null;
  max_share_percent: string | null;
  is_medicated: boolean;
  withdrawal_period_days: number;
  vet_drug: string | null;
  vet_drug_sku: string | null;
  sort_order: number;
}

export interface RecipeVersion {
  id: string;
  recipe: string;
  recipe_code: string | null;
  version_number: number;
  status: 'draft' | 'active' | 'archived';
  effective_from: string;
  target_protein_percent: string | null;
  target_fat_percent: string | null;
  target_fibre_percent: string | null;
  target_lysine_percent: string | null;
  target_methionine_percent: string | null;
  target_threonine_percent: string | null;
  target_me_kcal_per_kg: string | null;
  comment: string;
  author: string | null;
  components: RecipeComponent[];
  created_at: string;
  updated_at: string;
}

export type ProductionTaskStatus =
  | 'planned' | 'running' | 'paused' | 'done' | 'cancelled';

export interface ProductionTaskComponent {
  id: string;
  task: string;
  nomenclature: string;
  nomenclature_sku: string | null;
  nomenclature_name: string | null;
  /**
   * Партия сырья, которая будет списана. null если не нашлось доступной
   * партии этой номенклатуры — в этом случае замес провести нельзя.
   */
  source_batch: string | null;
  source_batch_doc_number: string | null;
  planned_quantity: string;
  actual_quantity: string | null;
  planned_price_per_unit_uzs: string;
  actual_price_per_unit_uzs: string | null;
  lab_result_snapshot: string | null;
  sort_order: number;
}

export interface ProductionTask {
  id: string;
  doc_number: string;
  recipe_version: string;
  production_line: string;
  shift: 'day' | 'night';
  scheduled_at: string;
  started_at: string | null;
  completed_at: string | null;
  planned_quantity_kg: string;
  actual_quantity_kg: string | null;
  status: ProductionTaskStatus;
  is_medicated: boolean;
  withdrawal_period_days: number;
  operator: string | null;
  technologist: string;
  notes: string;
  /** Заполняется бэкэндом автокопированием из версии при создании задания. */
  components: ProductionTaskComponent[];
  created_at: string;
  updated_at: string;
}

export type FeedBatchStatus = 'quality_check' | 'approved' | 'rejected' | 'depleted';

export type FeedBatchPassportStatus = 'pending' | 'passed' | 'failed';

export interface FeedBatch {
  id: string;
  doc_number: string;
  module: string;
  produced_by_task: string;
  recipe_version: string;
  recipe_code: string | null;
  produced_at: string;
  quantity_kg: string;
  current_quantity_kg: string;
  unit_cost_uzs: string;
  total_cost_uzs: string;
  storage_bin: string | null;
  storage_bin_code: string | null;
  storage_warehouse: string | null;
  status: FeedBatchStatus;
  is_medicated: boolean;
  withdrawal_period_days: number;
  withdrawal_period_ends: string | null;
  quality_passport_status: string | null;
  task_doc_number: string | null;
  notes: string;
  created_at: string;
  updated_at: string;
}

// feedlot
export type FeedlotStatus = 'placed' | 'growing' | 'ready_slaughter' | 'shipped';

export interface FeedlotBatch {
  id: string;
  doc_number: string;
  house_block: string;
  house_code?: string | null;
  batch: string;
  batch_doc?: string | null;
  placed_date: string;
  target_slaughter_date: string | null;
  target_weight_kg: string;
  initial_heads: number;
  current_heads: number;
  status: FeedlotStatus;
  technologist: string;
  notes: string;
  // Computed KPI (read-only от бэка)
  days_on_feedlot?: number;
  survival_pct?: string;
  total_mortality_pct?: string;
  current_avg_weight_kg?: string | null;
  total_feed_kg?: string;
  total_gain_kg?: string;
  total_fcr?: string | null;
  created_at: string;
  updated_at: string;
}

export interface DailyWeighing {
  id: string;
  feedlot_batch: string;
  date: string;
  day_of_age: number;
  sample_size: number;
  avg_weight_kg: string;
  gain_kg: string | null;
  notes: string;
}

export interface FeedlotMortality {
  id: string;
  feedlot_batch: string;
  date: string;
  day_of_age: number;
  dead_count: number;
  cause: string;
  notes: string;
}

export type FeedConsumptionType = 'start' | 'growth' | 'finish';

export interface FeedlotFeedConsumption {
  id: string;
  feedlot_batch: string;
  period_from_day: number;
  period_to_day: number;
  feed_type: FeedConsumptionType;
  feed_batch: string | null;
  feed_batch_doc: string | null;
  total_kg: string;
  per_head_g: string | null;
  period_fcr: string | null;
  notes: string;
  created_at: string;
}

export interface FeedlotStats {
  batch_id: string;
  days_on_feedlot: number;
  initial_heads: number;
  current_heads: number;
  dead_count: number;
  survival_pct: string;
  total_mortality_pct: string;
  current_avg_weight_kg: string | null;
  initial_avg_weight_kg: string | null;
  total_gain_kg: string;
  total_feed_kg: string;
  total_fcr: string | null;
  target_weight_kg: string;
  target_slaughter_date: string | null;
  projected_slaughter_date: string | null;
  status: FeedlotStatus;
}

export type FeedlotTimelineEventType =
  | 'placed' | 'weighing' | 'feed' | 'mortality' | 'shipped';

export interface FeedlotTimelineEvent {
  type: FeedlotTimelineEventType;
  date: string;
  id: string;
  title: string;
  subtitle: string;
  notes: string;
}

// slaughter
export type SlaughterStatus = 'active' | 'closed' | 'posted' | 'cancelled';

export interface SlaughterShift {
  id: string;
  doc_number: string;
  module: string;
  line_block: string;
  line_code: string | null;
  source_batch: string;
  batch_doc: string | null;
  shift_date: string;
  start_time: string | null;
  end_time: string | null;
  live_heads_received: number;
  live_weight_kg_total: string;
  status: SlaughterStatus;
  foreman: string;
  notes: string;
  // Computed KPI (read-only)
  total_output_kg: string;
  total_output_pct: string | null;
  waste_kg: string | null;
  waste_pct: string | null;
  carcass_kg: string;
  carcass_yield_pct: string | null;
  yield_per_head_kg: string | null;
  defect_rate: string | null;
  quality_checked: boolean;
  yields_count: number;
  lab_pending_count: number;
  lab_passed_count: number;
  lab_failed_count: number;
  created_at: string;
  updated_at: string;
}

export type SlaughterGrade = 'grade_1' | 'grade_2' | 'substandard';

export interface SlaughterYield {
  id: string;
  shift: string;
  nomenclature: string;
  grade: SlaughterGrade;
  nom_sku: string | null;
  nom_name: string | null;
  quantity: string;
  unit: string;
  unit_code: string | null;
  share_percent: string | null;
  output_batch: string | null;
  output_batch_doc: string | null;
  notes: string;
  // Computed (read-only)
  yield_pct: string | null;       // % от живого веса
  norm_pct: string | null;        // норма по бройлеру
  deviation_pct: string | null;   // факт − норма
  is_within_tolerance: boolean;
  created_at: string;
}

export interface SlaughterQualityCheck {
  id: string;
  shift: string;
  carcass_defect_percent: string | null;
  trauma_percent: string | null;
  cooling_temperature_c: string | null;
  confiscation_percent: string | null;
  vet_inspection_passed: boolean;
  inspector: string;
  inspector_name: string | null;
  inspected_at: string;
  notes: string;
  created_at: string;
}

export type SlaughterLabStatus = 'pending' | 'passed' | 'failed';

export interface SlaughterLabTest {
  id: string;
  shift: string;
  indicator: string;
  normal_range: string;
  actual_value: string;
  status: SlaughterLabStatus;
  sampled_at: string | null;
  result_at: string | null;
  operator: string | null;
  operator_name: string | null;
  notes: string;
  created_at: string;
}

export interface SlaughterYieldBreakdownRow {
  sku: string;
  name: string;
  quantity_kg: string;
  yield_pct: string | null;
  norm_pct: string | null;
  deviation_pct: string | null;
  is_within_tolerance: boolean;
}

export interface SlaughterStats {
  shift_id: string;
  live_heads: number;
  live_weight_kg: string;
  total_output_kg: string;
  total_output_pct: string | null;
  waste_kg: string | null;
  waste_pct: string | null;
  carcass_kg: string;
  carcass_yield_pct: string | null;
  yield_per_head_kg: string | null;
  defect_rate: string | null;
  quality_checked: boolean;
  yields_count: number;
  lab_pending_count: number;
  lab_passed_count: number;
  lab_failed_count: number;
  breakdown: SlaughterYieldBreakdownRow[];
}

export type SlaughterTimelineEventType =
  | 'created' | 'quality' | 'lab' | 'yield' | 'posted' | 'reversed';

export interface SlaughterTimelineEvent {
  type: SlaughterTimelineEventType;
  id: string;
  date: string;
  title: string;
  subtitle: string;
  notes: string;
}

// transfers
export type TransferState =
  | 'draft' | 'awaiting_acceptance' | 'under_review' | 'posted' | 'cancelled';

export interface InterModuleTransfer {
  id: string;
  doc_number: string;
  transfer_date: string;
  from_module: string;
  from_module_code: string | null;
  from_module_name: string | null;
  to_module: string;
  to_module_code: string | null;
  to_module_name: string | null;
  from_block: string | null;
  from_block_code: string | null;
  to_block: string | null;
  to_block_code: string | null;
  from_warehouse: string | null;
  from_warehouse_code: string | null;
  to_warehouse: string | null;
  to_warehouse_code: string | null;
  nomenclature: string;
  nomenclature_sku: string | null;
  nomenclature_name: string | null;
  unit: string;
  unit_code: string | null;
  quantity: string;
  cost_uzs: string;
  batch: string | null;
  batch_doc_number: string | null;
  feed_batch: string | null;
  feed_batch_doc_number: string | null;
  state: TransferState;
  review_reason: string;
  posted_at: string | null;
  notes: string;
  created_at: string;
  updated_at: string;
}

// vet
export type DrugType = 'vaccine' | 'antibiotic' | 'vitamin' | 'electrolyte' | 'other';
export type DrugRoute = 'injection' | 'oral' | 'drinking_water' | 'spray' | 'other';

export interface VetDrug {
  id: string;
  module: string;
  nomenclature: string;
  nomenclature_sku: string | null;
  nomenclature_name: string | null;
  drug_type: DrugType;
  administration_route: DrugRoute;
  default_withdrawal_days: number;
  storage_conditions: string;
  is_active: boolean;
  notes: string;
  created_at: string;
  updated_at: string;
}

export type VetStockStatus =
  | 'available' | 'quarantine' | 'expiring_soon' | 'expired' | 'depleted' | 'recalled';

export interface VetStockBatch {
  id: string;
  doc_number: string;
  module: string;
  drug: string;
  drug_sku: string | null;
  drug_name: string | null;
  drug_type: DrugType | null;
  lot_number: string;
  warehouse: string;
  warehouse_code: string | null;
  supplier: string;
  supplier_name: string | null;
  purchase: string | null;
  received_date: string;
  expiration_date: string;
  quantity: string;
  current_quantity: string;
  unit: string;
  unit_code: string | null;
  price_per_unit_uzs: string;
  status: VetStockStatus;
  quarantine_until: string | null;
  barcode: string | null;
  recalled_at: string | null;
  recall_reason: string;
  // Computed (read-only)
  days_to_expiry: number | null;
  is_expired: boolean;
  is_expiring_soon: boolean;
  notes: string;
  created_at: string;
  updated_at: string;
}

/**
 * Public-данные лота для сканера (без чувствительной информации).
 * Возвращается из /api/vet/public/scan/<barcode>/.
 */
export interface VetStockBatchPublic {
  id: string;
  barcode: string;
  drug_sku: string | null;
  drug_name: string | null;
  drug_type: DrugType | null;
  drug_type_display: string | null;
  lot_number: string;
  expiration_date: string;
  current_quantity: string;
  unit_code: string | null;
  price_per_unit_uzs: string;
  status: VetStockStatus;
  days_to_expiry: number | null;
  is_expired: boolean;
  is_expiring_soon: boolean;
}

export interface SellerDeviceToken {
  id: string;
  user: string;
  user_full_name: string;
  user_email: string | null;
  label: string;
  is_active: boolean;
  masked_token: string;
  last_used_at: string | null;
  revoked_at: string | null;
  created_at: string;
  // token приходит ТОЛЬКО при создании
  token?: string;
}

export type BatchState = 'active' | 'in_transit' | 'completed' | 'rejected' | 'review';

export interface Batch {
  id: string;
  doc_number: string;
  nomenclature: string;
  nomenclature_sku: string | null;
  nomenclature_name: string | null;
  unit: string;
  unit_code: string | null;
  origin_module: string;
  origin_module_code: string | null;
  current_module: string | null;
  current_module_code: string | null;
  current_block: string | null;
  current_block_code: string | null;
  current_quantity: string;
  initial_quantity: string;
  /** Зарезервировано в DRAFT-продажах (см. backend BatchSerializer). */
  reserved_quantity?: string;
  /** current_quantity − reserved_quantity. Сколько ещё можно продать. */
  available_quantity?: string;
  accumulated_cost_uzs: string;
  state: BatchState;
  started_at: string;
  completed_at: string | null;
  withdrawal_period_ends: string | null;
  parent_batch: string | null;
  parent_doc_number: string | null;
  origin_purchase: string | null;
  origin_counterparty: string | null;
  notes: string;
  created_at: string;
  updated_at: string;
}

// ─── Batch trace (apps/batches/views.py::trace) ─────────────────────────

export type BatchCostCategory =
  | 'egg_inherited' | 'feed' | 'vet' | 'labor' | 'utilities'
  | 'depreciation' | 'transfer_in' | 'other';

export interface BatchChainStep {
  id: string;
  batch: string;
  sequence: number;
  module: string;
  module_code: string | null;
  block: string | null;
  block_code: string | null;
  entered_at: string;
  exited_at: string | null;
  quantity_in: string;
  quantity_out: string | null;
  accumulated_cost_at_exit: string | null;
  transfer_in: string | null;
  transfer_out: string | null;
  transfer_in_doc: string | null;
  transfer_out_doc: string | null;
  note: string;
}

export interface BatchCostEntry {
  id: string;
  batch: string;
  category: BatchCostCategory;
  amount_uzs: string;
  description: string;
  occurred_at: string;
  module: string | null;
  module_code: string | null;
  source_content_type: number | null;
  source_object_id: string | null;
  created_at: string;
}

export interface BatchRelativeSnapshot {
  id: string;
  doc_number: string;
  nomenclature_sku: string | null;
  current_quantity: string;
  accumulated_cost_uzs: string;
  state: BatchState;
  current_module?: string | null;
}

export interface BatchCostBreakdownItem {
  category: BatchCostCategory;
  category_label: string;
  amount_uzs: string;
  share_percent: string;
}

export interface BatchTraceTotals {
  total_cost_uzs: string;
  accumulated_cost_uzs: string;
  unit_cost_uzs: string;
  initial_quantity: string;
  current_quantity: string;
}

export interface BatchTrace {
  batch: Batch;
  parent: BatchRelativeSnapshot | null;
  children: BatchRelativeSnapshot[];
  chain_steps: BatchChainStep[];
  cost_breakdown: BatchCostBreakdownItem[];
  totals: BatchTraceTotals;
}

export interface VetTreatmentLog {
  id: string;
  doc_number: string;
  module: string;
  treatment_date: string;
  target_block: string;
  target_block_code: string | null;
  target_batch: string | null;
  target_batch_doc: string | null;
  target_herd: string | null;
  target_herd_doc: string | null;
  drug: string;
  drug_sku: string | null;
  stock_batch: string;
  stock_batch_lot: string | null;
  dose_quantity: string;
  unit: string;
  heads_treated: number;
  withdrawal_period_days: number;
  administration_route: DrugRoute | null;
  veterinarian: string;
  technician: string | null;
  schedule_item: string | null;
  indication: string;
  notes: string;
  cancelled_at: string | null;
  cancel_reason: string;
  cancelled_by: string | null;
  created_at: string;
  updated_at: string;
}


// ─── Sales (apps/sales) ──────────────────────────────────────────────────

export type SaleStatus = 'draft' | 'confirmed' | 'cancelled';
export type SalePaymentStatus = 'unpaid' | 'partial' | 'paid' | 'overpaid';

export interface SaleItem {
  id: string;
  nomenclature: string;
  nomenclature_sku?: string | null;
  nomenclature_name?: string | null;

  // XOR: ровно одна партия из трёх
  batch: string | null;
  vet_stock_batch: string | null;
  feed_batch: string | null;

  quantity: string;
  unit_price_uzs: string;

  // snapshot, заполняется при confirm
  cost_per_unit_uzs: string | null;
  line_total_uzs: string;
  line_cost_uzs: string;
}

export interface SaleOrder {
  id: string;
  doc_number: string;
  date: string;

  module: string;
  module_code?: string | null;

  customer: string;
  customer_name?: string | null;
  warehouse: string;
  warehouse_code?: string | null;

  status: SaleStatus;

  // FX-snapshot (заполняется после confirm)
  currency: string | null;
  currency_code?: string | null;
  exchange_rate: string | null;
  exchange_rate_source: string | null;
  amount_foreign: string | null;
  amount_uzs: string;
  cost_uzs: string;

  // payments
  paid_amount_uzs: string;
  payment_status: SalePaymentStatus;
  due_date: string | null;

  // derived
  margin_uzs?: string;
  /** Σ qty*unit_price по позициям. Заполнено только для DRAFT, иначе null. */
  draft_total_uzs?: string | null;

  items: SaleItem[];

  notes: string;
  created_at: string;
  updated_at: string;
}

// ─── Purchases (apps/purchases) ──────────────────────────────────────────

export type PurchaseStatus = 'draft' | 'confirmed' | 'paid' | 'cancelled';
export type PurchasePaymentStatus = 'unpaid' | 'partial' | 'paid' | 'overpaid';

export interface PurchaseItem {
  id: string;
  nomenclature: string;
  quantity: string;
  received_qty: string;
  unit_price: string;
  line_total_foreign: string | null;
  line_total_uzs: string;
}

export interface PurchaseOrder {
  id: string;
  content_type_id: number;
  doc_number: string;
  date: string;

  module: string;

  counterparty: string;
  counterparty_name?: string | null;
  warehouse: string;

  status: PurchaseStatus;
  payment_status: PurchasePaymentStatus;
  paid_amount_uzs: string;

  // FX snapshot (заполняется после confirm)
  currency: string | null;
  currency_code?: string | null;
  exchange_rate: string | null;
  exchange_rate_source: string | null;
  amount_foreign: string | null;
  amount_uzs: string;

  batch: string | null;

  items: PurchaseItem[];

  notes: string;
  created_at: string;
  updated_at: string;
}
