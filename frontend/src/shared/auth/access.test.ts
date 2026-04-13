import { beforeAll, describe, expect, it } from 'vitest';

import { useWorkspaceStore } from '@/shared/workspace';
import { canAccessModuleKey, canReadCrudResource, getFirstAccessibleModuleKey } from './access';

describe('department implicit read access', () => {
  let eggModule = useWorkspaceStore.getState().moduleMap.egg;
  let medicineModule = useWorkspaceStore.getState().moduleMap.medicine;

  beforeAll(() => {
    useWorkspaceStore.getState().setModules([
      {
        id: 'module-egg',
        key: 'egg',
        label: 'Маточник',
        description: '',
        icon: 'egg',
        sort_order: 10,
        is_department_assignable: true,
        analytics_section_key: 'egg_farm',
        implicit_read_permissions: [
          'egg_production.read',
          'egg_shipment.read',
          'egg_monthly_analytics.read',
          'feed_consumption.read',
          'medicine_consumption.read',
          'warehouse.read',
        ],
        analytics_read_permissions: [
          'egg_production.read',
          'egg_shipment.read',
          'feed_consumption.read',
          'medicine_consumption.read',
        ],
        resources: [
          {
            id: 'egg-med',
            module_key: 'egg',
            key: 'medicine-consumptions',
            label: 'Расход лекарств',
            path: 'consumptions',
            permission_prefix: 'medicine_consumption',
            api_module_key: 'medicine',
            is_head_visible: false,
          },
          {
            id: 'egg-client',
            module_key: 'egg',
            key: 'clients',
            label: 'Клиенты',
            path: 'clients',
            permission_prefix: 'client',
            api_module_key: 'core',
            is_head_visible: true,
          },
          {
            id: 'egg-warehouse',
            module_key: 'egg',
            key: 'warehouses',
            label: 'Склады',
            path: 'warehouses',
            permission_prefix: 'warehouse',
            api_module_key: 'core',
            is_head_visible: true,
          },
        ],
      },
      {
        id: 'module-medicine',
        key: 'medicine',
        label: 'Вет аптека',
        description: '',
        icon: 'pill',
        sort_order: 20,
        is_department_assignable: true,
        analytics_section_key: 'vet_pharmacy',
        implicit_read_permissions: [
          'medicine_arrival.read',
          'medicine_consumption.read',
          'medicine_batch.read',
          'medicine_type.read',
        ],
        analytics_read_permissions: [
          'medicine_arrival.read',
          'medicine_consumption.read',
          'medicine_batch.read',
          'medicine_type.read',
        ],
        resources: [
          {
            id: 'med-arr',
            module_key: 'medicine',
            key: 'arrivals',
            label: 'Приход лекарств',
            path: 'arrivals',
            permission_prefix: 'medicine_arrival',
            is_head_visible: false,
          },
        ],
      },
    ]);
    eggModule = useWorkspaceStore.getState().moduleMap.egg;
    medicineModule = useWorkspaceStore.getState().moduleMap.medicine;
  });

  it('opens the employee department module without explicit read permissions', () => {
    expect(canAccessModuleKey('egg', [], [], 'egg')).toBe(true);
    expect(getFirstAccessibleModuleKey([], [], 'egg')).toBe('egg');
  });

  it('keeps cross-api resources available only inside the owning department module', () => {
    const eggMedicineConsumptionResource = eggModule.resources.find(
      (resource) => resource.permissionPrefix === 'medicine_consumption',
    );
    expect(eggMedicineConsumptionResource).toBeDefined();
    expect(
      canReadCrudResource([], [], 'egg', eggMedicineConsumptionResource!, 'egg'),
    ).toBe(true);

    expect(canAccessModuleKey(medicineModule.key, [], [], 'egg')).toBe(false);
  });

  it('does not auto-grant shared read resources like clients', () => {
    const eggClientResource = eggModule.resources.find(
      (resource) => resource.permissionPrefix === 'client',
    );
    expect(eggClientResource).toBeDefined();
    expect(canReadCrudResource([], [], 'egg', eggClientResource!, 'egg')).toBe(false);
  });

  it('allows module-local warehouse resources through implicit warehouse read access', () => {
    const eggWarehouseResource = eggModule.resources.find(
      (resource) => resource.permissionPrefix === 'warehouse',
    );
    expect(eggWarehouseResource).toBeDefined();
    expect(canReadCrudResource([], [], 'egg', eggWarehouseResource!, 'egg')).toBe(true);
  });
});
