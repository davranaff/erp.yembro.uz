import { useMemo } from 'react';

import { listVisibleDepartments, type CrudListResponse } from '@/shared/api/backend-crud';
import { baseQueryKeys } from '@/shared/api/query-keys';
import { useApiQuery } from '@/shared/api/react-query';
import { buildDepartmentTree, flattenDepartmentTree } from '@/shared/lib/departments';
import { isValidUuid } from '@/shared/lib/uuid';
import type { BackendModuleConfig } from '@/shared/workspace';

import { getDepartmentLabel, type DepartmentRecord } from '../module-crud-page.helpers';

export interface UseDepartmentsOptions {
  moduleConfig: BackendModuleConfig | null;
  sessionEmployeeId: string;
  requestedDepartmentId: string;
}

export function useDepartments(options: UseDepartmentsOptions) {
  const { moduleConfig, sessionEmployeeId, requestedDepartmentId } = options;

  const departmentQuery = useApiQuery<CrudListResponse>({
    queryKey: baseQueryKeys.crud.resource('core', 'visible-departments-filter'),
    queryFn: () => listVisibleDepartments(),
    enabled: Boolean(moduleConfig?.isDepartmentAssignable && sessionEmployeeId),
  });

  const allDepartments = useMemo(
    () => (departmentQuery.data?.items ?? []) as DepartmentRecord[],
    [departmentQuery.data?.items],
  );

  const departmentModuleKey =
    moduleConfig && moduleConfig.isDepartmentAssignable ? moduleConfig.key : null;

  const availableDepartments = useMemo(() => {
    if (!moduleConfig || !moduleConfig.isDepartmentAssignable) {
      return [] as DepartmentRecord[];
    }

    if (departmentModuleKey === null) {
      return allDepartments.filter(
        (department) => typeof department.id === 'string' && isValidUuid(department.id),
      );
    }

    return allDepartments.filter(
      (department) =>
        department.module_key === departmentModuleKey &&
        typeof department.id === 'string' &&
        isValidUuid(department.id),
    );
  }, [allDepartments, departmentModuleKey, moduleConfig]);

  const departmentTree = useMemo(
    () => buildDepartmentTree(availableDepartments, getDepartmentLabel),
    [availableDepartments],
  );

  const departmentOptions = useMemo(() => flattenDepartmentTree(departmentTree), [departmentTree]);
  const departmentFilterOptions = departmentOptions;

  const selectableDepartmentOptions = useMemo(
    () => departmentOptions.filter((department) => department.children.length === 0),
    [departmentOptions],
  );

  const departmentNodeMap = useMemo(
    () => new Map(departmentOptions.map((department) => [department.id, department] as const)),
    [departmentOptions],
  );

  const selectableDepartmentIds = useMemo(
    () => new Set(selectableDepartmentOptions.map((department) => department.id)),
    [selectableDepartmentOptions],
  );

  const availableDepartmentIds = useMemo(
    () => new Set(departmentFilterOptions.map((department) => department.id)),
    [departmentFilterOptions],
  );

  const supportsDepartmentFilter = departmentFilterOptions.length > 0;

  const selectedDepartmentId =
    supportsDepartmentFilter &&
    isValidUuid(requestedDepartmentId) &&
    availableDepartmentIds.has(requestedDepartmentId)
      ? requestedDepartmentId
      : '';

  return {
    allDepartments,
    availableDepartments,
    departmentTree,
    departmentOptions,
    departmentFilterOptions,
    selectableDepartmentOptions,
    departmentNodeMap,
    selectableDepartmentIds,
    availableDepartmentIds,
    supportsDepartmentFilter,
    selectedDepartmentId,
  };
}
