import { useEffect, useMemo } from 'react';

import {
  listCrudRecords,
  type CrudListResponse,
  type CrudReferenceOption,
} from '@/shared/api/backend-crud';
import { baseQueryKeys } from '@/shared/api/query-keys';
import { useApiQuery } from '@/shared/api/react-query';
import type { TranslateFn } from '@/shared/i18n/types';
import { isValidUuid } from '@/shared/lib/uuid';

import type { FormValues } from '../module-crud-page.helpers';

import {
  compareWarehouses,
  getDefaultWarehouseId,
  getWarehouseDepartmentId,
  getWarehouseId,
  getWarehouseRecordLabel,
  isDefaultWarehouse,
  isWarehouseActive,
  type WarehouseRecord,
} from './warehouse-utils';

export interface UseWarehouseMovementOptions {
  t: TranslateFn;
  isInventoryMovementsResource: boolean;
  isTransferMovementForm: boolean;
  isFormSheetOpen: boolean;
  selectedRecordId: string;
  formValues: FormValues;
  availableDepartmentIds: Set<string>;
  selectedDepartmentId: string;
  fallbackDepartmentId: string;
  departmentNodeMap: Map<string, { depth: number; label: string }>;
  setFormValues: React.Dispatch<React.SetStateAction<FormValues>>;
}

export function useWarehouseMovement(options: UseWarehouseMovementOptions) {
  const {
    t,
    isInventoryMovementsResource,
    isTransferMovementForm,
    isFormSheetOpen,
    selectedRecordId,
    formValues,
    availableDepartmentIds,
    selectedDepartmentId,
    fallbackDepartmentId,
    departmentNodeMap,
    setFormValues,
  } = options;

  const warehouseQuery = useApiQuery<CrudListResponse>({
    queryKey: baseQueryKeys.crud.resource('core', 'warehouses-filter'),
    queryFn: () => listCrudRecords('core', 'warehouses', { orderBy: 'department_id' }),
    enabled: isInventoryMovementsResource,
  });

  const availableWarehouses = useMemo(() => {
    const warehouseItems = (warehouseQuery.data?.items ?? []) as WarehouseRecord[];

    return warehouseItems
      .filter((warehouse) => {
        const warehouseId = getWarehouseId(warehouse);
        const departmentId = getWarehouseDepartmentId(warehouse);

        return (
          isValidUuid(warehouseId) &&
          departmentId.length > 0 &&
          availableDepartmentIds.has(departmentId)
        );
      })
      .sort(compareWarehouses);
  }, [availableDepartmentIds, warehouseQuery.data]);

  const warehouseById = useMemo(
    () =>
      new Map(
        availableWarehouses.map((warehouse) => [getWarehouseId(warehouse), warehouse] as const),
      ),
    [availableWarehouses],
  );

  const warehousesByDepartmentId = useMemo(() => {
    const nextMap = new Map<string, WarehouseRecord[]>();

    availableWarehouses.forEach((warehouse) => {
      const departmentId = getWarehouseDepartmentId(warehouse);
      if (!departmentId) {
        return;
      }

      const currentWarehouses = nextMap.get(departmentId) ?? [];
      currentWarehouses.push(warehouse);
      nextMap.set(departmentId, currentWarehouses);
    });

    return nextMap;
  }, [availableWarehouses]);

  const movementDepartmentId = useMemo(() => {
    if (!isInventoryMovementsResource) {
      return '';
    }

    const formDepartmentId =
      typeof formValues.department_id === 'string' ? formValues.department_id.trim() : '';
    if (formDepartmentId && availableDepartmentIds.has(formDepartmentId)) {
      return formDepartmentId;
    }
    if (selectedDepartmentId && availableDepartmentIds.has(selectedDepartmentId)) {
      return selectedDepartmentId;
    }
    if (fallbackDepartmentId && availableDepartmentIds.has(fallbackDepartmentId)) {
      return fallbackDepartmentId;
    }
    return '';
  }, [
    availableDepartmentIds,
    fallbackDepartmentId,
    formValues.department_id,
    isInventoryMovementsResource,
    selectedDepartmentId,
  ]);

  const movementWarehouseRecords = useMemo(() => {
    if (!isInventoryMovementsResource || !movementDepartmentId) {
      return [] as WarehouseRecord[];
    }

    return (warehousesByDepartmentId.get(movementDepartmentId) ?? []).filter((warehouse) =>
      isWarehouseActive(warehouse),
    );
  }, [isInventoryMovementsResource, movementDepartmentId, warehousesByDepartmentId]);

  const movementCounterpartyWarehouseRecords = useMemo(() => {
    if (!isInventoryMovementsResource || !isTransferMovementForm) {
      return [] as WarehouseRecord[];
    }

    const selectedWarehouseId =
      typeof formValues.warehouse_id === 'string' ? formValues.warehouse_id.trim() : '';

    return availableWarehouses.filter((warehouse) => {
      const warehouseId = getWarehouseId(warehouse);
      return (
        isWarehouseActive(warehouse) &&
        warehouseId.length > 0 &&
        warehouseId !== selectedWarehouseId
      );
    });
  }, [
    availableWarehouses,
    formValues.warehouse_id,
    isInventoryMovementsResource,
    isTransferMovementForm,
  ]);

  const movementWarehouseIds = useMemo(
    () =>
      new Set(
        movementWarehouseRecords.map((warehouse) => getWarehouseId(warehouse)).filter(Boolean),
      ),
    [movementWarehouseRecords],
  );

  const movementCounterpartyWarehouseIds = useMemo(
    () =>
      new Set(
        movementCounterpartyWarehouseRecords
          .map((warehouse) => getWarehouseId(warehouse))
          .filter(Boolean),
      ),
    [movementCounterpartyWarehouseRecords],
  );

  const movementWarehouseReferenceOptions = useMemo<CrudReferenceOption[]>(
    () =>
      movementWarehouseRecords.map((warehouse) => {
        const departmentId = getWarehouseDepartmentId(warehouse);
        const departmentLabel =
          departmentNodeMap.get(departmentId)?.label ??
          t('common.notSpecified', undefined, 'Не определён');
        const warehouseLabel = getWarehouseRecordLabel(warehouse);
        const defaultSuffix = isDefaultWarehouse(warehouse)
          ? ` · ${t('fields.is_default', undefined, 'По умолчанию')}`
          : '';
        const labelPrefix = movementDepartmentId ? '' : `${departmentLabel} · `;

        return {
          value: getWarehouseId(warehouse),
          label: `${labelPrefix}${warehouseLabel}${defaultSuffix}`,
        };
      }),
    [departmentNodeMap, movementDepartmentId, movementWarehouseRecords, t],
  );

  const movementCounterpartyWarehouseReferenceOptions = useMemo<CrudReferenceOption[]>(
    () =>
      movementCounterpartyWarehouseRecords.map((warehouse) => {
        const departmentId = getWarehouseDepartmentId(warehouse);
        const departmentLabel =
          departmentNodeMap.get(departmentId)?.label ??
          t('common.notSpecified', undefined, 'Не определён');
        const warehouseLabel = getWarehouseRecordLabel(warehouse);
        const defaultSuffix = isDefaultWarehouse(warehouse)
          ? ` · ${t('fields.is_default', undefined, 'По умолчанию')}`
          : '';

        return {
          value: getWarehouseId(warehouse),
          label: `${departmentLabel} · ${warehouseLabel}${defaultSuffix}`,
        };
      }),
    [departmentNodeMap, movementCounterpartyWarehouseRecords, t],
  );

  useEffect(() => {
    if (!isInventoryMovementsResource || !isFormSheetOpen) {
      return;
    }

    setFormValues((current) => {
      const currentWarehouseId =
        typeof current.warehouse_id === 'string' ? current.warehouse_id.trim() : '';
      const currentCounterpartyWarehouseId =
        typeof current.counterparty_warehouse_id === 'string'
          ? current.counterparty_warehouse_id.trim()
          : '';
      let hasChanges = false;
      const nextValues = { ...current };

      if (currentWarehouseId && !movementWarehouseIds.has(currentWarehouseId)) {
        nextValues.warehouse_id = '';
        hasChanges = true;
      }
      if (
        currentCounterpartyWarehouseId &&
        !movementCounterpartyWarehouseIds.has(currentCounterpartyWarehouseId)
      ) {
        nextValues.counterparty_warehouse_id = '';
        nextValues.counterparty_department_id = '';
        hasChanges = true;
      }

      return hasChanges ? nextValues : current;
    });
  }, [
    isFormSheetOpen,
    isInventoryMovementsResource,
    movementCounterpartyWarehouseIds,
    movementWarehouseIds,
    setFormValues,
  ]);

  useEffect(() => {
    if (!isInventoryMovementsResource || !isFormSheetOpen || selectedRecordId) {
      return;
    }

    const defaultWarehouseId = getDefaultWarehouseId(movementWarehouseRecords);
    if (!defaultWarehouseId) {
      return;
    }

    setFormValues((current) => {
      const currentWarehouseId =
        typeof current.warehouse_id === 'string' ? current.warehouse_id.trim() : '';
      if (currentWarehouseId && movementWarehouseIds.has(currentWarehouseId)) {
        return current;
      }

      return {
        ...current,
        warehouse_id: defaultWarehouseId,
      };
    });
  }, [
    isFormSheetOpen,
    isInventoryMovementsResource,
    movementWarehouseIds,
    movementWarehouseRecords,
    selectedRecordId,
    setFormValues,
  ]);

  return {
    warehouseQuery,
    warehouseById,
    movementDepartmentId,
    movementWarehouseReferenceOptions,
    movementCounterpartyWarehouseReferenceOptions,
  };
}
