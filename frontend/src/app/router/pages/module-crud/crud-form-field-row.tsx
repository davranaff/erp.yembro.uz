import { CustomSelect } from '@/components/ui/custom-select';
import { HierarchicalCategorySelect } from '@/components/ui/hierarchical-category-select';
import { Input } from '@/components/ui/input';
import { MeasurementUnitSelect } from '@/components/ui/measurement-unit-select';
import { SearchableReferenceSelect } from '@/components/ui/searchable-reference-select';
import type {
  CrudFieldMeta,
  CrudFieldReference,
  CrudReferenceOption,
} from '@/shared/api/backend-crud';
import type { Language } from '@/shared/i18n/types';
import { cn } from '@/shared/lib/cn';

import {
  EMPTY_TEXT,
  frostedPanelClassName,
  getFieldInputKind,
  getInputProps,
  getInputType,
  humanizeKey,
  inputBaseClassName,
  isMultiReferenceField,
  resolveLocalizedText,
  type EnumOption,
  type FormValues,
  type LocalizedText,
} from '../module-crud-page.helpers';

type TranslateFn = (
  key: string,
  params?: Record<string, string | number>,
  fallback?: string,
) => string;

type ReferenceLabelTranslator = (
  field: CrudFieldMeta,
  optionValue: string,
  optionLabel: string,
) => string;

export interface DepartmentNodeEntry {
  depth: number;
  label: string;
}

export interface InventoryMovementItemKeyField {
  reference: (CrudFieldReference & { options?: CrudReferenceOption[] }) | null;
}

export interface CrudFormFieldRowContext {
  t: TranslateFn;
  translateReferenceLabel: ReferenceLabelTranslator;
  yesLabel: string;
  noLabel: string;
  isFormReadOnly: boolean;
  pendingAction: boolean;
  supportsDepartmentFilter: boolean;
  isInventoryMovementsResource: boolean;
  isClientDebtsResource: boolean;
  isTransferMovementForm: boolean;
  formValues: FormValues;
  selectedDepartmentId: string;
  fallbackDepartmentId: string;
  movementDepartmentId: string;
  departmentNodeMap: Map<string, DepartmentNodeEntry>;
  departmentReferenceOptions: CrudReferenceOption[];
  movementWarehouseReferenceOptions: CrudReferenceOption[];
  movementCounterpartyWarehouseReferenceOptions: CrudReferenceOption[];
  inventoryMovementItemKeyField: InventoryMovementItemKeyField;
  resourceModuleKey: string;
  resourcePath: string;
  fieldHelpers?: Record<string, string | LocalizedText>;
  fieldEnums?: Record<string, EnumOption[]>;
  language: Language;
  onInputChange: (field: CrudFieldMeta, value: string | boolean | string[]) => void;
}

export interface CrudFormFieldRowProps {
  field: CrudFieldMeta;
  value: unknown;
  fieldError?: string;
  context: CrudFormFieldRowContext;
}

export function CrudFormFieldRow({ field, value, fieldError, context }: CrudFormFieldRowProps) {
  const {
    t,
    translateReferenceLabel,
    yesLabel,
    noLabel,
    isFormReadOnly,
    pendingAction,
    supportsDepartmentFilter,
    isInventoryMovementsResource,
    isClientDebtsResource,
    isTransferMovementForm,
    formValues,
    selectedDepartmentId,
    fallbackDepartmentId,
    movementDepartmentId,
    departmentNodeMap,
    departmentReferenceOptions,
    movementWarehouseReferenceOptions,
    movementCounterpartyWarehouseReferenceOptions,
    inventoryMovementItemKeyField,
    resourceModuleKey,
    resourcePath,
    fieldHelpers,
    fieldEnums,
    language,
    onInputChange,
  } = context;
  const rawFieldHelper = fieldHelpers?.[field.name];
  const fieldHelperText = rawFieldHelper
    ? resolveLocalizedText(rawFieldHelper, language)
    : undefined;
  const enumOptionsForField = fieldEnums?.[field.name];
  const resolvedEnumOptions = enumOptionsForField?.map((option) => ({
    value: option.value,
    label: resolveLocalizedText(option.label, language),
  }));

  const fieldInputKind = getFieldInputKind(field);
  const isDepartmentReferenceField = supportsDepartmentFilter && field.name === 'department_id';
  const isMovementWarehouseField =
    isInventoryMovementsResource &&
    (field.name === 'warehouse_id' || field.name === 'counterparty_warehouse_id');
  const isMovementItemKeyField = isInventoryMovementsResource && field.name === 'item_key';
  const isClientDebtItemKeyField = isClientDebtsResource && field.name === 'item_key';
  const isFinanceDepartmentScopedReferenceField =
    field.name === 'category_id' ||
    field.name === 'expense_category_id' ||
    field.name === 'cash_account_id';
  const clientDebtDepartmentId =
    typeof formValues.department_id === 'string'
      ? formValues.department_id.trim()
      : selectedDepartmentId || fallbackDepartmentId || '';
  const financeDepartmentId =
    typeof formValues.department_id === 'string'
      ? formValues.department_id.trim()
      : selectedDepartmentId || fallbackDepartmentId || '';
  const currentDepartmentReferenceValue =
    isDepartmentReferenceField && typeof value === 'string' ? value.trim() : '';
  const currentDepartmentNode = currentDepartmentReferenceValue
    ? departmentNodeMap.get(currentDepartmentReferenceValue)
    : null;
  const currentDepartmentReferenceOption =
    currentDepartmentNode &&
    !departmentReferenceOptions.some((option) => option.value === currentDepartmentReferenceValue)
      ? {
          value: currentDepartmentReferenceValue,
          label: `${' '.repeat(currentDepartmentNode.depth * 2)}${currentDepartmentNode.label}`,
        }
      : null;
  const isMovementWarehouseScopeSelected =
    !isMovementWarehouseField ||
    (field.name === 'warehouse_id'
      ? movementDepartmentId.length > 0
      : typeof formValues.warehouse_id === 'string' && formValues.warehouse_id.trim().length > 0);
  const referenceOptions = isDepartmentReferenceField
    ? currentDepartmentReferenceOption
      ? [...departmentReferenceOptions, currentDepartmentReferenceOption]
      : departmentReferenceOptions
    : field.name === 'warehouse_id'
      ? movementWarehouseReferenceOptions
      : field.name === 'counterparty_warehouse_id'
        ? movementCounterpartyWarehouseReferenceOptions
        : field.name === 'item_key'
          ? inventoryMovementItemKeyField.reference?.options
          : field.reference?.options;
  const DEPARTMENT_META_FIELDS = new Set([
    'department_id',
    'parent_department_id',
    'head_id',
    'organization_id',
    'module_key',
    'id',
  ]);
  const formDepartmentId =
    typeof formValues.department_id === 'string' ? formValues.department_id.trim() : '';
  const defaultFormScopeDepartmentId =
    formDepartmentId || selectedDepartmentId || fallbackDepartmentId || '';
  const expenseItemCategoryId =
    typeof formValues.category_id === 'string' ? formValues.category_id.trim() : '';
  const isExpenseItemField =
    resourceModuleKey === 'finance' && resourcePath === 'expenses' && field.name === 'item';
  const referenceQueryParams =
    field.name === 'warehouse_id' && isInventoryMovementsResource
      ? { department_id: movementDepartmentId || undefined }
      : field.name === 'item_key'
        ? {
            department_id: isInventoryMovementsResource
              ? movementDepartmentId || undefined
              : isClientDebtsResource
                ? clientDebtDepartmentId || undefined
                : undefined,
            item_type:
              typeof formValues.item_type === 'string'
                ? formValues.item_type.trim() || undefined
                : undefined,
          }
        : isExpenseItemField
          ? {
              department_id: financeDepartmentId || undefined,
              category_id: expenseItemCategoryId || undefined,
            }
          : isFinanceDepartmentScopedReferenceField
            ? { department_id: financeDepartmentId || undefined }
            : field.reference &&
                !DEPARTMENT_META_FIELDS.has(field.name) &&
                defaultFormScopeDepartmentId
              ? { department_id: defaultFormScopeDepartmentId }
              : undefined;
  const hasReferenceOptions =
    isDepartmentReferenceField ||
    isMovementWarehouseField ||
    isMovementItemKeyField ||
    isClientDebtItemKeyField ||
    Boolean(field.reference);
  const isMultiReference = isMultiReferenceField(field);
  const useCompactReferenceSelect =
    hasReferenceOptions &&
    !isMultiReference &&
    !isMovementItemKeyField &&
    !isClientDebtItemKeyField &&
    (field.name === 'movement_kind' || field.name === 'item_type' || field.name === 'unit');
  const compactReferenceOptions = (referenceOptions ?? []).map((option) => ({
    value: option.value,
    label: translateReferenceLabel(field, option.value, option.label),
    searchText: option.label,
  }));
  const isWideField =
    fieldInputKind === 'json' || (isInventoryMovementsResource && field.name === 'note');
  const isItemTypeSelected =
    (!isMovementItemKeyField && !isClientDebtItemKeyField) ||
    (typeof formValues.item_type === 'string' && formValues.item_type.trim().length > 0);
  const isItemScopeSelected =
    !isMovementItemKeyField && !isClientDebtItemKeyField
      ? true
      : isInventoryMovementsResource
        ? movementDepartmentId.length > 0
        : clientDebtDepartmentId.length > 0;
  const fieldLabel =
    isInventoryMovementsResource && field.name === 'warehouse_id'
      ? isTransferMovementForm
        ? t('fields.from_warehouse_id', undefined, 'Откуда')
        : t('fields.warehouse_id', undefined, 'Склад')
      : isInventoryMovementsResource && field.name === 'counterparty_warehouse_id'
        ? t('fields.to_warehouse_id', undefined, 'Куда')
        : t(`fields.${field.name}`, undefined, field.label || humanizeKey(field.name));

  return (
    <div
      className={cn(`${frostedPanelClassName} space-y-3 p-4`, isWideField ? 'md:col-span-2' : '')}
      data-tour={
        isClientDebtsResource && field.name === 'item_key'
          ? 'client-debt-item-key-field'
          : isClientDebtsResource && field.name === 'due_on'
            ? 'client-debt-due-on-field'
            : undefined
      }
    >
      <label className="text-sm font-medium text-foreground" htmlFor={field.name}>
        {fieldLabel}
        {field.required ? <span className="ml-1 text-destructive">*</span> : null}
      </label>

      {fieldInputKind === 'boolean' ? (
        <label className="flex items-center gap-3 rounded-2xl border border-border/75 bg-card px-4 py-3 shadow-[0_16px_36px_-30px_rgba(15,23,42,0.1)]">
          <input
            id={field.name}
            type="checkbox"
            checked={Boolean(value)}
            disabled={isFormReadOnly || pendingAction}
            onChange={(event) => onInputChange(field, event.target.checked)}
            className="h-4 w-4 rounded border-border text-primary focus:ring-primary"
          />
          <span className="text-sm text-foreground">{`${yesLabel} / ${noLabel}`}</span>
        </label>
      ) : resolvedEnumOptions ? (
        <CustomSelect
          value={typeof value === 'string' ? value : EMPTY_TEXT}
          onChange={(nextValue) => onInputChange(field, nextValue)}
          options={resolvedEnumOptions}
          disabled={isFormReadOnly || pendingAction}
          className={inputBaseClassName}
          placeholder={t('common.chooseValue')}
          searchable={resolvedEnumOptions.length > 6}
        />
      ) : field.name === 'category_id' || field.name === 'expense_category_id' ? (
        <HierarchicalCategorySelect
          value={typeof value === 'string' ? value : EMPTY_TEXT}
          onChange={(nextValue) => onInputChange(field, nextValue)}
          disabled={isFormReadOnly || pendingAction}
          className={inputBaseClassName}
          placeholder={t('common.chooseValue')}
        />
      ) : field.name === 'unit' ? (
        <MeasurementUnitSelect
          value={typeof value === 'string' ? value : EMPTY_TEXT}
          onChange={(nextValue) => onInputChange(field, nextValue)}
          disabled={isFormReadOnly || pendingAction}
          className={inputBaseClassName}
          placeholder={t('common.chooseValue')}
        />
      ) : useCompactReferenceSelect ? (
        <CustomSelect
          value={typeof value === 'string' ? value : EMPTY_TEXT}
          onChange={(nextValue) => onInputChange(field, nextValue)}
          options={compactReferenceOptions}
          disabled={
            isFormReadOnly ||
            pendingAction ||
            !isItemTypeSelected ||
            !isItemScopeSelected ||
            !isMovementWarehouseScopeSelected
          }
          className={inputBaseClassName}
          placeholder={t('common.chooseValue')}
          searchPlaceholder={t('common.search', undefined, 'Поиск')}
          emptySearchLabel={t(
            'crud.referenceNoOptions',
            undefined,
            'Подходящие варианты не найдены.',
          )}
          searchable={
            isDepartmentReferenceField ||
            isMovementWarehouseField ||
            compactReferenceOptions.length > 6
          }
        />
      ) : hasReferenceOptions ? (
        <SearchableReferenceSelect
          moduleKey={resourceModuleKey}
          resourcePath={resourcePath}
          field={{
            ...field,
            reference:
              isDepartmentReferenceField || isMovementWarehouseField || isMovementItemKeyField
                ? {
                    ...((isMovementItemKeyField
                      ? inventoryMovementItemKeyField.reference
                      : field.reference) ?? {
                      table: isMovementWarehouseField
                        ? 'warehouses'
                        : isMovementItemKeyField
                          ? '__inventory_item_key__'
                          : 'departments',
                      column: isMovementItemKeyField ? 'value' : 'id',
                      label_column: isMovementItemKeyField ? 'label' : 'name',
                      options: [],
                    }),
                    options: referenceOptions ?? [],
                  }
                : field.reference,
          }}
          value={
            isMultiReference
              ? Array.isArray(value)
                ? value
                : []
              : typeof value === 'string'
                ? value
                : EMPTY_TEXT
          }
          onChange={(nextValue) => onInputChange(field, nextValue)}
          disabled={
            isFormReadOnly ||
            pendingAction ||
            !isItemTypeSelected ||
            !isItemScopeSelected ||
            !isMovementWarehouseScopeSelected
          }
          className={inputBaseClassName}
          placeholder={t('common.chooseValue')}
          searchPlaceholder={t('common.search', undefined, 'Поиск')}
          emptySearchLabel={t(
            'crud.referenceNoOptions',
            undefined,
            'Подходящие варианты не найдены.',
          )}
          translateOptionLabel={translateReferenceLabel}
          referenceQueryParams={referenceQueryParams}
        />
      ) : fieldInputKind === 'json' ? (
        <textarea
          id={field.name}
          value={typeof value === 'string' ? value : EMPTY_TEXT}
          disabled={isFormReadOnly || pendingAction}
          onChange={(event) => onInputChange(field, event.target.value)}
          spellCheck={false}
          className="min-h-[140px] w-full rounded-2xl border border-border/75 bg-card px-4 py-3 text-sm text-foreground shadow-[0_16px_38px_-30px_rgba(15,23,42,0.12)] ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        />
      ) : (
        <Input
          id={field.name}
          type={getInputType(field)}
          {...getInputProps(field)}
          value={typeof value === 'string' ? value : EMPTY_TEXT}
          disabled={isFormReadOnly || pendingAction}
          onChange={(event) => onInputChange(field, event.target.value)}
          className={inputBaseClassName}
        />
      )}

      {fieldError ? (
        <p className="text-xs text-destructive">{fieldError}</p>
      ) : fieldHelperText ? (
        <p className="text-xs text-muted-foreground">{fieldHelperText}</p>
      ) : null}
    </div>
  );
}
