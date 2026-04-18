import type { CrudRecord } from '@/shared/api/backend-crud';
import type { InventoryItemType, InventoryUnit } from '@/shared/api/inventory';

import { getRecordId } from '../module-crud-page.helpers';

export type WarehouseRecord = CrudRecord & {
  id?: string;
  name?: string;
  code?: string;
  department_id?: string;
  organization_id?: string;
  is_default?: boolean | string;
  is_active?: boolean | string;
};

export type InventoryCreateMode = 'incoming' | 'outgoing' | 'transfer';

export const TRANSFER_MOVEMENT_KINDS = new Set(['transfer_in', 'transfer_out']);

export const parseDecimalValue = (value: string): number => {
  const normalized = value.trim().replace(',', '.');
  const parsed = Number.parseFloat(normalized);
  return Number.isFinite(parsed) ? parsed : Number.NaN;
};

export const getRecordBoolean = (value: unknown, fallback: boolean): boolean => {
  if (typeof value === 'boolean') {
    return value;
  }

  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase();
    if (normalized === 'true') {
      return true;
    }
    if (normalized === 'false') {
      return false;
    }
  }

  return fallback;
};

export const isWarehouseActive = (warehouse: WarehouseRecord): boolean =>
  getRecordBoolean(warehouse.is_active, true);

export const isDefaultWarehouse = (warehouse: WarehouseRecord): boolean =>
  getRecordBoolean(warehouse.is_default, false);

export const getWarehouseId = (warehouse: WarehouseRecord): string => getRecordId(warehouse, 'id');

export const getWarehouseDepartmentId = (warehouse: WarehouseRecord): string =>
  typeof warehouse.department_id === 'string' ? warehouse.department_id.trim() : '';

export const getWarehouseRecordLabel = (warehouse: WarehouseRecord): string => {
  const warehouseName =
    typeof warehouse.name === 'string' && warehouse.name.trim().length > 0
      ? warehouse.name.trim()
      : typeof warehouse.code === 'string' && warehouse.code.trim().length > 0
        ? warehouse.code.trim()
        : getWarehouseId(warehouse);
  const warehouseCode =
    typeof warehouse.code === 'string' && warehouse.code.trim().length > 0
      ? warehouse.code.trim()
      : '';

  return warehouseCode && warehouseCode !== warehouseName
    ? `${warehouseName} (${warehouseCode})`
    : warehouseName;
};

export const compareWarehouses = (left: WarehouseRecord, right: WarehouseRecord): number => {
  if (isDefaultWarehouse(left) !== isDefaultWarehouse(right)) {
    return Number(isDefaultWarehouse(right)) - Number(isDefaultWarehouse(left));
  }

  if (isWarehouseActive(left) !== isWarehouseActive(right)) {
    return Number(isWarehouseActive(right)) - Number(isWarehouseActive(left));
  }

  const leftDepartmentId =
    typeof left.department_id === 'string' && left.department_id.trim().length > 0
      ? left.department_id.trim()
      : '';
  const rightDepartmentId =
    typeof right.department_id === 'string' && right.department_id.trim().length > 0
      ? right.department_id.trim()
      : '';
  if (leftDepartmentId !== rightDepartmentId) {
    return leftDepartmentId.localeCompare(rightDepartmentId);
  }

  return getWarehouseRecordLabel(left).localeCompare(getWarehouseRecordLabel(right));
};

export const getDefaultWarehouseId = (warehouses: WarehouseRecord[]): string => {
  if (warehouses.length === 0) {
    return '';
  }

  const defaultWarehouse =
    warehouses.find((warehouse) => isWarehouseActive(warehouse) && isDefaultWarehouse(warehouse)) ??
    warehouses.find((warehouse) => isWarehouseActive(warehouse)) ??
    warehouses[0];

  return getWarehouseId(defaultWarehouse);
};

export const getSuggestedInventoryUnit = (itemType: InventoryItemType): InventoryUnit => {
  switch (itemType) {
    case 'feed':
    case 'semi_product':
      return 'kg';
    case 'medicine':
      return 'pcs';
    case 'egg':
    case 'chick':
    default:
      return 'pcs';
  }
};
