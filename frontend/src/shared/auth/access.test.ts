import { beforeAll, describe, expect, it } from 'vitest';

import { useWorkspaceStore } from '@/shared/workspace';

import { canAccessModuleKey, canReadCrudResource, getFirstAccessibleModuleKey } from './access';

describe('department implicit read access', () => {
  let eggModule = useWorkspaceStore.getState().moduleMap.egg;

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
          'warehouse.read',
        ],
        analytics_read_permissions: ['egg_production.read', 'egg_shipment.read'],
        resources: [
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
          'medicine_batch.read',
          'medicine_type.read',
          'stock_movement.read',
          'warehouse.read',
        ],
        analytics_read_permissions: ['medicine_batch.read', 'medicine_type.read'],
        resources: [
          {
            id: 'med-batch',
            module_key: 'medicine',
            key: 'batches',
            label: 'Партии',
            path: 'batches',
            permission_prefix: 'medicine_batch',
            is_head_visible: false,
          },
        ],
      },
    ]);
    eggModule = useWorkspaceStore.getState().moduleMap.egg;
  });

  it('opens the employee department module without explicit read permissions', () => {
    expect(canAccessModuleKey('egg', [], [], 'egg')).toBe(true);
    expect(getFirstAccessibleModuleKey([], [], 'egg')).toBe('egg');
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
