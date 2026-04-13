import type { CrudFieldMeta, CrudFieldReference, CrudRecord } from '@/shared/api/backend-crud';
import type { InventoryItemType } from '@/shared/api/inventory';
import { getReadableReferenceLabel } from '@/shared/lib/reference-label';
import { isValidUuid } from '@/shared/lib/uuid';

export type FormValues = Record<string, string | boolean | string[]>;
export type FormErrors = Record<string, string>;
export type SubmitMode = 'create' | 'update';
export type ModuleViewMode = 'records' | 'stats';
export type ResourceCategoryGroupId = 'finance' | 'people_clients' | 'operations';
export type ResourceUiConfig = {
  formOrder?: string[];
  tableOrder?: string[];
  hiddenFields?: string[];
  hideDepartmentFieldWhenScoped?: boolean;
  hideOrganizationFieldWhenScoped?: boolean;
};
export type DepartmentRecord = CrudRecord & {
  id?: string;
  name?: string;
  code?: string;
  module_key?: string;
  organization_id?: string;
  parent_department_id?: string | null;
};
export type AuditSnapshot = Record<string, unknown>;
export type ResourceCategoryCandidate = {
  key: string;
  permissionPrefix: string;
};

export const EMPTY_TEXT = '';
export const MASKED_PASSWORD_VALUE = '********';
export const FORM_HIDDEN_FIELDS = new Set(['is_active']);
const MODULE_DEFAULT_INVENTORY_ITEM_TYPES: Record<string, InventoryItemType> = {
  egg: 'egg',
  incubation: 'chick',
  factory: 'chick',
  feed: 'feed',
  medicine: 'medicine',
  slaughter: 'semi_product',
};
const FINANCE_RESOURCE_PERMISSION_PREFIXES = new Set([
  'expense_category',
  'expense',
  'cash_account',
  'cash_transaction',
  'client_debt',
  'currency',
]);
const PEOPLE_RESOURCE_PERMISSION_PREFIXES = new Set(['employee', 'client']);
const PEOPLE_RESOURCE_KEYS = new Set(['factory-clients']);
export const isPasswordFieldName = (fieldName: string): boolean =>
  fieldName.toLowerCase().includes('password');
export const getDefaultInventoryItemTypeForModule = (
  moduleKey: string,
  fallback: InventoryItemType = 'egg',
): InventoryItemType => {
  const normalizedModuleKey = moduleKey.trim().toLowerCase();
  return MODULE_DEFAULT_INVENTORY_ITEM_TYPES[normalizedModuleKey] ?? fallback;
};
export const isCodeFieldName = (fieldName: string): boolean => {
  const normalizedFieldName = fieldName.trim().toLowerCase();
  return normalizedFieldName === 'code' || normalizedFieldName.endsWith('_code');
};

const CYRILLIC_TO_LATIN_MAP: Record<string, string> = {
  а: 'a',
  б: 'b',
  в: 'v',
  г: 'g',
  д: 'd',
  е: 'e',
  ё: 'e',
  ж: 'zh',
  з: 'z',
  и: 'i',
  й: 'y',
  к: 'k',
  л: 'l',
  м: 'm',
  н: 'n',
  о: 'o',
  п: 'p',
  р: 'r',
  с: 's',
  т: 't',
  у: 'u',
  ф: 'f',
  х: 'x',
  ц: 'ts',
  ч: 'ch',
  ш: 'sh',
  щ: 'sh',
  ъ: '',
  ы: 'y',
  ь: '',
  э: 'e',
  ю: 'yu',
  я: 'ya',
};
const AUTO_CODE_SOURCE_GROUPS = [
  ['resource', 'action'],
  ['title'],
  ['name'],
  ['label'],
  ['part_name'],
  ['first_name', 'last_name'],
  ['last_name', 'first_name'],
] as const;

const resourceUiConfigs: Record<string, ResourceUiConfig> = {
  'hr:employees': {
    formOrder: [
      'first_name',
      'last_name',
      'organization_key',
      'email',
      'phone',
      'password',
      'department_id',
      'position_id',
      'salary',
      'work_start_time',
      'work_end_time',
      'role_ids',
      'is_active',
    ],
    tableOrder: [
      'first_name',
      'last_name',
      'organization_key',
      'email',
      'department_id',
      'position_id',
    ],
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'hr:roles': {
    formOrder: ['name', 'slug', 'description', 'permission_ids', 'is_active'],
    tableOrder: ['name', 'slug', 'description', 'is_active'],
    hideOrganizationFieldWhenScoped: true,
  },
  'hr:permissions': {
    formOrder: ['code', 'resource', 'action', 'description', 'is_active'],
    tableOrder: ['code', 'resource', 'action', 'is_active'],
    hideOrganizationFieldWhenScoped: true,
  },
  'core:currencies': {
    formOrder: ['code', 'name', 'symbol', 'description', 'sort_order', 'is_default', 'is_active'],
    tableOrder: ['code', 'name', 'symbol', 'is_default', 'is_active'],
    hideOrganizationFieldWhenScoped: true,
  },
  'core:warehouses': {
    formOrder: ['department_id', 'name', 'code', 'is_default', 'is_active', 'description'],
    tableOrder: ['name', 'department_id', 'code', 'is_default', 'is_active'],
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'core:client-debts': {
    formOrder: [
      'client_id',
      'department_id',
      'item_type',
      'item_key',
      'quantity',
      'unit',
      'amount_total',
      'amount_paid',
      'currency',
      'issued_on',
      'due_on',
      'status',
      'note',
      'is_active',
    ],
    tableOrder: [
      'issued_on',
      'due_on',
      'client_id',
      'item_type',
      'item_key',
      'quantity',
      'unit',
      'amount_total',
      'amount_paid',
      'currency',
      'status',
    ],
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'finance:expense-categories': {
    formOrder: ['name', 'code', 'description', 'is_active'],
    tableOrder: ['name', 'code', 'department_id', 'is_active'],
    hiddenFields: ['is_global'],
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'finance:expenses': {
    formOrder: [
      'category_id',
      'title',
      'item',
      'quantity',
      'unit',
      'unit_price',
      'amount',
      'currency',
      'expense_date',
      'note',
      'is_active',
    ],
    tableOrder: [
      'expense_date',
      'category_id',
      'title',
      'amount',
      'currency',
      'department_id',
      'is_active',
    ],
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'finance:cash-accounts': {
    formOrder: [
      'name',
      'code',
      'currency',
      'opening_balance',
      'note',
      'is_active',
    ],
    tableOrder: ['name', 'code', 'currency', 'opening_balance', 'department_id', 'is_active'],
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'finance:cash-transactions': {
    formOrder: [
      'title',
      'transaction_type',
      'cash_account_id',
      'expense_category_id',
      'counterparty_client_id',
      'amount',
      'currency',
      'transaction_date',
      'reference_no',
      'note',
    ],
    tableOrder: [
      'transaction_date',
      'transaction_type',
      'title',
      'cash_account_id',
      'department_id',
      'expense_category_id',
      'amount',
      'currency',
      'reference_no',
    ],
    hiddenFields: ['expense_id'],
    hideOrganizationFieldWhenScoped: true,
  },
  'slaughter:arrivals': {
    formOrder: [
      'arrived_on',
      'supplier_client_id',
      'poultry_type_id',
      'birds_count',
      'average_weight_kg',
      'unit_price',
      'currency',
      'invoice_no',
      'note',
    ],
    tableOrder: [
      'arrived_on',
      'supplier_client_id',
      'birds_count',
      'average_weight_kg',
      'invoice_no',
    ],
    hiddenFields: ['is_active'],
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'slaughter:processings': {
    formOrder: [
      'processed_on',
      'arrival_id',
      'processed_by',
      'birds_processed',
      'first_sort_count',
      'second_sort_count',
      'bad_count',
      'first_sort_weight_kg',
      'second_sort_weight_kg',
      'bad_weight_kg',
      'note',
    ],
    tableOrder: [
      'processed_on',
      'birds_processed',
      'first_sort_count',
      'second_sort_count',
      'bad_count',
    ],
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'slaughter:semi-products': {
    formOrder: [
      'produced_on',
      'processing_id',
      'part_name',
      'quality',
      'quantity',
      'unit',
      'code',
      'note',
    ],
    tableOrder: ['produced_on', 'part_name', 'quality', 'quantity', 'unit'],
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'slaughter:semi-product-shipments': {
    formOrder: [
      'shipped_on',
      'semi_product_id',
      'client_id',
      'quantity',
      'unit',
      'unit_price',
      'currency',
      'invoice_no',
      'created_by',
      'note',
    ],
    tableOrder: ['shipped_on', 'semi_product_id', 'client_id', 'quantity', 'invoice_no'],
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'inventory:movements': {
    formOrder: [
      'department_id',
      'warehouse_id',
      'occurred_on',
      'movement_kind',
      'item_type',
      'item_key',
      'quantity',
      'unit',
      'counterparty_warehouse_id',
      'note',
    ],
    tableOrder: [
      'occurred_on',
      'movement_kind',
      'warehouse_id',
      'item_type',
      'item_key',
      'quantity',
      'unit',
      'counterparty_warehouse_id',
      'note',
    ],
    hiddenFields: ['counterparty_department_id', 'reference_table', 'reference_id'],
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'medicine:batches': {
    formOrder: [
      'arrived_on',
      'expiry_date',
      'medicine_type_id',
      'arrival_id',
      'supplier_client_id',
      'batch_code',
      'barcode',
      'received_quantity',
      'remaining_quantity',
      'unit',
      'unit_cost',
      'currency',
      'note',
    ],
    tableOrder: [
      'arrived_on',
      'medicine_type_id',
      'batch_code',
      'barcode',
      'remaining_quantity',
      'unit',
      'expiry_date',
      'supplier_client_id',
    ],
    hiddenFields: [
      'qr_public_token',
      'qr_token_expires_at',
      'qr_generated_at',
      'qr_image_key',
      'qr_image_content_type',
      'qr_image_size_bytes',
      'attachment_key',
      'attachment_name',
      'attachment_content_type',
      'attachment_size_bytes',
    ],
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
};

export const inputBaseClassName =
  'flex h-11 w-full rounded-2xl border border-border/75 bg-card px-4 py-3 text-sm text-foreground shadow-[0_16px_38px_-30px_rgba(15,23,42,0.12)] ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50';
export const heroCardClassName =
  'relative overflow-hidden rounded-[30px] border border-border/70 bg-card shadow-[0_28px_88px_-56px_rgba(15,23,42,0.16)]';
export const frostedPanelClassName =
  'rounded-[24px] border border-border/70 bg-card shadow-[0_20px_56px_-40px_rgba(15,23,42,0.14)]';
export const compactPillClassName =
  'rounded-full border border-border/75 bg-card px-3 py-1.5 text-xs font-medium text-muted-foreground shadow-[0_16px_36px_-30px_rgba(15,23,42,0.1)]';

type FieldInputKind =
  | 'text'
  | 'password'
  | 'email'
  | 'tel'
  | 'integer'
  | 'number'
  | 'boolean'
  | 'date'
  | 'datetime'
  | 'json';

const DATE_FIELD_NAMES = new Set([
  'arrived_on',
  'consumed_on',
  'created_at',
  'deleted_at',
  'end_date',
  'expense_date',
  'expected_hatch_on',
  'expiry_date',
  'finished_on',
  'month_start',
  'processed_on',
  'produced_on',
  'received_on',
  'shipped_on',
  'start_date',
  'started_on',
  'transaction_date',
  'updated_at',
]);
const DATE_FIELD_SUFFIXES = ['_date', '_on', '_start', '_end', '_at'] as const;

export const FORBIDDEN_PAYLOAD_FIELDS = new Set(['id', 'created_at', 'updated_at', 'deleted_at']);
export type ModuleCrudAction =
  | 'create_record'
  | 'update_record'
  | 'delete_record'
  | 'stock_transfer'
  | 'client_notification';
export type ModuleCrudActionAccess = {
  canCreateActiveResource: boolean;
  canEditRecordEntries: boolean;
  canDeleteActiveResource: boolean;
  canSendClientNotifications: boolean;
};

export const canExecuteModuleCrudAction = (
  action: ModuleCrudAction,
  access: ModuleCrudActionAccess,
): boolean => {
  switch (action) {
    case 'create_record':
      return access.canCreateActiveResource;
    case 'update_record':
      return access.canEditRecordEntries;
    case 'delete_record':
      return access.canDeleteActiveResource;
    case 'stock_transfer':
      return access.canCreateActiveResource;
    case 'client_notification':
      return access.canSendClientNotifications;
    default:
      return false;
  }
};

export const isMultiReferenceField = (field: CrudFieldMeta): boolean =>
  Boolean(field.reference?.multiple);

const sanitizePayload = (payload: CrudRecord, idColumn: string): CrudRecord => {
  const cleaned: CrudRecord = {};
  for (const [key, value] of Object.entries(payload)) {
    if (key === idColumn || FORBIDDEN_PAYLOAD_FIELDS.has(key)) {
      continue;
    }
    if (value === undefined) {
      continue;
    }
    cleaned[key] = value;
  }

  return cleaned;
};

export const getFieldInputKind = (field: CrudFieldMeta): FieldInputKind => {
  const fieldName = field.name.toLowerCase();
  const databaseType = (field.database_type || '').toLowerCase();

  if (isPasswordFieldName(fieldName)) {
    return 'password';
  }
  if (fieldName === 'email') {
    return 'email';
  }
  if (fieldName === 'phone') {
    return 'tel';
  }
  if (
    field.type === 'date' ||
    databaseType === 'date' ||
    DATE_FIELD_NAMES.has(fieldName) ||
    DATE_FIELD_SUFFIXES.some((suffix) => fieldName.endsWith(suffix))
  ) {
    return 'date';
  }
  if (field.type === 'datetime' || databaseType.includes('timestamp')) {
    return 'datetime';
  }
  if (field.type === 'boolean' || databaseType === 'boolean' || databaseType === 'bool') {
    return 'boolean';
  }
  if (
    field.type === 'integer' ||
    databaseType === 'smallint' ||
    databaseType === 'integer' ||
    databaseType === 'bigint'
  ) {
    return 'integer';
  }
  if (
    field.type === 'number' ||
    databaseType === 'numeric' ||
    databaseType === 'decimal' ||
    databaseType === 'real' ||
    databaseType === 'double precision'
  ) {
    return 'number';
  }
  if (
    field.type === 'json' ||
    databaseType === 'json' ||
    databaseType === 'jsonb' ||
    databaseType.startsWith('_')
  ) {
    return 'json';
  }
  return 'text';
};

export const humanizeKey = (value: string): string =>
  value
    .split(/[-_]/g)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');

const getStringFormValue = (value: string | boolean | string[] | undefined): string => {
  if (typeof value === 'string') {
    return value.trim();
  }
  if (Array.isArray(value)) {
    return value
      .map((item) => item.trim())
      .filter((item) => item.length > 0)
      .join(' ')
      .trim();
  }
  return '';
};

const transliterateToLatin = (value: string): string =>
  value
    .split('')
    .map((character) => {
      const lowerCharacter = character.toLowerCase();
      if (!(lowerCharacter in CYRILLIC_TO_LATIN_MAP)) {
        return character;
      }
      const mappedCharacter = CYRILLIC_TO_LATIN_MAP[lowerCharacter] ?? '';
      return character === lowerCharacter ? mappedCharacter : mappedCharacter.toUpperCase();
    })
    .join('');

const normalizeCodeSourceValue = (value: string): string =>
  transliterateToLatin(value)
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[ʻʼ’'`]+/g, '')
    .replace(/&/g, ' and ')
    .trim();

const buildDelimitedCode = (
  values: string[],
  options: { delimiter: '-' | '.'; casing: 'upper' | 'lower' },
): string => {
  const tokens = values
    .map((value) => normalizeCodeSourceValue(value))
    .join(options.delimiter === '.' ? ' ' : ' ')
    .replace(/[^A-Za-z0-9]+/g, ' ')
    .trim()
    .split(/\s+/)
    .filter((token) => token.length > 0);

  if (tokens.length === 0) {
    return EMPTY_TEXT;
  }

  const joined = tokens.join(options.delimiter);
  return options.casing === 'upper' ? joined.toUpperCase() : joined.toLowerCase();
};

export const buildAutoGeneratedCodeValue = (
  fields: CrudFieldMeta[],
  values: FormValues,
  targetFieldName: string,
): string => {
  if (!isCodeFieldName(targetFieldName)) {
    return EMPTY_TEXT;
  }

  const availableFieldNames = new Set(fields.map((field) => field.name));
  const normalizedTargetFieldName = targetFieldName.trim().toLowerCase();
  const resourceActionSourceGroup = AUTO_CODE_SOURCE_GROUPS[0];

  for (const fieldGroup of AUTO_CODE_SOURCE_GROUPS) {
    if (!fieldGroup.every((fieldName) => availableFieldNames.has(fieldName))) {
      continue;
    }

    const parts = fieldGroup
      .map((fieldName) => getStringFormValue(values[fieldName]))
      .filter((value) => value.length > 0);

    if (parts.length !== fieldGroup.length) {
      continue;
    }

    if (fieldGroup === resourceActionSourceGroup) {
      return buildDelimitedCode(parts, { delimiter: '.', casing: 'lower' });
    }

    if (normalizedTargetFieldName === 'client_code') {
      return buildDelimitedCode(parts, { delimiter: '-', casing: 'upper' });
    }

    return buildDelimitedCode(parts, { delimiter: '-', casing: 'upper' });
  }

  const fallbackSourceFields = fields
    .filter(
      (field) =>
        field.name !== targetFieldName &&
        !isCodeFieldName(field.name) &&
        !isPasswordFieldName(field.name) &&
        /(title|name|label)/i.test(field.name),
    )
    .map((field) => getStringFormValue(values[field.name]))
    .filter((value) => value.length > 0);

  if (fallbackSourceFields.length > 0) {
    return buildDelimitedCode([fallbackSourceFields[0]], { delimiter: '-', casing: 'upper' });
  }

  return EMPTY_TEXT;
};

export const applyAutoGeneratedCodeFields = (
  fields: CrudFieldMeta[],
  previousValues: FormValues,
  nextValues: FormValues,
  changedFieldName?: string,
): FormValues => {
  const resolvedValues = cloneFormValues(nextValues);

  for (const field of fields) {
    if (field.readonly || !isCodeFieldName(field.name) || changedFieldName === field.name) {
      continue;
    }

    const currentFieldValue = getStringFormValue(previousValues[field.name]);
    const nextFieldValue = getStringFormValue(resolvedValues[field.name]);
    const currentGeneratedValue = buildAutoGeneratedCodeValue(fields, previousValues, field.name);
    const nextGeneratedValue = buildAutoGeneratedCodeValue(fields, resolvedValues, field.name);

    if (!nextGeneratedValue) {
      continue;
    }

    const shouldReplaceValue =
      nextFieldValue.length === 0 ||
      currentFieldValue.length === 0 ||
      currentFieldValue === currentGeneratedValue;

    if (shouldReplaceValue) {
      resolvedValues[field.name] = nextGeneratedValue;
    }
  }

  return resolvedValues;
};

export const getResourceUiConfig = (
  moduleKey: string,
  resourceKey: string,
): ResourceUiConfig | undefined => resourceUiConfigs[`${moduleKey}:${resourceKey}`];

export const resolveResourceCategoryGroupId = (
  resource: ResourceCategoryCandidate,
): ResourceCategoryGroupId => {
  if (FINANCE_RESOURCE_PERMISSION_PREFIXES.has(resource.permissionPrefix)) {
    return 'finance';
  }
  if (
    PEOPLE_RESOURCE_PERMISSION_PREFIXES.has(resource.permissionPrefix) ||
    PEOPLE_RESOURCE_KEYS.has(resource.key)
  ) {
    return 'people_clients';
  }
  return 'operations';
};

export const shouldExposeResourceInModule = (
  moduleKey: string,
  resource: { key: string; apiModuleKey?: string },
): boolean => Boolean(moduleKey.trim() || resource.key.trim());

export const sortFieldsByPreferredOrder = (
  fields: CrudFieldMeta[],
  preferredOrder?: string[],
): CrudFieldMeta[] => {
  if (!preferredOrder || preferredOrder.length === 0) {
    return fields;
  }

  const priority = new Map(preferredOrder.map((fieldName, index) => [fieldName, index]));

  return [...fields].sort((left, right) => {
    const leftPriority = priority.get(left.name);
    const rightPriority = priority.get(right.name);
    if (leftPriority === undefined && rightPriority === undefined) {
      return 0;
    }
    if (leftPriority === undefined) {
      return 1;
    }
    if (rightPriority === undefined) {
      return -1;
    }
    return leftPriority - rightPriority;
  });
};

export const getDepartmentLabel = (department: DepartmentRecord): string => {
  if (typeof department.name === 'string' && department.name) {
    return department.name;
  }
  if (typeof department.code === 'string' && department.code) {
    return department.code;
  }
  if (typeof department.id === 'string' && department.id) {
    return department.id;
  }
  return EMPTY_TEXT;
};

export const getReferenceOptionLabel = (
  field: CrudFieldMeta,
  optionValue: string,
  optionLabel: string,
  translate: (key: string, params?: Record<string, string | number>, fallback?: string) => string,
): string => {
  const readableLabel = getReadableReferenceLabel({
    fieldName: field.name,
    fieldLabel: field.label,
    optionValue,
    optionLabel,
  });

  if (field.name === 'module_key') {
    return readableLabel || translate(`modules.${optionValue}.label`, undefined, optionValue);
  }
  if (field.name === 'transaction_type') {
    return translate(
      `cashTransactionTypes.${optionValue}`,
      undefined,
      readableLabel || optionValue,
    );
  }
  if (field.name === 'item_type') {
    return translate(
      `inventory.itemTypes.${optionValue}`,
      undefined,
      readableLabel || humanizeKey(optionValue),
    );
  }
  if (field.name === 'movement_kind') {
    return translate(
      `inventory.movementKinds.${optionValue}`,
      undefined,
      readableLabel || humanizeKey(optionValue),
    );
  }
  if (field.name === 'unit') {
    return translate(
      `inventory.units.${optionValue}`,
      undefined,
      readableLabel || optionValue,
    );
  }
  return readableLabel;
};

export const buildDepartmentScope = (
  selectedDepartmentId: string,
  childrenMap: Map<string, string[]>,
): Set<string> => {
  if (!selectedDepartmentId) {
    return new Set();
  }

  const scope = new Set<string>();
  const stack = [selectedDepartmentId];
  while (stack.length > 0) {
    const currentDepartmentId = stack.pop();
    if (!currentDepartmentId || scope.has(currentDepartmentId)) {
      continue;
    }
    scope.add(currentDepartmentId);
    for (const childId of childrenMap.get(currentDepartmentId) ?? []) {
      stack.push(childId);
    }
  }
  return scope;
};

export const getRecordId = (record: CrudRecord | null | undefined, idColumn: string): string => {
  const candidate = record?.[idColumn];
  if (typeof candidate === 'string' || typeof candidate === 'number') {
    return String(candidate);
  }
  return '';
};

export const getInputType = (field: CrudFieldMeta): string => {
  const fieldInputKind = getFieldInputKind(field);
  switch (fieldInputKind) {
    case 'password':
      return 'password';
    case 'email':
      return 'email';
    case 'tel':
      return 'tel';
    case 'integer':
    case 'number':
      return 'number';
    case 'date':
      return 'date';
    case 'datetime':
      return 'datetime-local';
    default:
      return 'text';
  }
};

export const formatDateValue = (value: unknown): string => {
  if (typeof value !== 'string') {
    return EMPTY_TEXT;
  }
  return value.slice(0, 10);
};

const formatDateTimeValue = (value: unknown): string => {
  if (typeof value !== 'string') {
    return EMPTY_TEXT;
  }
  const normalized = value.replace(/Z$/, '');
  return normalized.length >= 16 ? normalized.slice(0, 16) : normalized;
};

export const formatDateTimeDisplayValue = (value: unknown): string => {
  const normalized = formatDateTimeValue(value);
  return normalized ? normalized.replace('T', ' ') : EMPTY_TEXT;
};

export const getInputProps = (field: CrudFieldMeta) => {
  const fieldInputKind = getFieldInputKind(field);
  switch (fieldInputKind) {
    case 'integer':
      return { inputMode: 'numeric' as const, step: '1' };
    case 'number':
      return { inputMode: 'decimal' as const, step: 'any' };
    case 'email':
      return { inputMode: 'email' as const, autoComplete: 'email' };
    case 'tel':
      return { inputMode: 'tel' as const, autoComplete: 'tel' };
    case 'password':
      return { autoComplete: 'new-password' };
    case 'date':
    case 'datetime':
      return { autoComplete: 'off' };
    default:
      return {};
  }
};

const normalizeReferenceCandidateValue = (
  value: unknown,
  options: { allowNonUuidFallback?: boolean } = {},
): string => {
  if (typeof value === 'string') {
    return value.trim();
  }
  if (typeof value === 'number' || typeof value === 'bigint') {
    return String(value).trim();
  }
  if (Array.isArray(value)) {
    return '';
  }
  if (value && typeof value === 'object') {
    const recordValue = value as {
      id?: unknown;
      value?: unknown;
      uuid?: unknown;
      code?: unknown;
      slug?: unknown;
    };

    if (typeof recordValue.id === 'string' && recordValue.id.trim()) {
      return recordValue.id.trim();
    }
    if (typeof recordValue.value === 'string' && recordValue.value.trim()) {
      const resolved = recordValue.value.trim();
      if (options.allowNonUuidFallback || isValidUuid(resolved)) {
        return resolved;
      }
      return '';
    }
    if (typeof recordValue.uuid === 'string' && recordValue.uuid.trim()) {
      return recordValue.uuid.trim();
    }
    if (
      options.allowNonUuidFallback &&
      typeof recordValue.code === 'string' &&
      recordValue.code.trim()
    ) {
      return recordValue.code.trim();
    }
    if (
      options.allowNonUuidFallback &&
      typeof recordValue.slug === 'string' &&
      recordValue.slug.trim()
    ) {
      return recordValue.slug.trim();
    }
  }
  return '';
};

const resolveReferenceOptionValue = (
  rawValue: string,
  reference: CrudFieldReference | null,
): string | null => {
  if (!reference?.options?.length) {
    return null;
  }
  const exactOption = reference.options.find((option) => option.value === rawValue);
  if (exactOption) {
    return exactOption.value;
  }
  const normalizedSearch = rawValue.trim().toLowerCase();
  if (!normalizedSearch) {
    return null;
  }
  const labelOption = reference.options.find(
    (option) => option.label.trim().toLowerCase() === normalizedSearch,
  );
  return labelOption ? labelOption.value : null;
};

export const buildFormValues = (fields: CrudFieldMeta[], record: CrudRecord | null): FormValues => {
  const values: FormValues = {};
  for (const field of fields) {
    const currentValue = record?.[field.name];
    const fieldInputKind = getFieldInputKind(field);

    if (isMultiReferenceField(field)) {
      if (Array.isArray(currentValue)) {
        values[field.name] = currentValue
          .map((item) =>
            normalizeReferenceCandidateValue(item, { allowNonUuidFallback: field.type !== 'uuid' }),
          )
          .filter((item) => item.length > 0);
        continue;
      }
      if (currentValue === null || currentValue === undefined || currentValue === '') {
        values[field.name] = [];
        continue;
      }
      values[field.name] = [
        normalizeReferenceCandidateValue(currentValue, {
          allowNonUuidFallback: field.type !== 'uuid',
        }),
      ];
      continue;
    }

    if (fieldInputKind === 'boolean') {
      values[field.name] = Boolean(currentValue);
      continue;
    }
    if (fieldInputKind === 'password') {
      values[field.name] = EMPTY_TEXT;
      continue;
    }
    if (currentValue === null || currentValue === undefined) {
      values[field.name] = EMPTY_TEXT;
      continue;
    }
    if (fieldInputKind === 'date') {
      values[field.name] = formatDateValue(currentValue);
      continue;
    }
    if (fieldInputKind === 'datetime') {
      values[field.name] = formatDateTimeValue(currentValue);
      continue;
    }
    if (fieldInputKind === 'json') {
      values[field.name] =
        typeof currentValue === 'string' ? currentValue : JSON.stringify(currentValue, null, 2);
      continue;
    }
    if (field.reference) {
      values[field.name] = normalizeReferenceCandidateValue(currentValue, {
        allowNonUuidFallback: field.type !== 'uuid',
      });
      continue;
    }
    values[field.name] = String(currentValue);
  }

  return values;
};

export const cloneFormValues = (values: FormValues): FormValues => {
  const nextValues: FormValues = {};
  for (const [fieldName, fieldValue] of Object.entries(values)) {
    nextValues[fieldName] = Array.isArray(fieldValue) ? [...fieldValue] : fieldValue;
  }
  return nextValues;
};

const normalizeFormValueForComparison = (
  value: string | boolean | string[] | undefined,
): string => {
  if (Array.isArray(value)) {
    return JSON.stringify(value);
  }
  if (typeof value === 'boolean') {
    return value ? '1' : '0';
  }
  if (typeof value === 'string') {
    return value;
  }
  return '';
};

export const areFormValuesEqual = (left: FormValues, right: FormValues): boolean => {
  const allFieldNames = new Set([...Object.keys(left), ...Object.keys(right)]);
  for (const fieldName of allFieldNames) {
    if (
      normalizeFormValueForComparison(left[fieldName]) !==
      normalizeFormValueForComparison(right[fieldName])
    ) {
      return false;
    }
  }
  return true;
};

export const getDisplayValue = (
  field: CrudFieldMeta,
  value: unknown,
  yesLabel: string,
  noLabel: string,
  emptyLabel: string,
  translateReferenceLabel?: (
    field: CrudFieldMeta,
    optionValue: string,
    optionLabel: string,
  ) => string,
): string => {
  const fieldInputKind = getFieldInputKind(field);

  if (value === null || value === undefined || value === '') {
    return emptyLabel;
  }
  if (fieldInputKind === 'password') {
    return MASKED_PASSWORD_VALUE;
  }
  if (isMultiReferenceField(field) && Array.isArray(value)) {
    const labels = value
      .map((item) => normalizeReferenceCandidateValue(item))
      .filter((item) => item.length > 0)
      .map((item) => {
        const matchedOption = field.reference?.options.find((option) => option.value === item);
        if (!matchedOption) {
          return item;
        }
        return translateReferenceLabel
          ? translateReferenceLabel(field, matchedOption.value, matchedOption.label)
          : matchedOption.label;
      });
    return labels.length > 0 ? labels.join(', ') : emptyLabel;
  }

  if (field.reference?.options.length) {
    const matchedOption = field.reference.options.find((option) => option.value === String(value));
    if (matchedOption) {
      return translateReferenceLabel
        ? translateReferenceLabel(field, matchedOption.value, matchedOption.label)
        : matchedOption.label;
    }
  }

  if (field.reference) {
    const fallbackValue = String(value);
    return getReadableReferenceLabel({
      fieldName: field.name,
      fieldLabel: field.label,
      optionValue: fallbackValue,
      optionLabel: fallbackValue,
    });
  }

  if (fieldInputKind === 'boolean') {
    return value ? yesLabel : noLabel;
  }
  if (fieldInputKind === 'date') {
    return formatDateValue(value);
  }
  if (fieldInputKind === 'datetime') {
    return formatDateTimeDisplayValue(value);
  }
  if (fieldInputKind === 'json') {
    return typeof value === 'string' ? value : JSON.stringify(value);
  }

  return String(value);
};

export const getTableFields = (fields: CrudFieldMeta[], idColumn: string): CrudFieldMeta[] => {
  const preferredFields = fields.filter(
    (field) =>
      field.name !== idColumn &&
      !isPasswordFieldName(field.name) &&
      !(field.type === 'uuid' && !field.reference) &&
      field.type !== 'json' &&
      field.name !== 'created_at' &&
      field.name !== 'updated_at' &&
      field.name !== 'deleted_at',
  );
  if (preferredFields.length > 0) {
    return preferredFields.slice(0, 6);
  }
  return fields
    .filter(
      (field) =>
        !isPasswordFieldName(field.name) &&
        field.type !== 'json' &&
        field.name !== 'created_at' &&
        field.name !== 'updated_at' &&
        field.name !== 'deleted_at',
    )
    .slice(0, 6);
};

export const isAuditSnapshot = (value: unknown): value is AuditSnapshot => {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
};

export const isStructuredAuditValue = (value: unknown): boolean => {
  if (Array.isArray(value)) {
    return value.some((item) => typeof item === 'object' && item !== null);
  }
  return typeof value === 'object' && value !== null;
};

const parseFieldValue = (
  field: CrudFieldMeta,
  rawValue: unknown,
  mode: SubmitMode,
  requiredMessage: string,
  integerMessage: string,
  numberMessage: string,
  invalidJsonMessage: string,
  invalidUuidMessage: string,
): { ok: true; value?: unknown } | { ok: false; message: string } => {
  const fieldInputKind = getFieldInputKind(field);

  if (field.readonly || field.name === 'id') {
    return { ok: true };
  }

  if (isMultiReferenceField(field)) {
    const values = (
      Array.isArray(rawValue) ? rawValue : typeof rawValue === 'string' ? [rawValue] : []
    )
      .map((item) =>
        normalizeReferenceCandidateValue(item, { allowNonUuidFallback: field.type !== 'uuid' }),
      )
      .filter((item) => item.length > 0)
      .map((item) => resolveReferenceOptionValue(item, field.reference) ?? item)
      .filter((item) => item.length > 0);

    if (
      field.type === 'uuid' &&
      values.some(
        (item) =>
          !isValidUuid(item) && !field.reference?.options?.some((option) => option.value === item),
      )
    ) {
      return { ok: false, message: invalidUuidMessage };
    }
    if (values.length === 0 && field.required) {
      return { ok: false, message: requiredMessage };
    }

    return { ok: true, value: Array.from(new Set(values)) };
  }

  if (fieldInputKind === 'boolean') {
    return { ok: true, value: Boolean(rawValue) };
  }

  const value = normalizeReferenceCandidateValue(rawValue, {
    allowNonUuidFallback: field.type !== 'uuid',
  });
  const isPasswordField = field.name.toLowerCase().includes('password');

  if (value === EMPTY_TEXT) {
    if (isPasswordField && mode === 'update') {
      return { ok: true };
    }
    if (field.nullable) {
      return { ok: true, value: null };
    }
    if (field.required) {
      return { ok: false, message: requiredMessage };
    }
    return { ok: true };
  }

  if (fieldInputKind === 'integer') {
    const parsed = Number(value);
    if (!Number.isInteger(parsed)) {
      return { ok: false, message: integerMessage };
    }
    return { ok: true, value: parsed };
  }
  if (fieldInputKind === 'number') {
    const parsed = Number(value);
    if (Number.isNaN(parsed)) {
      return { ok: false, message: numberMessage };
    }
    return { ok: true, value: parsed };
  }
  if (fieldInputKind === 'json') {
    try {
      return { ok: true, value: JSON.parse(value) };
    } catch {
      return { ok: false, message: invalidJsonMessage };
    }
  }
  if (field.type === 'uuid') {
    const resolvedReferenceValue = resolveReferenceOptionValue(value, field.reference);
    if (resolvedReferenceValue !== null) {
      return { ok: true, value: resolvedReferenceValue };
    }
    if (!isValidUuid(value)) {
      return { ok: false, message: invalidUuidMessage };
    }
    return { ok: true, value };
  }
  return { ok: true, value };
};

export const buildPayload = (
  fields: CrudFieldMeta[],
  values: FormValues,
  mode: SubmitMode,
  requiredMessage: string,
  integerMessage: string,
  numberMessage: string,
  invalidJsonMessage: string,
  invalidUuidMessage: string,
  idColumn: string,
): { payload: CrudRecord; errors: FormErrors } => {
  const preparedValues = applyAutoGeneratedCodeFields(fields, values, values);
  const payload: CrudRecord = {};
  const errors: FormErrors = {};

  for (const field of fields) {
    if (field.name === idColumn || field.name === 'id') {
      continue;
    }

    const parsed = parseFieldValue(
      field,
      preparedValues[field.name],
      mode,
      requiredMessage,
      integerMessage,
      numberMessage,
      invalidJsonMessage,
      invalidUuidMessage,
    );

    if (!parsed.ok) {
      errors[field.name] = parsed.message;
      continue;
    }

    if ('value' in parsed) {
      payload[field.name] = parsed.value;
    }
  }

  return { payload: sanitizePayload(payload, idColumn), errors };
};
