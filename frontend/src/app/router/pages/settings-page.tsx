import {
  type MouseEvent as ReactMouseEvent,
  type ReactNode,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import {
  Building2,
  ChevronDown,
  LockKeyhole,
  Mail,
  Pencil,
  Phone,
  Plus,
  Search,
  Save,
  ShieldCheck,
  Trash2,
  UserRound,
  Waypoints,
  X,
  type LucideIcon,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { CrudDrawer, CrudDrawerFooter } from '@/components/ui/crud-drawer';
import { CustomSelect, type CustomSelectOption } from '@/components/ui/custom-select';
import { ErrorNotice } from '@/components/ui/error-notice';
import { Input } from '@/components/ui/input';
import { Sheet } from '@/components/ui/sheet';
import {
  createCrudRecord,
  deleteCrudRecord,
  listCrudRecords,
  updateCrudRecord,
  type CrudListResponse,
  type CrudRecord,
} from '@/shared/api/backend-crud';
import {
  createAuthProfileUpdateSchema,
  getMyProfile,
  updateMyProfile,
  type AuthProfileUpdate,
} from '@/shared/api/auth';
import { baseQueryKeys } from '@/shared/api/query-keys';
import { useApiMutation, useApiQuery } from '@/shared/api/react-query';
import {
  canCreateDepartmentsGlobally,
  canDeleteDepartmentsGlobally,
  canReadDepartmentsDirectory,
  canWriteDepartmentsGlobally,
  useAuthStore,
} from '@/shared/auth';
import { departmentIconOptions, getDepartmentIcon } from '@/shared/config/department-icons';
import { useI18n } from '@/shared/i18n';
import { cn } from '@/shared/lib/cn';
import {
  buildDepartmentTree,
  flattenDepartmentTree,
  type DepartmentTreeNode,
} from '@/shared/lib/departments';
import {
  buildDepartmentForm,
  canCreateSubdepartmentForAccess,
  canDeleteDepartmentByIdAccess,
  canDeleteDepartmentRecordAccess,
  canManageDepartmentRecordAccess,
  canSaveDepartmentDraftAccess,
  defaultDepartmentForm,
  DepartmentFormState,
  DepartmentModuleRecord,
  DepartmentRecord,
  DepartmentSheetMode,
  DepartmentStatusFilter,
  drawerPrimaryButtonClassName,
  getDepartmentIconLabel,
  getDepartmentLabel,
  getDepartmentModuleKey,
  getDepartmentModuleLabel,
  getEmployeeLabel,
  getEmployeeOptionLabel,
  getEmployeeUserHandle,
  getOrganizationLabel,
  getProfileInitials,
  getRecordId,
  managementInputClassName,
  managementPanelClassName,
  managementPillClassName,
  type EmployeeRecord,
  type OrganizationRecord,
  settingsAvatarTileClassName,
  settingsCardClassName,
  settingsGlassPanelClassName,
  settingsGlassPanelSoftClassName,
  settingsHeroCardClassName,
  settingsIconTileClassName,
  type SettingsTabKey,
} from './settings-page.helpers';

const defaultValues: AuthProfileUpdate = {
  firstName: '',
  lastName: '',
  email: '',
  phone: '',
  currentPassword: '',
  newPassword: '',
  confirmNewPassword: '',
};

const hiddenDepartmentModuleKeys = new Set(['core', 'finance', 'hr']);

export function SettingsPage() {
  const { t } = useI18n();
  const authSession = useAuthStore((state) => state.session);
  const schema = useMemo(() => createAuthProfileUpdateSchema(t), [t]);
  const [activeTab, setActiveTab] = useState<SettingsTabKey>('account');
  const [isAccountSheetOpen, setIsAccountSheetOpen] = useState(false);
  const [isDepartmentSheetOpen, setIsDepartmentSheetOpen] = useState(false);
  const [selectedDepartmentId, setSelectedDepartmentId] = useState('');
  const [departmentSheetMode, setDepartmentSheetMode] = useState<DepartmentSheetMode>('create');
  const [departmentEditingId, setDepartmentEditingId] = useState('');
  const [deleteConfirmDepartmentId, setDeleteConfirmDepartmentId] = useState('');
  const [collapsedDepartmentRootIds, setCollapsedDepartmentRootIds] = useState<string[]>([]);
  const [departmentForm, setDepartmentForm] = useState<DepartmentFormState>(defaultDepartmentForm);
  const [departmentSearch, setDepartmentSearch] = useState('');
  const [departmentModuleFilter, setDepartmentModuleFilter] = useState('all');
  const [departmentStatusFilter, setDepartmentStatusFilter] =
    useState<DepartmentStatusFilter>('all');
  const profileQuery = useApiQuery({
    queryKey: baseQueryKeys.auth.me,
    queryFn: getMyProfile,
  });
  const sessionRoles = authSession?.roles ?? [];
  const sessionPermissions = authSession?.permissions ?? [];
  const canOpenDepartmentsTab = canReadDepartmentsDirectory(
    sessionRoles,
    sessionPermissions,
    authSession?.headsAnyDepartment ?? profileQuery.data?.headsAnyDepartment ?? false,
  );
  const organizationsQuery = useApiQuery<CrudListResponse>({
    queryKey: baseQueryKeys.crud.resource('core', 'settings-organizations'),
    queryFn: () => listCrudRecords('core', 'organizations'),
  });
  const departmentsQuery = useApiQuery<CrudListResponse>({
    queryKey: baseQueryKeys.crud.resource('core', 'settings-departments'),
    queryFn: () => listCrudRecords('core', 'departments'),
    enabled: activeTab === 'departments' && canOpenDepartmentsTab,
  });
  const departmentModulesQuery = useApiQuery<CrudListResponse>({
    queryKey: baseQueryKeys.crud.resource('core', 'settings-department-modules'),
    queryFn: () => listCrudRecords('core', 'department-modules', { orderBy: 'sort_order' }),
    enabled: activeTab === 'departments' && canOpenDepartmentsTab,
  });
  const employeesQuery = useApiQuery<CrudListResponse>({
    queryKey: baseQueryKeys.crud.resource('hr', 'settings-employees'),
    queryFn: () => listCrudRecords('hr', 'employees'),
    enabled: activeTab === 'departments' && canOpenDepartmentsTab,
  });

  const form = useForm<AuthProfileUpdate>({
    resolver: zodResolver(schema),
    defaultValues,
    mode: 'onSubmit',
  });

  const organizations = useMemo(
    () => (organizationsQuery.data?.items ?? []) as OrganizationRecord[],
    [organizationsQuery.data],
  );
  const departmentModules = useMemo(
    () => (departmentModulesQuery.data?.items ?? []) as DepartmentModuleRecord[],
    [departmentModulesQuery.data],
  );
  const assignableDepartmentModules = useMemo(
    () =>
      departmentModules.filter((departmentModule) => {
        const moduleKey = getDepartmentModuleKey(departmentModule).trim().toLowerCase();
        return (
          moduleKey !== '' &&
          departmentModule.is_active !== false &&
          departmentModule.is_department_assignable !== false &&
          !hiddenDepartmentModuleKeys.has(moduleKey)
        );
      }),
    [departmentModules],
  );
  const currentOrganizationId =
    authSession?.organizationId ?? profileQuery.data?.organizationId ?? '';
  const scopedOrganizations = useMemo(
    () =>
      currentOrganizationId
        ? organizations.filter(
            (organization) => getRecordId(organization) === currentOrganizationId,
          )
        : organizations,
    [currentOrganizationId, organizations],
  );
  const departments = useMemo(
    () =>
      ((departmentsQuery.data?.items ?? []) as DepartmentRecord[]).filter(
        (department) =>
          !currentOrganizationId || department.organization_id === currentOrganizationId,
      ),
    [currentOrganizationId, departmentsQuery.data],
  );
  const employees = useMemo(
    () =>
      ((employeesQuery.data?.items ?? []) as EmployeeRecord[]).filter(
        (employee) => !currentOrganizationId || employee.organization_id === currentOrganizationId,
      ),
    [currentOrganizationId, employeesQuery.data],
  );
  const employeeMap = useMemo(
    () =>
      new Map(
        employees
          .map((employee) => [getRecordId(employee), employee] as const)
          .filter(([employeeId]) => employeeId !== ''),
      ),
    [employees],
  );
  const defaultOrganizationId = useMemo(
    () => currentOrganizationId || getRecordId(scopedOrganizations[0]),
    [currentOrganizationId, scopedOrganizations],
  );
  const departmentModuleLabelMap = useMemo(
    () =>
      new Map(
        departmentModules
          .map(
            (departmentModule) =>
              [
                getDepartmentModuleKey(departmentModule),
                getDepartmentModuleLabel(departmentModule),
              ] as const,
          )
          .filter(([moduleKey]) => moduleKey !== ''),
      ),
    [departmentModules],
  );
  const departmentModuleSortOrderMap = useMemo(
    () =>
      new Map(
        departmentModules
          .map(
            (departmentModule) =>
              [
                getDepartmentModuleKey(departmentModule),
                typeof departmentModule.sort_order === 'number'
                  ? departmentModule.sort_order
                  : Number.MAX_SAFE_INTEGER,
              ] as const,
          )
          .filter(([moduleKey]) => moduleKey !== ''),
      ),
    [departmentModules],
  );
  const defaultDepartmentModuleKey = useMemo(() => {
    const firstDepartmentModule = assignableDepartmentModules.find(
      (departmentModule) => getDepartmentModuleKey(departmentModule) !== '',
    );
    if (firstDepartmentModule) {
      return getDepartmentModuleKey(firstDepartmentModule);
    }

    return defaultDepartmentForm.moduleKey;
  }, [assignableDepartmentModules]);
  const resolveDepartmentModuleLabel = (moduleKey: string): string => {
    if (!moduleKey) {
      return t('common.empty');
    }

    return (
      departmentModuleLabelMap.get(moduleKey) ??
      t(`modules.${moduleKey}.label`, undefined, moduleKey)
    );
  };
  const orderedDepartmentModuleKeys = useMemo(() => {
    const nextKeys: string[] = [];
    const seenKeys = new Set<string>();

    departmentModules.forEach((departmentModule) => {
      const moduleKey = getDepartmentModuleKey(departmentModule);
      if (!moduleKey || seenKeys.has(moduleKey)) {
        return;
      }

      seenKeys.add(moduleKey);
      nextKeys.push(moduleKey);
    });

    departments.forEach((department) => {
      const moduleKey = typeof department.module_key === 'string' ? department.module_key : '';
      if (!moduleKey || seenKeys.has(moduleKey)) {
        return;
      }

      seenKeys.add(moduleKey);
      nextKeys.push(moduleKey);
    });

    if (departmentForm.moduleKey && !seenKeys.has(departmentForm.moduleKey)) {
      nextKeys.push(departmentForm.moduleKey);
    }

    return nextKeys.sort((leftKey, rightKey) => {
      const leftOrder = departmentModuleSortOrderMap.get(leftKey) ?? Number.MAX_SAFE_INTEGER;
      const rightOrder = departmentModuleSortOrderMap.get(rightKey) ?? Number.MAX_SAFE_INTEGER;

      if (leftOrder !== rightOrder) {
        return leftOrder - rightOrder;
      }

      const leftLabel =
        departmentModuleLabelMap.get(leftKey) ?? t(`modules.${leftKey}.label`, undefined, leftKey);
      const rightLabel =
        departmentModuleLabelMap.get(rightKey) ??
        t(`modules.${rightKey}.label`, undefined, rightKey);

      return leftLabel.localeCompare(rightLabel);
    });
  }, [
    departmentForm.moduleKey,
    departmentModuleLabelMap,
    departmentModuleSortOrderMap,
    departmentModules,
    departments,
    t,
  ]);
  const orderedAssignableDepartmentModuleKeys = useMemo(() => {
    const nextKeys: string[] = [];
    const seenKeys = new Set<string>();

    assignableDepartmentModules.forEach((departmentModule) => {
      const moduleKey = getDepartmentModuleKey(departmentModule);
      if (!moduleKey || seenKeys.has(moduleKey)) {
        return;
      }

      seenKeys.add(moduleKey);
      nextKeys.push(moduleKey);
    });

    return nextKeys.sort((leftKey, rightKey) => {
      const leftOrder = departmentModuleSortOrderMap.get(leftKey) ?? Number.MAX_SAFE_INTEGER;
      const rightOrder = departmentModuleSortOrderMap.get(rightKey) ?? Number.MAX_SAFE_INTEGER;

      if (leftOrder !== rightOrder) {
        return leftOrder - rightOrder;
      }

      const leftLabel =
        departmentModuleLabelMap.get(leftKey) ?? t(`modules.${leftKey}.label`, undefined, leftKey);
      const rightLabel =
        departmentModuleLabelMap.get(rightKey) ??
        t(`modules.${rightKey}.label`, undefined, rightKey);

      return leftLabel.localeCompare(rightLabel);
    });
  }, [assignableDepartmentModules, departmentModuleLabelMap, departmentModuleSortOrderMap, t]);
  const currentOrganization = useMemo(
    () =>
      scopedOrganizations.find(
        (organization) => getRecordId(organization) === defaultOrganizationId,
      ) ?? null,
    [defaultOrganizationId, scopedOrganizations],
  );

  useEffect(() => {
    if (!profileQuery.data) {
      return;
    }

    form.reset({
      firstName: profileQuery.data.firstName ?? '',
      lastName: profileQuery.data.lastName ?? '',
      email: profileQuery.data.email ?? '',
      phone: profileQuery.data.phone ?? '',
      currentPassword: '',
      newPassword: '',
      confirmNewPassword: '',
    });
  }, [form, profileQuery.data]);

  useEffect(() => {
    if (!defaultOrganizationId || departmentForm.organizationId) {
      return;
    }

    setDepartmentForm((currentForm) => ({
      ...currentForm,
      organizationId: defaultOrganizationId,
    }));
  }, [defaultOrganizationId, departmentForm.organizationId]);
  useEffect(() => {
    if (!defaultDepartmentModuleKey || departmentForm.moduleKey) {
      return;
    }

    setDepartmentForm((currentForm) => ({
      ...currentForm,
      moduleKey: defaultDepartmentModuleKey,
    }));
  }, [defaultDepartmentModuleKey, departmentForm.moduleKey]);
  useEffect(() => {
    if (activeTab !== 'departments' || canOpenDepartmentsTab) {
      return;
    }

    setActiveTab('account');
  }, [activeTab, canOpenDepartmentsTab]);

  const departmentEditingRecord = useMemo(
    () => departments.find((department) => getRecordId(department) === departmentEditingId) ?? null,
    [departmentEditingId, departments],
  );
  const departmentTree = useMemo(
    () => buildDepartmentTree(departments, getDepartmentLabel),
    [departments],
  );
  useEffect(() => {
    const availableRootIds = new Set(departmentTree.map((rootNode) => rootNode.id));

    setCollapsedDepartmentRootIds((current) => {
      const next = current.filter((rootId) => availableRootIds.has(rootId));
      return next.length === current.length ? current : next;
    });
  }, [departmentTree]);
  const orderedDepartments = useMemo(() => flattenDepartmentTree(departmentTree), [departmentTree]);
  const departmentNodeMap = useMemo(
    () => new Map(orderedDepartments.map((department) => [department.id, department] as const)),
    [orderedDepartments],
  );
  const departmentRecordMap = useMemo(
    () =>
      new Map(
        departments
          .map((department) => [getRecordId(department), department] as const)
          .filter(([departmentId]) => departmentId !== ''),
      ),
    [departments],
  );
  const currentActorId = authSession?.employeeId ?? '';
  const canWriteAllDepartments = canWriteDepartmentsGlobally(sessionRoles, sessionPermissions);
  const canCreateRootDepartments = canCreateDepartmentsGlobally(sessionRoles, sessionPermissions);
  const canDeleteAnyDepartment = canDeleteDepartmentsGlobally(sessionRoles, sessionPermissions);
  const selectedDepartmentNode = useMemo(
    () => (selectedDepartmentId ? (departmentNodeMap.get(selectedDepartmentId) ?? null) : null),
    [departmentNodeMap, selectedDepartmentId],
  );
  const normalizedDepartmentSearch = departmentSearch.trim().toLowerCase();
  const filteredDepartmentNodes = useMemo(() => {
    return orderedDepartments.filter((departmentNode) => {
      const department = departmentNode.record;
      const moduleKey = typeof department.module_key === 'string' ? department.module_key : '';
      const parentDepartment =
        typeof department.parent_department_id === 'string'
          ? (departmentNodeMap.get(department.parent_department_id)?.record ?? null)
          : null;
      const headEmployee =
        typeof department.head_id === 'string'
          ? (employeeMap.get(department.head_id) ?? null)
          : null;
      const matchesModule =
        departmentModuleFilter === 'all' || moduleKey === departmentModuleFilter;
      const isActive = department.is_active !== false;
      const matchesStatus =
        departmentStatusFilter === 'all' ||
        (departmentStatusFilter === 'active' ? isActive : !isActive);

      if (!matchesModule || !matchesStatus) {
        return false;
      }

      if (!normalizedDepartmentSearch) {
        return true;
      }

      const searchValue = [
        getDepartmentLabel(department),
        typeof department.code === 'string' ? department.code : '',
        typeof department.description === 'string' ? department.description : '',
        parentDepartment ? getDepartmentLabel(parentDepartment) : '',
        headEmployee ? getEmployeeLabel(headEmployee) : '',
      ]
        .join(' ')
        .toLowerCase();

      return searchValue.includes(normalizedDepartmentSearch);
    });
  }, [
    departmentModuleFilter,
    departmentNodeMap,
    departmentStatusFilter,
    employeeMap,
    normalizedDepartmentSearch,
    orderedDepartments,
  ]);
  const blockedParentDepartmentIds = useMemo(() => {
    if (!selectedDepartmentNode) {
      return new Set<string>();
    }

    return new Set([
      selectedDepartmentNode.id,
      ...flattenDepartmentTree(selectedDepartmentNode.children).map((department) => department.id),
    ]);
  }, [selectedDepartmentNode]);
  const activeDepartmentCount = useMemo(
    () => departments.filter((department) => department.is_active !== false).length,
    [departments],
  );
  const rootDepartmentCount = departmentTree.length;
  const filteredDepartmentCount = filteredDepartmentNodes.length;
  const collapsedDepartmentRootIdSet = useMemo(
    () => new Set(collapsedDepartmentRootIds),
    [collapsedDepartmentRootIds],
  );
  const filteredDepartmentGroups = useMemo(() => {
    const nodesByRoot = new Map<string, DepartmentTreeNode<DepartmentRecord>[]>();

    filteredDepartmentNodes.forEach((departmentNode) => {
      nodesByRoot.set(departmentNode.rootId, [
        ...(nodesByRoot.get(departmentNode.rootId) ?? []),
        departmentNode,
      ]);
    });

    return departmentTree
      .map((rootNode) => {
        const visibleNodes = nodesByRoot.get(rootNode.id) ?? [];

        if (visibleNodes.length === 0) {
          return null;
        }

        return {
          rootNode,
          visibleDescendantNodes: visibleNodes.filter(
            (departmentNode) => departmentNode.id !== rootNode.id,
          ),
        };
      })
      .filter(
        (
          group,
        ): group is {
          rootNode: DepartmentTreeNode<DepartmentRecord>;
          visibleDescendantNodes: DepartmentTreeNode<DepartmentRecord>[];
        } => group !== null,
      );
  }, [departmentTree, filteredDepartmentNodes]);
  const departmentDetailsTargetId = useMemo(() => {
    if (selectedDepartmentId && departmentNodeMap.has(selectedDepartmentId)) {
      return selectedDepartmentId;
    }

    return filteredDepartmentNodes[0]?.id ?? '';
  }, [departmentNodeMap, filteredDepartmentNodes, selectedDepartmentId]);
  const headedDepartmentIdSet = useMemo(() => {
    if (!currentActorId) {
      return new Set<string>();
    }

    return new Set(
      departments
        .filter((department) => department.head_id === currentActorId)
        .map((department) => getRecordId(department))
        .filter((departmentId) => departmentId !== ''),
    );
  }, [currentActorId, departments]);
  const managedDepartmentIdSet = useMemo(() => {
    const managedIds = new Set<string>();

    headedDepartmentIdSet.forEach((departmentId) => {
      const node = departmentNodeMap.get(departmentId);
      if (!node) {
        return;
      }

      managedIds.add(departmentId);
      flattenDepartmentTree(node.children).forEach((child) => managedIds.add(child.id));
    });

    return managedIds;
  }, [departmentNodeMap, headedDepartmentIdSet]);
  const filteredParentDepartments = useMemo(() => {
    const candidates = departments.filter((department) => {
      const departmentId = getRecordId(department);
      return (
        departmentId !== '' &&
        !blockedParentDepartmentIds.has(departmentId) &&
        department.organization_id === departmentForm.organizationId &&
        department.module_key === departmentForm.moduleKey
      );
    });

    return flattenDepartmentTree(buildDepartmentTree(candidates, getDepartmentLabel));
  }, [
    blockedParentDepartmentIds,
    departments,
    departmentForm.moduleKey,
    departmentForm.organizationId,
  ]);
  const rootDepartmentByModuleKey = useMemo(() => {
    const map = new Map<string, DepartmentRecord>();

    departments.forEach((department) => {
      const departmentId = getRecordId(department);
      const moduleKey = typeof department.module_key === 'string' ? department.module_key : '';
      const parentDepartmentId =
        typeof department.parent_department_id === 'string' ? department.parent_department_id : '';

      if (!departmentId || !moduleKey || parentDepartmentId) {
        return;
      }

      map.set(moduleKey, department);
    });

    return map;
  }, [departments]);
  const selectedParentDepartment = useMemo(
    () =>
      departmentForm.parentDepartmentId
        ? (departmentRecordMap.get(departmentForm.parentDepartmentId) ?? null)
        : null,
    [departmentForm.parentDepartmentId, departmentRecordMap],
  );
  const availableRootDepartmentModuleKeys = useMemo(
    () =>
      orderedAssignableDepartmentModuleKeys.filter((moduleKey) => {
        const rootDepartment = rootDepartmentByModuleKey.get(moduleKey);
        if (!rootDepartment) {
          return true;
        }

        return getRecordId(rootDepartment) === departmentEditingId;
      }),
    [departmentEditingId, orderedAssignableDepartmentModuleKeys, rootDepartmentByModuleKey],
  );
  const selectableDepartmentModuleKeys = useMemo(() => {
    if (selectedParentDepartment?.module_key) {
      return [selectedParentDepartment.module_key];
    }

    const nextKeys = [...availableRootDepartmentModuleKeys];
    if (departmentForm.moduleKey && !nextKeys.includes(departmentForm.moduleKey)) {
      nextKeys.unshift(departmentForm.moduleKey);
    }

    const seenKeys = new Set<string>();
    return nextKeys.filter((moduleKey) => {
      if (!moduleKey || seenKeys.has(moduleKey)) {
        return false;
      }

      seenKeys.add(moduleKey);
      return true;
    });
  }, [
    availableRootDepartmentModuleKeys,
    departmentForm.moduleKey,
    selectedParentDepartment?.module_key,
  ]);
  const departmentModuleSelectOptions = useMemo<CustomSelectOption[]>(
    () =>
      selectableDepartmentModuleKeys.map((moduleKey) => ({
        value: moduleKey,
        label: resolveDepartmentModuleLabel(moduleKey),
        searchText: moduleKey,
      })),
    [resolveDepartmentModuleLabel, selectableDepartmentModuleKeys],
  );

  const filteredEmployees = useMemo(() => {
    return employees.filter(
      (employee) => employee.organization_id === departmentForm.organizationId,
    );
  }, [departmentForm.organizationId, employees]);
  const assignableEmployees = useMemo(() => {
    return [...filteredEmployees].sort((left, right) => {
      const currentEmployeeId = authSession?.employeeId ?? '';
      const leftId = getRecordId(left);
      const rightId = getRecordId(right);
      const leftIsCurrent = leftId !== '' && leftId === currentEmployeeId;
      const rightIsCurrent = rightId !== '' && rightId === currentEmployeeId;

      if (leftIsCurrent !== rightIsCurrent) {
        return leftIsCurrent ? -1 : 1;
      }

      const leftIsActive = left.is_active !== false;
      const rightIsActive = right.is_active !== false;

      if (leftIsActive !== rightIsActive) {
        return leftIsActive ? -1 : 1;
      }

      return getEmployeeLabel(left).localeCompare(getEmployeeLabel(right));
    });
  }, [authSession?.employeeId, filteredEmployees]);
  const departmentFilterModuleOptions = useMemo<CustomSelectOption[]>(
    () => [
      {
        value: 'all',
        label: t('settings.statusAll', undefined, 'Все'),
      },
      ...orderedDepartmentModuleKeys.map((moduleKey) => ({
        value: moduleKey,
        label: resolveDepartmentModuleLabel(moduleKey),
        searchText: moduleKey,
      })),
    ],
    [orderedDepartmentModuleKeys, resolveDepartmentModuleLabel, t],
  );
  const departmentStatusOptions = useMemo<CustomSelectOption[]>(
    () => [
      {
        value: 'all',
        label: t('settings.statusAll', undefined, 'Все'),
      },
      {
        value: 'active',
        label: t('settings.statusActive', undefined, 'Только активные'),
      },
      {
        value: 'inactive',
        label: t('settings.statusInactive', undefined, 'Только неактивные'),
      },
    ],
    [t],
  );
  const assignableEmployeeOptions = useMemo<CustomSelectOption[]>(
    () => [
      {
        value: '',
        label: t('settings.responsibleUserPlaceholder', undefined, 'Выберите пользователя'),
      },
      ...assignableEmployees.map((employee) => ({
        value: getRecordId(employee),
        label: getEmployeeOptionLabel(employee),
        searchText: [
          getEmployeeLabel(employee),
          getEmployeeUserHandle(employee),
          typeof employee.email === 'string' ? employee.email : '',
        ].join(' '),
      })),
    ],
    [assignableEmployees, t],
  );
  const parentDepartmentOptions = useMemo<CustomSelectOption[]>(
    () => [
      {
        value: '',
        label: t('common.chooseValue'),
      },
      ...filteredParentDepartments.map((department) => ({
        value: department.id,
        label: `${' '.repeat(department.depth * 2)}${department.label}`,
        searchText: department.label,
      })),
    ],
    [filteredParentDepartments, t],
  );
  const departmentRbacScope = useMemo(
    () => ({
      canWriteAllDepartments,
      canCreateRootDepartments,
      canDeleteAnyDepartment,
      managedDepartmentIds: managedDepartmentIdSet,
      headedDepartmentIds: headedDepartmentIdSet,
    }),
    [
      canCreateRootDepartments,
      canDeleteAnyDepartment,
      canWriteAllDepartments,
      headedDepartmentIdSet,
      managedDepartmentIdSet,
    ],
  );
  const canManageDepartmentRecord = (department: DepartmentRecord): boolean => {
    const departmentId = getRecordId(department);
    return canManageDepartmentRecordAccess(departmentId, departmentRbacScope);
  };
  const canCreateSubdepartmentFor = (department: DepartmentRecord): boolean => {
    const departmentId = getRecordId(department);
    return canCreateSubdepartmentForAccess(departmentId, departmentRbacScope);
  };
  const canDeleteDepartmentRecord = (department: DepartmentRecord): boolean => {
    const departmentId = getRecordId(department);
    return canDeleteDepartmentRecordAccess(departmentId, departmentRbacScope);
  };
  const canSaveDepartmentDraft = (
    values: DepartmentFormState,
    mode: DepartmentSheetMode,
    editingId: string,
  ): boolean => {
    return canSaveDepartmentDraftAccess({
      departmentForm: values,
      departmentSheetMode: mode,
      departmentEditingId: editingId,
      departmentRecordMap,
      scope: departmentRbacScope,
    });
  };
  const canDeleteDepartmentById = (departmentId: string): boolean => {
    return canDeleteDepartmentByIdAccess(departmentId, departmentRecordMap, departmentRbacScope);
  };

  const updateProfileMutation = useApiMutation({
    mutationKey: ['auth', 'me', 'update'],
    mutationFn: (values: AuthProfileUpdate) =>
      updateMyProfile({
        firstName: values.firstName.trim(),
        lastName: values.lastName.trim(),
        email: values.email?.trim() || undefined,
        phone: values.phone?.trim() || undefined,
        currentPassword: values.currentPassword?.trim() || undefined,
        newPassword: values.newPassword?.trim() || undefined,
      }),
    onSuccess: (profile) => {
      form.reset({
        firstName: profile.firstName ?? '',
        lastName: profile.lastName ?? '',
        email: profile.email ?? '',
        phone: profile.phone ?? '',
        currentPassword: '',
        newPassword: '',
        confirmNewPassword: '',
      });
      setIsAccountSheetOpen(false);
      profileQuery.refetch();
    },
  });

  const departmentSaveMutation = useApiMutation<CrudRecord, Error, DepartmentFormState>({
    mutationKey: ['settings', 'departments', 'save'],
    mutationFn: async (values) => {
      if (!canSaveDepartmentDraft(values, departmentSheetMode, departmentEditingId)) {
        throw new Error('Недостаточно прав для сохранения отдела.');
      }

      const payload = {
        organization_id: values.organizationId,
        parent_department_id: values.parentDepartmentId || null,
        head_id: values.headId || null,
        module_key: values.moduleKey,
        icon: values.icon || null,
        name: values.name.trim(),
        code: values.code.trim() || null,
        description: values.description.trim() || null,
        is_active: values.isActive,
      };

      return departmentSheetMode === 'edit' && departmentEditingId
        ? updateCrudRecord('core', 'departments', departmentEditingId, payload)
        : createCrudRecord('core', 'departments', payload);
    },
    onSuccess: async (department) => {
      const nextDepartmentId = getRecordId(department);
      setSelectedDepartmentId(nextDepartmentId);
      setDepartmentEditingId(nextDepartmentId);
      setDepartmentForm(
        buildDepartmentForm(
          department as DepartmentRecord,
          defaultOrganizationId,
          defaultDepartmentModuleKey,
        ),
      );
      setIsDepartmentSheetOpen(false);
      await departmentsQuery.refetch();
    },
  });

  const departmentDeleteMutation = useApiMutation<{ deleted?: boolean }, Error, string>({
    mutationKey: ['settings', 'departments', 'delete'],
    mutationFn: (departmentId) => {
      if (!canDeleteDepartmentById(departmentId)) {
        throw new Error('Недостаточно прав для удаления отдела.');
      }

      return deleteCrudRecord('core', 'departments', departmentId);
    },
    onSuccess: async () => {
      setSelectedDepartmentId('');
      setDepartmentEditingId('');
      setDepartmentSheetMode('create');
      setDeleteConfirmDepartmentId('');
      setDepartmentForm(
        buildDepartmentForm(null, defaultOrganizationId, defaultDepartmentModuleKey),
      );
      setIsDepartmentSheetOpen(false);
      await departmentsQuery.refetch();
    },
  });

  const onSubmit = form.handleSubmit((values) => {
    updateProfileMutation.mutate(values);
  });
  const canSaveDepartmentForm = canSaveDepartmentDraft(
    departmentForm,
    departmentSheetMode,
    departmentEditingId,
  );
  const isDepartmentFormReadOnly = !canSaveDepartmentForm;

  const handleDepartmentFieldChange = (key: keyof DepartmentFormState, value: string | boolean) => {
    if (isDepartmentFormReadOnly) {
      return;
    }

    setDepartmentForm((currentForm) => ({
      ...currentForm,
      [key]: value,
    }));
  };
  const handleDepartmentParentChange = (parentDepartmentId: string) => {
    if (isDepartmentFormReadOnly) {
      return;
    }

    const parentDepartment = parentDepartmentId
      ? (departmentRecordMap.get(parentDepartmentId) ?? null)
      : null;

    setDepartmentForm((currentForm) => ({
      ...currentForm,
      parentDepartmentId,
      organizationId:
        parentDepartment && typeof parentDepartment.organization_id === 'string'
          ? parentDepartment.organization_id
          : currentForm.organizationId,
      moduleKey:
        parentDepartment && typeof parentDepartment.module_key === 'string'
          ? parentDepartment.module_key
          : currentForm.moduleKey,
    }));
  };

  const handleSelectDepartment = (department: DepartmentRecord) => {
    const departmentId = getRecordId(department);

    if (!departmentId) {
      return;
    }

    setSelectedDepartmentId(departmentId);
    setDeleteConfirmDepartmentId('');
  };

  const closeDepartmentSheet = () => {
    setIsDepartmentSheetOpen(false);
    setDepartmentEditingId('');
    setDepartmentSheetMode('create');
    setDeleteConfirmDepartmentId('');
  };

  const handleCreateDepartment = () => {
    if (!canCreateRootDepartments) {
      return;
    }

    const nextModuleKey = availableRootDepartmentModuleKeys[0] ?? defaultDepartmentModuleKey;
    setDepartmentSheetMode('create');
    setDepartmentEditingId('');
    setDeleteConfirmDepartmentId('');
    setDepartmentForm(buildDepartmentForm(null, defaultOrganizationId, nextModuleKey));
    setIsDepartmentSheetOpen(true);
  };

  const handleCreateSubdepartment = (parentDepartment?: DepartmentRecord | null) => {
    if (parentDepartment && !canCreateSubdepartmentFor(parentDepartment)) {
      return;
    }
    if (!parentDepartment && !canCreateRootDepartments) {
      return;
    }

    const baseForm = buildDepartmentForm(null, defaultOrganizationId, defaultDepartmentModuleKey);
    const parentDepartmentId = parentDepartment ? getRecordId(parentDepartment) : '';
    const nextOrganizationId =
      typeof parentDepartment?.organization_id === 'string' && parentDepartment.organization_id
        ? parentDepartment.organization_id
        : baseForm.organizationId;
    const nextModuleKey =
      typeof parentDepartment?.module_key === 'string' && parentDepartment.module_key
        ? parentDepartment.module_key
        : baseForm.moduleKey;

    setDepartmentSheetMode('create');
    setDepartmentEditingId('');
    setDeleteConfirmDepartmentId('');
    setDepartmentForm({
      ...baseForm,
      organizationId: nextOrganizationId,
      moduleKey: nextModuleKey,
      parentDepartmentId,
    });
    setIsDepartmentSheetOpen(true);
  };

  const handleEditDepartment = (department: DepartmentRecord) => {
    if (!canManageDepartmentRecord(department)) {
      return;
    }

    const departmentId = getRecordId(department);
    setSelectedDepartmentId(departmentId);
    setDepartmentSheetMode('edit');
    setDepartmentEditingId(departmentId);
    setDeleteConfirmDepartmentId('');
    setDepartmentForm(
      buildDepartmentForm(department, defaultOrganizationId, defaultDepartmentModuleKey),
    );
    setIsDepartmentSheetOpen(true);
  };

  const commitDeleteDepartment = (departmentId: string) => {
    if (!departmentId || !canDeleteDepartmentById(departmentId)) {
      return;
    }

    setDeleteConfirmDepartmentId('');
    departmentDeleteMutation.mutate(departmentId);
  };

  const armDeleteDepartment = (departmentId: string) => {
    if (!departmentId) {
      return;
    }

    setSelectedDepartmentId(departmentId);
    setDeleteConfirmDepartmentId(departmentId);
  };

  const handleDeleteDepartmentClick = (
    event: ReactMouseEvent<HTMLButtonElement>,
    department: DepartmentRecord,
  ) => {
    event.preventDefault();
    event.stopPropagation();

    const departmentId = getRecordId(department);

    if (!departmentId) {
      return;
    }
    if (!canDeleteDepartmentRecord(department)) {
      return;
    }

    if (deleteConfirmDepartmentId === departmentId) {
      commitDeleteDepartment(departmentId);
      return;
    }

    armDeleteDepartment(departmentId);
  };

  const handleSaveDepartment = () => {
    if (!canSaveDepartmentForm) {
      return;
    }

    departmentSaveMutation.mutate(departmentForm);
  };

  const handleUseCurrentUserAsResponsible = () => {
    if (!currentSessionEmployee || isDepartmentFormReadOnly) {
      return;
    }

    handleDepartmentFieldChange('headId', getRecordId(currentSessionEmployee));
  };

  useEffect(() => {
    if (!selectedParentDepartment) {
      return;
    }

    const nextOrganizationId =
      typeof selectedParentDepartment.organization_id === 'string'
        ? selectedParentDepartment.organization_id
        : '';
    const nextModuleKey =
      typeof selectedParentDepartment.module_key === 'string'
        ? selectedParentDepartment.module_key
        : '';

    if (!nextOrganizationId || !nextModuleKey) {
      return;
    }

    setDepartmentForm((currentForm) => {
      if (
        currentForm.organizationId === nextOrganizationId &&
        currentForm.moduleKey === nextModuleKey
      ) {
        return currentForm;
      }

      return {
        ...currentForm,
        organizationId: nextOrganizationId,
        moduleKey: nextModuleKey,
      };
    });
  }, [selectedParentDepartment]);

  useEffect(() => {
    if (selectedParentDepartment || departmentForm.moduleKey) {
      return;
    }

    const nextModuleKey = selectableDepartmentModuleKeys[0] ?? '';
    if (!nextModuleKey) {
      return;
    }

    setDepartmentForm((currentForm) => ({
      ...currentForm,
      moduleKey: nextModuleKey,
    }));
  }, [departmentForm.moduleKey, selectableDepartmentModuleKeys, selectedParentDepartment]);

  const SelectedDepartmentIcon = getDepartmentIcon(departmentForm.icon, null);
  const isDepartmentEditMode = departmentSheetMode === 'edit' && departmentEditingId !== '';
  const profileInitials = getProfileInitials(
    profileQuery.data?.firstName,
    profileQuery.data?.lastName,
    profileQuery.data?.username,
  );
  const organizationLabel = currentOrganization
    ? getOrganizationLabel(currentOrganization)
    : t('common.empty');
  const currentSessionEmployee =
    authSession?.employeeId && typeof authSession.employeeId === 'string'
      ? (employeeMap.get(authSession.employeeId) ?? null)
      : null;
  const selectedResponsibleEmployee =
    departmentForm.headId && typeof departmentForm.headId === 'string'
      ? (employeeMap.get(departmentForm.headId) ?? null)
      : null;
  const selectedRootModuleOwner =
    !selectedParentDepartment && departmentForm.moduleKey
      ? (rootDepartmentByModuleKey.get(departmentForm.moduleKey) ?? null)
      : null;
  const selectedRootModuleOwnerId = selectedRootModuleOwner
    ? getRecordId(selectedRootModuleOwner)
    : '';
  const isSelectedRootModuleAvailable =
    Boolean(selectedParentDepartment) ||
    !departmentForm.moduleKey ||
    !selectedRootModuleOwnerId ||
    selectedRootModuleOwnerId === departmentEditingId;
  const isDepartmentModuleLockedToParent = Boolean(selectedParentDepartment?.module_key);
  const hasAvailableRootDepartmentModules = availableRootDepartmentModuleKeys.length > 0;
  const renderDepartmentActionButtons = (
    department: DepartmentRecord,
    options?: {
      includeAssignCurrentUser?: boolean;
    },
  ): ReactNode => {
    const actions: ReactNode[] = [];
    const departmentId = getRecordId(department);

    if (!departmentId) {
      return null;
    }

    if (
      options?.includeAssignCurrentUser &&
      currentSessionEmployee &&
      canManageDepartmentRecord(department)
    ) {
      actions.push(
        <Button
          key={`${departmentId}-assign-current-user`}
          type="button"
          size="sm"
          variant="outline"
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            setDepartmentForm({
              ...buildDepartmentForm(department, defaultOrganizationId, defaultDepartmentModuleKey),
              headId: getRecordId(currentSessionEmployee),
            });
            setDepartmentSheetMode('edit');
            setDepartmentEditingId(departmentId);
            setDeleteConfirmDepartmentId('');
            setIsDepartmentSheetOpen(true);
          }}
        >
          <UserRound className="h-4 w-4" />
          {t('settings.useCurrentUserAsResponsible', undefined, 'Назначить меня')}
        </Button>,
      );
    }

    if (canManageDepartmentRecord(department)) {
      actions.push(
        <Button
          key={`${departmentId}-edit`}
          type="button"
          size="sm"
          variant="outline"
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            handleEditDepartment(department);
          }}
          data-tour="settings-open-department-drawer-edit"
        >
          <Pencil className="h-4 w-4" />
          {t('common.edit')}
        </Button>,
      );
    }

    if (canCreateSubdepartmentFor(department)) {
      actions.push(
        <Button
          key={`${departmentId}-create-subdepartment`}
          type="button"
          size="sm"
          variant="outline"
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            handleCreateSubdepartment(department);
          }}
          data-tour="settings-open-department-drawer-create"
        >
          <Plus className="h-4 w-4" />
          {t('settings.createSubdepartment', undefined, 'Дочерний отдел')}
        </Button>,
      );
    }

    if (canDeleteDepartmentRecord(department)) {
      actions.push(
        <Button
          key={`${departmentId}-delete`}
          type="button"
          size="sm"
          variant={deleteConfirmDepartmentId === departmentId ? 'destructive' : 'outline'}
          className={
            deleteConfirmDepartmentId === departmentId
              ? undefined
              : 'border-destructive/25 bg-destructive/5 text-destructive hover:bg-destructive/10 hover:text-destructive'
          }
          onClick={(event) => handleDeleteDepartmentClick(event, department)}
          disabled={departmentDeleteMutation.isPending}
        >
          <Trash2 className="h-4 w-4" />
          {deleteConfirmDepartmentId === departmentId ? deleteConfirmHintLabel : t('common.delete')}
        </Button>,
      );
    }

    if (actions.length === 0) {
      return null;
    }

    return <div className="flex flex-wrap justify-end gap-2">{actions}</div>;
  };
  const deleteConfirmHintLabel = t(
    'settings.deleteDepartmentConfirm',
    undefined,
    'Нажмите еще раз для удаления',
  );
  const toggleDepartmentRoot = (rootId: string) => {
    setCollapsedDepartmentRootIds((current) =>
      current.includes(rootId)
        ? current.filter((collapsedRootId) => collapsedRootId !== rootId)
        : [...current, rootId],
    );
  };
  const getEmployeeMetaLine = (employee: EmployeeRecord | null | undefined): string => {
    if (!employee) {
      return t('settings.responsibleUserEmpty', undefined, 'Ответственный не назначен');
    }

    const metadata: string[] = [];
    const handle = getEmployeeUserHandle(employee);

    if (handle) {
      metadata.push(handle);
    }

    if (typeof employee.department_id === 'string' && employee.department_id) {
      const employeeDepartment = departmentRecordMap.get(employee.department_id) ?? null;

      if (employeeDepartment) {
        metadata.push(getDepartmentLabel(employeeDepartment));
      }
    }

    if (employee.is_active === false) {
      metadata.push(t('settings.employeeInactiveLabel', undefined, 'неактивный'));
    }

    return metadata.join(' · ') || t('common.empty');
  };
  const settingsTabs = useMemo(
    () =>
      [
        {
          key: 'account' as const,
          label: t('settings.profileTitle'),
          description: t(
            'settings.accountTabDescription',
            undefined,
            'Профиль, безопасность и рабочий контекст.',
          ),
        },
        canOpenDepartmentsTab
          ? {
              key: 'departments' as const,
              label: t('settings.departmentsSectionTitle', undefined, 'Управление отделами'),
              description: t(
                'settings.departmentsTabDescription',
                undefined,
                'Структура отделов, иерархия и управление подразделениями.',
              ),
            }
          : null,
      ].filter(
        (tab): tab is { key: SettingsTabKey; label: string; description: string } => tab !== null,
      ),
    [canOpenDepartmentsTab, t],
  );
  const activeSettingsTab = settingsTabs.find((tab) => tab.key === activeTab) ?? settingsTabs[0];
  const settingsHeroStats: Array<{
    key: string;
    label: string;
    value: string;
    icon: LucideIcon;
    caption?: string;
  }> = activeTab === 'departments'
    ? [
        {
          key: 'total',
          label: t('common.totalRecords', { count: departments.length }),
          value: String(departments.length),
          icon: Building2,
        },
        {
          key: 'active',
          label: t('common.active'),
          value: String(activeDepartmentCount),
          icon: ShieldCheck,
        },
        {
          key: 'roots',
          label: t('settings.rootDepartmentsLabel', { count: rootDepartmentCount }, `Головные: ${rootDepartmentCount}`),
          value: String(rootDepartmentCount),
          icon: Waypoints,
        },
      ]
    : [
        {
          key: 'username',
          label: t('settings.username'),
          value: profileQuery.data?.username ?? t('common.empty'),
          icon: UserRound,
        },
        {
          key: 'email',
          label: t('settings.email'),
          value: profileQuery.data?.email ?? t('common.empty'),
          icon: Mail,
        },
        {
          key: 'phone',
          label: t('settings.phone'),
          value: profileQuery.data?.phone ?? t('common.empty'),
          icon: Phone,
        },
      ];
  const activeDepartmentFilterCount =
    (departmentSearch.trim().length > 0 ? 1 : 0) +
    (departmentModuleFilter !== 'all' ? 1 : 0) +
    (departmentStatusFilter !== 'all' ? 1 : 0);
  const renderDepartmentListItem = (
    departmentNode: DepartmentTreeNode<DepartmentRecord>,
    options?: {
      indentLevel?: number;
    },
  ) => {
    const department = departmentNode.record;
    const departmentId = getRecordId(department);

    if (!departmentId) {
      return null;
    }

    const headEmployee =
      typeof department.head_id === 'string' ? (employeeMap.get(department.head_id) ?? null) : null;
    const DepartmentIcon = getDepartmentIcon(department.icon, null);
    const isSelected = departmentId === selectedDepartmentId;
    const isDepartmentDetailsTarget = departmentId === departmentDetailsTargetId;
    const indentLevel = options?.indentLevel ?? 0;

    return (
      <div
        className="flex flex-col gap-2 lg:flex-row lg:items-start"
        style={indentLevel > 0 ? { marginLeft: `${indentLevel * 0.95}rem` } : undefined}
      >
        <button
          type="button"
          data-tour={isDepartmentDetailsTarget ? 'settings-department-details' : undefined}
          className={cn(
            'group flex w-full items-start gap-3 rounded-2xl border px-3.5 py-3 text-left transition-[background-color,border-color,box-shadow,transform] lg:flex-1',
            isSelected
              ? 'bg-primary/8 border-primary/30 shadow-[0_18px_40px_-34px_rgba(234,88,12,0.24)]'
              : 'bg-background/98 hover:border-primary/18 border-border/65 shadow-[0_12px_30px_-28px_rgba(15,23,42,0.12)] hover:bg-background',
          )}
          onClick={() => handleSelectDepartment(department)}
        >
          <span className="bg-background/98 flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-border/70 text-primary shadow-[0_12px_28px_-24px_rgba(15,23,42,0.12)]">
            {DepartmentIcon ? (
              <DepartmentIcon className="h-4 w-4" />
            ) : (
              <Building2 className="h-4 w-4" />
            )}
          </span>
          <span className="min-w-0 flex-1">
            <span className="flex flex-wrap items-center gap-2">
              <span className="truncate text-sm font-semibold text-foreground">
                {getDepartmentLabel(department)}
              </span>
              {department.is_active === false ? (
                <span className="rounded-full border border-amber-200/70 bg-amber-50 px-2.5 py-0.5 text-[11px] font-semibold text-amber-800">
                  {t('settings.employeeInactiveLabel', undefined, 'неактивный')}
                </span>
              ) : null}
            </span>
            <span className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
              {typeof department.code === 'string' && department.code ? (
                <span>{department.code}</span>
              ) : null}
              <span>
                {headEmployee
                  ? getEmployeeLabel(headEmployee)
                  : t('settings.responsibleUserEmpty', undefined, 'Ответственный не назначен')}
              </span>
            </span>
          </span>
        </button>

        {renderDepartmentActionButtons(department)}
      </div>
    );
  };
  const renderDepartmentGroup = (group: {
    rootNode: DepartmentTreeNode<DepartmentRecord>;
    visibleDescendantNodes: DepartmentTreeNode<DepartmentRecord>[];
  }) => {
    const rootDepartment = group.rootNode.record;
    const rootDepartmentId = group.rootNode.id;
    const rootHeadEmployee =
      typeof rootDepartment.head_id === 'string'
        ? (employeeMap.get(rootDepartment.head_id) ?? null)
        : null;
    const RootIcon = getDepartmentIcon(rootDepartment.icon, null);
    const isSelectedRoot = selectedDepartmentId === rootDepartmentId;
    const isDepartmentDetailsTarget = rootDepartmentId === departmentDetailsTargetId;
    const isFocusedTree = selectedDepartmentNode?.rootId === rootDepartmentId;
    const rootModuleKey =
      typeof rootDepartment.module_key === 'string' ? rootDepartment.module_key : '';
    const rootModuleLabel = rootModuleKey
      ? resolveDepartmentModuleLabel(rootModuleKey)
      : t('common.empty');
    const isForcedOpen =
      selectedDepartmentNode?.rootId === rootDepartmentId || normalizedDepartmentSearch.length > 0;
    const isExpanded =
      group.visibleDescendantNodes.length > 0 &&
      (isForcedOpen || !collapsedDepartmentRootIdSet.has(rootDepartmentId));

    return (
      <div
        key={rootDepartmentId}
        className={cn(
          settingsGlassPanelClassName,
          'space-y-2.5 p-2.5',
          isFocusedTree ? 'border-primary/24 shadow-[0_22px_58px_-44px_rgba(234,88,12,0.18)]' : '',
        )}
      >
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start">
          <button
            type="button"
            data-tour={isDepartmentDetailsTarget ? 'settings-department-details' : undefined}
            className={cn(
              'rounded-2xl border px-4 py-3.5 text-left transition-[background-color,border-color,box-shadow] lg:flex-1',
              isSelectedRoot
                ? 'bg-primary/8 border-primary/30 shadow-[0_20px_44px_-34px_rgba(234,88,12,0.24)]'
                : 'bg-background/98 hover:border-primary/18 border-border/65 shadow-[0_14px_34px_-28px_rgba(15,23,42,0.12)] hover:bg-background',
            )}
            onClick={() => handleSelectDepartment(rootDepartment)}
          >
            <div className="flex items-start gap-3">
              <span className="bg-background/98 flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-border/70 text-primary shadow-[0_12px_28px_-24px_rgba(15,23,42,0.12)]">
                {RootIcon ? <RootIcon className="h-4 w-4" /> : <Building2 className="h-4 w-4" />}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="truncate text-base font-semibold text-foreground">
                    {getDepartmentLabel(rootDepartment)}
                  </p>
                  <span className={managementPillClassName}>{rootModuleLabel}</span>
                  {rootDepartment.is_active === false ? (
                    <span className="rounded-full border border-amber-200/70 bg-amber-50 px-2.5 py-0.5 text-[11px] font-semibold text-amber-800">
                      {t('settings.employeeInactiveLabel', undefined, 'неактивный')}
                    </span>
                  ) : null}
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {typeof rootDepartment.code === 'string' && rootDepartment.code
                    ? rootDepartment.code
                    : getEmployeeMetaLine(rootHeadEmployee)}
                </p>
              </div>
            </div>
          </button>

          <div className="flex flex-wrap justify-end gap-2">
            {renderDepartmentActionButtons(rootDepartment, { includeAssignCurrentUser: true })}
            {group.visibleDescendantNodes.length > 0 ? (
              <Button
                type="button"
                size="sm"
                variant="outline"
                aria-expanded={isExpanded}
                className="shrink-0"
                onClick={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  toggleDepartmentRoot(rootDepartmentId);
                }}
              >
                <ChevronDown
                  className={cn('h-3.5 w-3.5 transition-transform', isExpanded ? 'rotate-180' : '')}
                />
                {group.visibleDescendantNodes.length}
              </Button>
            ) : null}
          </div>
        </div>

        {isExpanded ? (
          <div className="space-y-2 border-l border-border/50 pl-2">
            {group.visibleDescendantNodes.map((departmentNode) => (
              <div key={departmentNode.id}>
                {renderDepartmentListItem(departmentNode, {
                  indentLevel: Math.max(0, departmentNode.depth - 1),
                })}
              </div>
            ))}
          </div>
        ) : null}
      </div>
    );
  };

  return (
    <div className="space-y-6" data-tour="settings-page">
      <Card className={settingsHeroCardClassName} data-tour="settings-tabs">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              'radial-gradient(circle at 88% 10%, hsl(var(--accent) / 0.14), transparent 24%), radial-gradient(circle at 12% 0%, hsl(var(--primary) / 0.12), transparent 18%)',
          }}
        />
        <CardContent className="relative space-y-5 p-4 sm:p-5">
          <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
            <div className="max-w-3xl space-y-4">
              <div className="space-y-2">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  {t('settings.title', undefined, 'Настройки')}
                </p>
                <h1 className="text-3xl font-semibold tracking-[-0.05em] text-foreground sm:text-4xl">
                  {activeSettingsTab?.label ?? t('settings.title', undefined, 'Настройки')}
                </h1>
              </div>

              <div className="flex flex-wrap gap-2">
                {settingsTabs.map((tab) => (
                  <Button
                    key={tab.key}
                    type="button"
                    variant={activeTab === tab.key ? 'default' : 'outline'}
                    data-tour={`settings-tab-${tab.key}`}
                    className={cn(
                      'rounded-full px-4',
                      activeTab === tab.key
                        ? 'shadow-[0_18px_42px_-28px_rgba(234,88,12,0.42)]'
                        : 'bg-background/88 border-border/60 shadow-[0_14px_32px_-28px_rgba(15,23,42,0.14)] backdrop-blur-xl supports-[backdrop-filter]:bg-background/80',
                    )}
                    onClick={() => setActiveTab(tab.key)}
                  >
                    {tab.label}
                  </Button>
                ))}
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:w-[25rem]">
              {settingsHeroStats.map((item) => (
                <SettingsOverviewTile
                  key={item.key}
                  label={item.label}
                  value={item.value}
                  caption={item.caption}
                  icon={item.icon}
                />
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {activeTab === 'account' ? (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(22rem,0.8fr)]">
          <Card className={settingsCardClassName} data-tour="settings-account-profile">
            <CardHeader className="gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="space-y-3">
                <div className={settingsIconTileClassName}>
                  <UserRound className="h-4 w-4 text-primary" />
                </div>
                <div className="space-y-2">
                  <CardTitle className="text-2xl tracking-[-0.04em]">
                    {t('settings.profileTitle')}
                  </CardTitle>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <div className={settingsAvatarTileClassName}>{profileInitials}</div>
                <Button
                  type="button"
                  onClick={() => setIsAccountSheetOpen(true)}
                  disabled={profileQuery.isLoading}
                  data-tour="settings-open-account-drawer"
                >
                  <Pencil className="h-4 w-4" />
                  {t('common.edit')}
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <Field
                  label={t('settings.username')}
                  value={profileQuery.data?.username ?? ''}
                  readOnly
                />
                <Field
                  label={t('settings.firstName')}
                  value={profileQuery.data?.firstName ?? ''}
                  readOnly
                />
                <Field
                  label={t('settings.lastName')}
                  value={profileQuery.data?.lastName ?? ''}
                  readOnly
                />
                <Field
                  label={t('settings.email')}
                  value={profileQuery.data?.email ?? ''}
                  readOnly
                />
                <Field
                  label={t('settings.phone')}
                  value={profileQuery.data?.phone ?? ''}
                  readOnly
                />
                <Field label={t('fields.organization_id')} value={organizationLabel} readOnly />
              </div>
            </CardContent>
          </Card>

          <div className="space-y-6">
            <Card className={settingsCardClassName} data-tour="settings-account-security">
              <CardHeader className="space-y-3">
                <div className={settingsIconTileClassName}>
                  <ShieldCheck className="h-4 w-4 text-primary" />
                </div>
                <div className="space-y-2">
                  <CardTitle className="text-2xl tracking-[-0.04em]">
                    {t('settings.securityTitle')}
                  </CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <Button
                  type="button"
                  className="w-full"
                  onClick={() => setIsAccountSheetOpen(true)}
                  data-tour="settings-open-account-drawer"
                >
                  <LockKeyhole className="h-4 w-4" />
                  {t('settings.securityTitle')}
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      ) : null}

      {activeTab === 'departments' ? (
        <div className="grid gap-6">
          <Card className={settingsCardClassName} data-tour="settings-departments-manager">
            <CardHeader className="space-y-4">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="space-y-3">
                  <div className={settingsIconTileClassName}>
                    <Building2 className="h-4 w-4 text-primary" />
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <CardTitle className="text-2xl tracking-[-0.04em]">
                      {t('settings.departmentsSectionTitle', undefined, 'Управление отделами')}
                    </CardTitle>
                    <span className={managementPillClassName}>
                      {filteredDepartmentCount}/{departments.length}
                    </span>
                  </div>
                </div>

                <div className="flex flex-wrap gap-2">
                  {canCreateRootDepartments && hasAvailableRootDepartmentModules ? (
                    <Button
                      type="button"
                      className="rounded-full"
                      onClick={handleCreateDepartment}
                      data-tour="settings-open-department-drawer-create"
                    >
                      <Plus className="h-4 w-4" />
                      {t('settings.createDepartmentTitle', undefined, 'Новый отдел')}
                    </Button>
                  ) : null}
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {departmentsQuery.error ? <ErrorNotice error={departmentsQuery.error} /> : null}
              {departmentDeleteMutation.error ? (
                <ErrorNotice error={departmentDeleteMutation.error} />
              ) : null}

              <div
                className="grid gap-3 xl:grid-cols-[minmax(0,1.4fr)_minmax(210px,0.82fr)_minmax(210px,0.82fr)_auto]"
                data-tour="settings-departments-filters"
              >
                <div className={cn(managementPanelClassName, 'p-4')}>
                  <label className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                    {t('settings.departmentSearchLabel', undefined, 'Поиск по отделам')}
                  </label>
                  <div className="relative mt-3">
                    <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                      value={departmentSearch}
                      onChange={(event) => setDepartmentSearch(event.target.value)}
                      className="pl-11 pr-11"
                      placeholder={t(
                        'settings.departmentSearchPlaceholder',
                        undefined,
                        'Название, код, описание, ответственный',
                      )}
                    />
                    {departmentSearch.trim().length > 0 ? (
                      <button
                        type="button"
                        className="absolute right-3 top-1/2 inline-flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground transition-colors hover:text-foreground"
                        onClick={() => setDepartmentSearch('')}
                        aria-label={t('common.clearSelection', undefined, 'Очистить выбор')}
                      >
                        <X className="h-4 w-4" />
                      </button>
                    ) : null}
                  </div>
                </div>

                <div className={cn(managementPanelClassName, 'p-4')}>
                  <label className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                    {t('settings.moduleFilterLabel', undefined, 'Фильтр по модулю')}
                  </label>
                  <CustomSelect
                    value={departmentModuleFilter}
                    onChange={setDepartmentModuleFilter}
                    options={departmentFilterModuleOptions}
                    className={`${managementInputClassName} mt-3`}
                    placeholder={t('settings.statusAll', undefined, 'Все')}
                    searchPlaceholder={t('common.search', undefined, 'Поиск')}
                    emptySearchLabel={t(
                      'crud.referenceNoOptions',
                      undefined,
                      'Подходящие варианты не найдены.',
                    )}
                  />
                </div>

                <div className={cn(managementPanelClassName, 'p-4')}>
                  <label className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                    {t('settings.statusFilterLabel', undefined, 'Фильтр по статусу')}
                  </label>
                  <CustomSelect
                    value={departmentStatusFilter}
                    onChange={(nextValue) =>
                      setDepartmentStatusFilter(nextValue as DepartmentStatusFilter)
                    }
                    options={departmentStatusOptions}
                    className={`${managementInputClassName} mt-3`}
                    searchable={false}
                  />
                </div>

                <div className="flex items-end">
                  <Button
                    type="button"
                    variant="outline"
                    className="h-11 rounded-full px-5"
                    disabled={activeDepartmentFilterCount === 0}
                    onClick={() => {
                      setDepartmentSearch('');
                      setDepartmentModuleFilter('all');
                      setDepartmentStatusFilter('all');
                    }}
                  >
                    {t('common.reset')}
                  </Button>
                </div>
              </div>

              {departmentsQuery.isLoading ? (
                <div className="bg-background/98 rounded-[24px] border border-dashed border-border/70 px-6 py-10 text-center shadow-[0_18px_48px_-36px_rgba(15,23,42,0.12)]">
                  <p className="text-sm text-muted-foreground">{t('common.loadingLabel')}</p>
                </div>
              ) : departments.length === 0 ? (
                <div className="bg-background/98 rounded-[24px] border border-dashed border-border/70 px-6 py-10 text-center shadow-[0_18px_48px_-36px_rgba(15,23,42,0.12)]">
                  <p className="text-lg font-semibold text-foreground">
                    {t('settings.emptyDepartmentsTitle', undefined, 'Пока нет отделов')}
                  </p>
                </div>
              ) : filteredDepartmentNodes.length === 0 ? (
                <div className="bg-background/98 rounded-[24px] border border-dashed border-border/70 px-6 py-10 text-center shadow-[0_18px_48px_-36px_rgba(15,23,42,0.12)]">
                  <p className="text-lg font-semibold text-foreground">
                    {t('settings.noDepartmentsMatchTitle', undefined, 'Ничего не найдено')}
                  </p>
                </div>
              ) : (
                <div className="grid gap-3" data-tour="settings-departments-tree">
                  {filteredDepartmentGroups.map((group) => renderDepartmentGroup(group))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      ) : null}

      <Sheet open={isAccountSheetOpen} onOpenChange={setIsAccountSheetOpen}>
        <CrudDrawer
          dataTour="settings-account-drawer"
          size="wide"
          title={t('settings.profileTitle')}
          description={t('settings.description')}
          bodyClassName="flex-1 space-y-6 overflow-y-auto bg-background px-6 py-5 xl:px-8"
          formProps={{ onSubmit }}
          footer={
            <CrudDrawerFooter
              closeLabel={t('common.close')}
              closeDisabled={updateProfileMutation.isPending}
              onClose={() => setIsAccountSheetOpen(false)}
            >
              <Button
                type="submit"
                className={drawerPrimaryButtonClassName}
                disabled={profileQuery.isLoading || updateProfileMutation.isPending}
              >
                <Save className="h-4 w-4" />
                {t('common.save')}
              </Button>
            </CrudDrawerFooter>
          }
        >
          <div className="grid gap-6 xl:grid-cols-2">
            <Card className={settingsCardClassName}>
              <CardHeader>
                <div className={settingsIconTileClassName}>
                  <UserRound className="h-4 w-4 text-primary" />
                </div>
                <CardTitle className="text-xl tracking-[-0.04em]">
                  {t('settings.profileTitle')}
                </CardTitle>
                <CardDescription>{t('settings.profileDescription')}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <Field
                  label={t('settings.username')}
                  value={profileQuery.data?.username ?? ''}
                  readOnly
                />
                <ControlledField
                  label={t('settings.firstName')}
                  error={form.formState.errors.firstName?.message}
                >
                  <Input {...form.register('firstName')} />
                </ControlledField>
                <ControlledField
                  label={t('settings.lastName')}
                  error={form.formState.errors.lastName?.message}
                >
                  <Input {...form.register('lastName')} />
                </ControlledField>
                <ControlledField
                  label={t('settings.email')}
                  error={form.formState.errors.email?.message}
                >
                  <Input {...form.register('email')} type="email" />
                </ControlledField>
                <ControlledField
                  label={t('settings.phone')}
                  error={form.formState.errors.phone?.message}
                >
                  <Input {...form.register('phone')} />
                </ControlledField>
              </CardContent>
            </Card>

            <Card className={settingsCardClassName}>
              <CardHeader>
                <div className={settingsIconTileClassName}>
                  <LockKeyhole className="h-4 w-4 text-primary" />
                </div>
                <CardTitle className="text-xl tracking-[-0.04em]">
                  {t('settings.securityTitle')}
                </CardTitle>
                <CardDescription>{t('settings.securityDescription')}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <ControlledField
                  label={t('settings.currentPassword')}
                  error={form.formState.errors.currentPassword?.message}
                >
                  <Input {...form.register('currentPassword')} type="password" />
                </ControlledField>
                <ControlledField
                  label={t('settings.newPassword')}
                  error={form.formState.errors.newPassword?.message}
                >
                  <Input {...form.register('newPassword')} type="password" />
                </ControlledField>
                <ControlledField
                  label={t('settings.confirmNewPassword')}
                  error={form.formState.errors.confirmNewPassword?.message}
                >
                  <Input {...form.register('confirmNewPassword')} type="password" />
                </ControlledField>
              </CardContent>
            </Card>
          </div>

          <div className="space-y-2">
            {profileQuery.error ? <ErrorNotice error={profileQuery.error} /> : null}
            {updateProfileMutation.error ? (
              <ErrorNotice error={updateProfileMutation.error} />
            ) : null}
            {updateProfileMutation.isSuccess ? (
              <p className="text-sm text-primary">{t('settings.success')}</p>
            ) : null}
          </div>
        </CrudDrawer>
      </Sheet>

      <Sheet
        open={isDepartmentSheetOpen}
        onOpenChange={(open) => {
          if (!open) {
            closeDepartmentSheet();
            return;
          }
          setIsDepartmentSheetOpen(true);
        }}
      >
        <CrudDrawer
          dataTour="settings-department-drawer"
          size="xwide"
          title={
            isDepartmentEditMode
              ? t('settings.editDepartmentTitle', undefined, 'Редактирование отдела')
              : t('settings.createDepartmentTitle', undefined, 'Новый отдел')
          }
          description={t(
            'settings.departmentFormDescription',
            undefined,
            'Заполните поля департамента и сохраните изменения.',
          )}
          bodyClassName="flex-1 space-y-6 overflow-y-auto bg-background px-6 py-5 xl:px-8"
          footer={
            <CrudDrawerFooter
              closeLabel={t('common.close')}
              closeDisabled={departmentSaveMutation.isPending || departmentDeleteMutation.isPending}
              onClose={closeDepartmentSheet}
            >
              <Button
                type="button"
                className={drawerPrimaryButtonClassName}
                onClick={handleSaveDepartment}
                disabled={
                  !canSaveDepartmentForm ||
                  !departmentForm.organizationId ||
                  !departmentForm.moduleKey ||
                  !departmentForm.name.trim() ||
                  !isSelectedRootModuleAvailable ||
                  departmentSaveMutation.isPending
                }
              >
                <Save className="h-4 w-4" />
                {isDepartmentEditMode ? t('common.save') : t('common.create')}
              </Button>
              {departmentEditingRecord && canDeleteDepartmentRecord(departmentEditingRecord) ? (
                <Button
                  type="button"
                  variant={
                    deleteConfirmDepartmentId === getRecordId(departmentEditingRecord)
                      ? 'destructive'
                      : 'outline'
                  }
                  className={cn(
                    deleteConfirmDepartmentId === getRecordId(departmentEditingRecord)
                      ? undefined
                      : 'border-destructive/25 bg-destructive/5 text-destructive hover:bg-destructive/10 hover:text-destructive',
                  )}
                  onClick={(event) => handleDeleteDepartmentClick(event, departmentEditingRecord)}
                  disabled={departmentDeleteMutation.isPending || departmentSaveMutation.isPending}
                >
                  <Trash2 className="h-4 w-4" />
                  {deleteConfirmDepartmentId === getRecordId(departmentEditingRecord)
                    ? deleteConfirmHintLabel
                    : t('common.delete')}
                </Button>
              ) : null}
            </CrudDrawerFooter>
          }
        >
          {departmentSaveMutation.error ? (
            <ErrorNotice error={departmentSaveMutation.error} />
          ) : null}
          <div
            className={cn(
              settingsGlassPanelClassName,
              'grid gap-4 rounded-2xl p-5 md:grid-cols-2 xl:gap-5',
            )}
            data-tour="settings-department-form-main"
          >
            <div className={cn(settingsGlassPanelSoftClassName, 'px-4 py-3 md:col-span-2')}>
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                {t('fields.organization_id')}
              </p>
              <p className="mt-2 text-sm font-semibold text-foreground">{organizationLabel}</p>
            </div>

            <ControlledField label={t('fields.module_key')}>
              <CustomSelect
                value={departmentForm.moduleKey}
                onChange={(nextValue) => handleDepartmentFieldChange('moduleKey', nextValue)}
                options={departmentModuleSelectOptions}
                className={managementInputClassName}
                disabled={isDepartmentFormReadOnly || isDepartmentModuleLockedToParent}
                placeholder={t('common.chooseValue')}
                searchPlaceholder={t('common.search', undefined, 'Поиск')}
                emptySearchLabel={t(
                  'crud.referenceNoOptions',
                  undefined,
                  'Подходящие варианты не найдены.',
                )}
              />
            </ControlledField>

            <div className="space-y-2 md:col-span-2" data-tour="settings-department-form-icon">
              <ControlledField label={t('fields.icon')}>
                <div className="space-y-3">
                  <div
                    className={cn(
                      settingsGlassPanelSoftClassName,
                      'grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-3',
                    )}
                  >
                    {departmentIconOptions.map((option) => (
                      <button
                        key={option.key}
                        type="button"
                        className={cn(
                          'flex items-center gap-3 rounded-2xl border px-4 py-3 text-left transition-[background-color,border-color,box-shadow,transform]',
                          departmentForm.icon === option.key
                            ? 'bg-primary/8 border-primary/30 text-foreground shadow-[0_18px_40px_-34px_rgba(234,88,12,0.24)]'
                            : 'bg-background/98 hover:border-primary/18 border-border/65 text-muted-foreground shadow-[0_12px_30px_-28px_rgba(15,23,42,0.12)] hover:bg-background',
                        )}
                        onClick={() =>
                          handleDepartmentFieldChange(
                            'icon',
                            departmentForm.icon === option.key ? '' : option.key,
                          )
                        }
                        disabled={isDepartmentFormReadOnly}
                      >
                        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-border/70 bg-background text-foreground shadow-[0_12px_28px_-24px_rgba(15,23,42,0.12)]">
                          <option.icon className="h-4 w-4" />
                        </span>
                        <span className="min-w-0">
                          <span className="block truncate text-sm font-semibold text-foreground">
                            {getDepartmentIconLabel(option.key, t)}
                          </span>
                          <span className="block text-xs text-muted-foreground">{option.key}</span>
                        </span>
                      </button>
                    ))}
                  </div>
                  <div className="bg-background/88 flex items-center gap-3 rounded-2xl border border-border/60 px-4 py-3 text-sm text-muted-foreground shadow-[0_14px_34px_-28px_rgba(15,23,42,0.12)] backdrop-blur-xl supports-[backdrop-filter]:bg-background/80">
                    <div className="supports-[backdrop-filter]:bg-background/82 flex h-9 w-9 items-center justify-center rounded-xl border border-border/60 bg-background/90 text-foreground shadow-[0_12px_28px_-22px_rgba(15,23,42,0.12)] backdrop-blur-xl">
                      {SelectedDepartmentIcon ? (
                        <SelectedDepartmentIcon className="h-4 w-4" />
                      ) : (
                        <Building2 className="h-4 w-4" />
                      )}
                    </div>
                    <span>
                      {departmentForm.icon
                        ? getDepartmentIconLabel(departmentForm.icon, t)
                        : t('common.chooseValue')}
                    </span>
                    {departmentForm.icon ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        className="ml-auto"
                        onClick={() => handleDepartmentFieldChange('icon', '')}
                        disabled={isDepartmentFormReadOnly}
                      >
                        {t('common.reset')}
                      </Button>
                    ) : null}
                  </div>
                </div>
              </ControlledField>
            </div>

            <div
              className="space-y-2 md:col-span-2"
              data-tour="settings-department-form-responsible"
            >
              <ControlledField
                label={t('settings.responsibleUserTitle', undefined, 'Ответственный пользователь')}
              >
                <div className={cn(settingsGlassPanelSoftClassName, 'space-y-4 p-4')}>
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div className="space-y-1">
                      <p className="text-sm font-semibold text-foreground">
                        {selectedResponsibleEmployee
                          ? getEmployeeLabel(selectedResponsibleEmployee)
                          : t(
                              'settings.responsibleUserEmpty',
                              undefined,
                              'Ответственный не назначен',
                            )}
                      </p>
                      <p className="text-sm leading-6 text-muted-foreground">
                        {selectedResponsibleEmployee
                          ? getEmployeeMetaLine(selectedResponsibleEmployee)
                          : t(
                              'settings.responsibleUserDescription',
                              undefined,
                              'Назначьте сотрудника, который отвечает за работу этого отдела и является основным контактным лицом.',
                            )}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {currentSessionEmployee ? (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={handleUseCurrentUserAsResponsible}
                          disabled={isDepartmentFormReadOnly}
                        >
                          <UserRound className="h-3.5 w-3.5" />
                          {t('settings.useCurrentUserAsResponsible', undefined, 'Назначить меня')}
                        </Button>
                      ) : null}
                      {departmentForm.headId ? (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => handleDepartmentFieldChange('headId', '')}
                          disabled={isDepartmentFormReadOnly}
                        >
                          {t('settings.clearResponsibleUser', undefined, 'Очистить')}
                        </Button>
                      ) : null}
                    </div>
                  </div>
                  <CustomSelect
                    value={departmentForm.headId}
                    onChange={(nextValue) => handleDepartmentFieldChange('headId', nextValue)}
                    options={assignableEmployeeOptions}
                    className={managementInputClassName}
                    disabled={isDepartmentFormReadOnly}
                    placeholder={t(
                      'settings.responsibleUserPlaceholder',
                      undefined,
                      'Выберите пользователя',
                    )}
                    searchPlaceholder={t('common.search', undefined, 'Поиск')}
                    emptySearchLabel={t(
                      'crud.referenceNoOptions',
                      undefined,
                      'Подходящие варианты не найдены.',
                    )}
                  />
                </div>
              </ControlledField>
            </div>

            <ControlledField label={t('fields.name')}>
              <Input
                value={departmentForm.name}
                onChange={(event) => handleDepartmentFieldChange('name', event.target.value)}
                disabled={isDepartmentFormReadOnly}
              />
            </ControlledField>

            <ControlledField label={t('fields.code')}>
              <Input
                value={departmentForm.code}
                onChange={(event) => handleDepartmentFieldChange('code', event.target.value)}
                disabled={isDepartmentFormReadOnly}
              />
            </ControlledField>

            <ControlledField label={t('fields.parent_department_id')}>
              <CustomSelect
                value={departmentForm.parentDepartmentId}
                onChange={handleDepartmentParentChange}
                options={parentDepartmentOptions}
                className={managementInputClassName}
                disabled={isDepartmentFormReadOnly}
                placeholder={t('common.chooseValue')}
                searchPlaceholder={t('common.search', undefined, 'Поиск')}
                emptySearchLabel={t(
                  'crud.referenceNoOptions',
                  undefined,
                  'Подходящие варианты не найдены.',
                )}
              />
            </ControlledField>

            <ControlledField label={t('fields.description')} className="md:col-span-2">
              <textarea
                value={departmentForm.description}
                onChange={(event) => handleDepartmentFieldChange('description', event.target.value)}
                disabled={isDepartmentFormReadOnly}
                className="supports-[backdrop-filter]:bg-background/82 min-h-[120px] w-full rounded-2xl border border-border/60 bg-background/90 px-3 py-3 text-sm text-foreground shadow-[0_16px_38px_-30px_rgba(15,23,42,0.16)] backdrop-blur-xl transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              />
            </ControlledField>

            <ControlledField label={t('fields.is_active')}>
              <label className="bg-background/88 flex items-center gap-3 rounded-2xl border border-border/60 px-4 py-3 shadow-[0_14px_34px_-28px_rgba(15,23,42,0.12)] backdrop-blur-xl supports-[backdrop-filter]:bg-background/80">
                <input
                  type="checkbox"
                  checked={departmentForm.isActive}
                  onChange={(event) =>
                    handleDepartmentFieldChange('isActive', event.target.checked)
                  }
                  disabled={isDepartmentFormReadOnly}
                  className="h-4 w-4 rounded border-border text-primary"
                />
                <span className="text-sm text-foreground">
                  {departmentForm.isActive ? t('common.yes') : t('common.no')}
                </span>
              </label>
            </ControlledField>
          </div>

          {!isSelectedRootModuleAvailable && selectedRootModuleOwner ? (
            <p className="text-sm text-destructive">
              {t(
                'settings.rootDepartmentConflict',
                undefined,
                `Для модуля уже существует корневой отдел: ${getDepartmentLabel(selectedRootModuleOwner)}.`,
              )}
            </p>
          ) : null}
        </CrudDrawer>
      </Sheet>
    </div>
  );
}

function SettingsOverviewTile({
  label,
  value,
  caption,
  icon: Icon,
}: {
  label: string;
  value: string;
  caption?: string;
  icon: LucideIcon;
}) {
  return (
    <div className={cn(settingsGlassPanelSoftClassName, 'p-4')}>
      <div className="flex items-start justify-between gap-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
          {label}
        </p>
        <span className="inline-flex h-9 w-9 items-center justify-center rounded-2xl border border-border/70 bg-background text-primary shadow-[0_12px_28px_-24px_rgba(15,23,42,0.12)]">
          <Icon className="h-4 w-4" />
        </span>
      </div>
      <p className="mt-3 line-clamp-2 text-lg font-semibold leading-6 tracking-[-0.03em] text-foreground">
        {value}
      </p>
      {caption ? <p className="mt-2 text-xs leading-5 text-muted-foreground">{caption}</p> : null}
    </div>
  );
}

function ControlledField({
  children,
  label,
  error,
  className,
}: {
  children: ReactNode;
  label: string;
  error?: string;
  className?: string;
}) {
  return (
    <div className={cn('space-y-2', className)}>
      <label className="text-sm font-medium text-foreground">{label}</label>
      {children}
      {error ? <p className="text-xs text-destructive">{error}</p> : null}
    </div>
  );
}

function Field({
  label,
  value,
  readOnly = false,
}: {
  label: string;
  value: string;
  readOnly?: boolean;
}) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-foreground">{label}</label>
      <Input value={value} readOnly={readOnly} />
    </div>
  );
}
