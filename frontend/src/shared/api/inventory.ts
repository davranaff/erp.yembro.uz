import { z } from 'zod';

import { apiClient } from './api-client';

export const inventoryItemTypeSchema = z.enum(['egg', 'chick', 'feed', 'medicine', 'semi_product']);
export const inventoryUnitSchema = z.enum(['pcs', 'kg', 'ltr']);

export const stockBalanceItemSchema = z.object({
  item_type: z.string(),
  item_key: z.string(),
  balance: z.string(),
  unit: z.string().nullable().optional(),
  last_movement_on: z.string().nullable().optional(),
});

export const inventoryStockBalanceResponseSchema = z.object({
  item_type: z.string(),
  department_id: z.string().trim().nullable().optional(),
  warehouse_id: z.string().trim().nullable().optional(),
  as_of: z.string().nullable().optional(),
  item_key: z.string().optional(),
  balance: z.string().optional(),
  items: z.array(stockBalanceItemSchema).optional(),
});

export const inventoryTransferRequestSchema = z
  .object({
    item_type: inventoryItemTypeSchema,
    item_key: z.string().trim().min(1),
    quantity: z.number().positive(),
    unit: inventoryUnitSchema,
    to_department_id: z.string().trim().min(1).optional(),
    from_department_id: z.string().trim().min(1).optional(),
    from_warehouse_id: z.string().trim().min(1).optional(),
    to_warehouse_id: z.string().trim().min(1).optional(),
    occurred_on: z.string().trim().optional(),
    note: z.string().trim().optional(),
  })
  .superRefine((value, context) => {
    if (!value.to_department_id && !value.to_warehouse_id) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['to_warehouse_id'],
        message: 'Destination warehouse or department is required',
      });
    }
  });

export const inventoryTransferResponseSchema = z.object({
  transfer_id: z.string(),
  organization_id: z.string(),
  item_type: inventoryItemTypeSchema,
  item_key: z.string(),
  quantity: z.string(),
  unit: inventoryUnitSchema,
  occurred_on: z.string(),
  from_department_id: z.string().trim().nullable().optional(),
  to_department_id: z.string().trim().nullable().optional(),
  from_warehouse_id: z.string().trim().nullable().optional(),
  to_warehouse_id: z.string().trim().nullable().optional(),
  note: z.string().nullable().optional(),
});

export type InventoryItemType = z.infer<typeof inventoryItemTypeSchema>;
export type InventoryUnit = z.infer<typeof inventoryUnitSchema>;
export type StockBalanceItem = z.infer<typeof stockBalanceItemSchema>;
export type InventoryStockBalanceResponse = z.infer<typeof inventoryStockBalanceResponseSchema>;
export type InventoryTransferRequest = z.infer<typeof inventoryTransferRequestSchema>;
export type InventoryTransferResponse = z.infer<typeof inventoryTransferResponseSchema>;

export type InventoryStockBalanceFilters = {
  itemType: InventoryItemType;
  itemKey?: string;
  asOf?: string;
  departmentId?: string;
  warehouseId?: string;
};

export const getInventoryStockBalance = async (
  filters: InventoryStockBalanceFilters,
): Promise<InventoryStockBalanceResponse> => {
  const searchParams = new URLSearchParams();
  searchParams.set('item_type', filters.itemType);

  if (filters.itemKey) {
    searchParams.set('item_key', filters.itemKey.trim());
  }

  if (filters.asOf) {
    searchParams.set('as_of', filters.asOf.trim());
  }

  if (filters.departmentId) {
    searchParams.set('department_id', filters.departmentId.trim());
  }

  if (filters.warehouseId) {
    searchParams.set('warehouse_id', filters.warehouseId.trim());
  }

  return apiClient.get(
    `/inventory/stock/balance?${searchParams.toString()}`,
    inventoryStockBalanceResponseSchema,
  );
};

export const createInventoryStockTransfer = async (
  payload: InventoryTransferRequest,
): Promise<InventoryTransferResponse> => {
  return apiClient.post('/inventory/stock/transfer', payload, inventoryTransferResponseSchema);
};
