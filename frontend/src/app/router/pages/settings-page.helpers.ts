import type { CrudRecord } from '@/shared/api/backend-crud';

export type OrganizationRecord = CrudRecord & {
  id?: string;
  name?: string;
};

export type EmployeeRecord = CrudRecord & {
  id?: string;
  first_name?: string;
  last_name?: string;
  organization_id?: string;
  organization_key?: string;
  department_id?: string | null;
  email?: string;
  phone?: string | null;
  is_active?: boolean;
};

export type DepartmentRecord = CrudRecord & {
  id?: string;
  organization_id?: string;
  parent_department_id?: string | null;
  head_id?: string | null;
  module_key?: string;
  icon?: string | null;
  name?: string;
  code?: string;
  description?: string | null;
  is_active?: boolean;
};

export type DepartmentModuleRecord = CrudRecord & {
  id?: string;
  key?: string;
  name?: string;
  description?: string | null;
  icon?: string | null;
  sort_order?: number | null;
  is_department_assignable?: boolean;
  is_active?: boolean;
};

export type DepartmentFormState = {
  organizationId: string;
  parentDepartmentId: string;
  headId: string;
  moduleKey: string;
  icon: string;
  name: string;
  code: string;
  description: string;
  isActive: boolean;
};

export type DepartmentStatusFilter = 'all' | 'active' | 'inactive';
export type SettingsTabKey = 'account';
export type DepartmentSheetMode = 'create' | 'edit';
export type DepartmentRbacScope = {
  canWriteAllDepartments: boolean;
  canCreateRootDepartments: boolean;
  canDeleteAnyDepartment: boolean;
  managedDepartmentIds: ReadonlySet<string>;
  headedDepartmentIds: ReadonlySet<string>;
};

export const defaultDepartmentForm: DepartmentFormState = {
  organizationId: '',
  parentDepartmentId: '',
  headId: '',
  moduleKey: '',
  icon: '',
  name: '',
  code: '',
  description: '',
  isActive: true,
};

export const settingsHeroCardClassName =
  'relative overflow-hidden rounded-[32px] border border-border/70 bg-card shadow-[0_32px_90px_-58px_rgba(15,23,42,0.18)]';
export const settingsCardClassName =
  'rounded-[28px] border border-border/70 bg-card shadow-[0_24px_72px_-52px_rgba(15,23,42,0.16)]';
export const settingsGlassPanelClassName =
  'rounded-[24px] border border-border/70 bg-card shadow-[0_20px_56px_-40px_rgba(15,23,42,0.14)]';
export const settingsGlassPanelSoftClassName =
  'rounded-2xl border border-border/70 bg-background shadow-[0_16px_42px_-34px_rgba(15,23,42,0.1)]';
export const settingsIconTileClassName =
  'inline-flex h-10 w-10 items-center justify-center rounded-2xl border border-border/70 bg-background shadow-[0_14px_34px_-28px_rgba(15,23,42,0.1)]';
export const settingsAvatarTileClassName =
  'flex h-16 w-16 items-center justify-center rounded-[22px] border border-border/70 bg-background text-lg font-semibold text-foreground shadow-[0_18px_44px_-34px_rgba(15,23,42,0.12)]';
export const managementInputClassName =
  'flex h-11 w-full rounded-2xl border border-border/70 bg-background px-4 py-3 text-sm text-foreground shadow-[0_16px_38px_-30px_rgba(15,23,42,0.1)] ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2';
export const managementPanelClassName = settingsGlassPanelClassName;
export const managementPillClassName =
  'rounded-full border border-border/70 bg-background px-3 py-1.5 text-xs font-medium text-muted-foreground shadow-[0_14px_32px_-28px_rgba(15,23,42,0.08)]';
export const drawerPrimaryButtonClassName = 'min-w-[148px]';

export const getRecordId = (record: CrudRecord | null | undefined): string => {
  const candidate = record?.id;

  if (typeof candidate === 'string' || typeof candidate === 'number') {
    return String(candidate);
  }

  return '';
};

export const getOrganizationLabel = (organization: OrganizationRecord): string => {
  if (typeof organization.name === 'string' && organization.name) {
    return organization.name;
  }

  return getRecordId(organization);
};

export const getEmployeeLabel = (employee: EmployeeRecord): string => {
  const parts = [employee.first_name, employee.last_name]
    .filter((part): part is string => typeof part === 'string' && part.trim().length > 0)
    .map((part) => part.trim());

  if (parts.length > 0) {
    return parts.join(' ');
  }

  return getRecordId(employee);
};

export const getEmployeeUserHandle = (employee: EmployeeRecord): string => {
  if (
    typeof employee.organization_key === 'string' &&
    employee.organization_key.trim().length > 0
  ) {
    return employee.organization_key.trim();
  }

  if (typeof employee.email === 'string' && employee.email.trim().length > 0) {
    return employee.email.trim();
  }

  return '';
};

export const getEmployeeOptionLabel = (employee: EmployeeRecord): string => {
  const name = getEmployeeLabel(employee);
  const handle = getEmployeeUserHandle(employee);

  if (handle && handle !== name) {
    return `${name} · ${handle}`;
  }

  return name;
};

export const getDepartmentLabel = (department: DepartmentRecord): string => {
  if (typeof department.name === 'string' && department.name) {
    return department.name;
  }

  if (typeof department.code === 'string' && department.code) {
    return department.code;
  }

  return getRecordId(department);
};

export const getDepartmentModuleKey = (
  departmentModule: DepartmentModuleRecord | null | undefined,
): string => {
  if (typeof departmentModule?.key === 'string' && departmentModule.key) {
    return departmentModule.key;
  }

  return getRecordId(departmentModule);
};

export const getDepartmentModuleLabel = (
  departmentModule: DepartmentModuleRecord | null | undefined,
): string => {
  if (typeof departmentModule?.name === 'string' && departmentModule.name) {
    return departmentModule.name;
  }

  const moduleKey = getDepartmentModuleKey(departmentModule);
  if (moduleKey) {
    return moduleKey;
  }

  return '';
};

export const getDepartmentIconLabel = (
  iconKey: string,
  t: (key: string, params?: Record<string, string | number>, fallback?: string) => string,
): string => {
  if (!iconKey) {
    return t('common.chooseValue');
  }

  return t(`departmentIcons.${iconKey}`, undefined, iconKey);
};

export const getProfileInitials = (
  firstName: string | null | undefined,
  lastName: string | null | undefined,
  username: string | null | undefined,
): string => {
  const initials = [firstName, lastName]
    .filter((part): part is string => typeof part === 'string' && part.trim().length > 0)
    .map((part) => part.trim().charAt(0).toUpperCase())
    .join('')
    .slice(0, 2);

  if (initials) {
    return initials;
  }

  if (typeof username === 'string' && username.trim()) {
    return username.trim().slice(0, 2).toUpperCase();
  }

  return 'U';
};

export const buildDepartmentForm = (
  department: DepartmentRecord | null,
  fallbackOrganizationId: string,
  fallbackModuleKey: string,
): DepartmentFormState => {
  if (!department) {
    return {
      ...defaultDepartmentForm,
      organizationId: fallbackOrganizationId,
      moduleKey: fallbackModuleKey,
    };
  }

  return {
    organizationId:
      typeof department.organization_id === 'string'
        ? department.organization_id
        : fallbackOrganizationId,
    parentDepartmentId:
      typeof department.parent_department_id === 'string' ? department.parent_department_id : '',
    headId: typeof department.head_id === 'string' ? department.head_id : '',
    moduleKey:
      typeof department.module_key === 'string' && department.module_key
        ? department.module_key
        : fallbackModuleKey,
    icon: typeof department.icon === 'string' ? department.icon : '',
    name: typeof department.name === 'string' ? department.name : '',
    code: typeof department.code === 'string' ? department.code : '',
    description: typeof department.description === 'string' ? department.description : '',
    isActive: typeof department.is_active === 'boolean' ? department.is_active : true,
  };
};

export const canManageDepartmentRecordAccess = (
  departmentId: string,
  scope: Pick<DepartmentRbacScope, 'canWriteAllDepartments' | 'managedDepartmentIds'>,
): boolean => {
  if (!departmentId) {
    return false;
  }

  return scope.canWriteAllDepartments || scope.managedDepartmentIds.has(departmentId);
};

export const canCreateSubdepartmentForAccess = (
  departmentId: string,
  scope: Pick<DepartmentRbacScope, 'canCreateRootDepartments' | 'managedDepartmentIds'>,
): boolean => {
  if (!departmentId) {
    return false;
  }

  return scope.canCreateRootDepartments || scope.managedDepartmentIds.has(departmentId);
};

export const canDeleteDepartmentRecordAccess = (
  departmentId: string,
  scope: Pick<
    DepartmentRbacScope,
    'canDeleteAnyDepartment' | 'managedDepartmentIds' | 'headedDepartmentIds'
  >,
): boolean => {
  if (!departmentId) {
    return false;
  }

  if (scope.canDeleteAnyDepartment) {
    return true;
  }

  return (
    scope.managedDepartmentIds.has(departmentId) && !scope.headedDepartmentIds.has(departmentId)
  );
};

export const canSaveDepartmentDraftAccess = ({
  departmentForm,
  departmentSheetMode,
  departmentEditingId,
  departmentRecordMap,
  scope,
}: {
  departmentForm: DepartmentFormState;
  departmentSheetMode: DepartmentSheetMode;
  departmentEditingId: string;
  departmentRecordMap: ReadonlyMap<string, DepartmentRecord>;
  scope: DepartmentRbacScope;
}): boolean => {
  if (departmentSheetMode === 'edit') {
    if (!departmentEditingId || !departmentRecordMap.has(departmentEditingId)) {
      return false;
    }

    return canManageDepartmentRecordAccess(departmentEditingId, scope);
  }

  if (departmentForm.parentDepartmentId) {
    if (!departmentRecordMap.has(departmentForm.parentDepartmentId)) {
      return false;
    }

    return canCreateSubdepartmentForAccess(departmentForm.parentDepartmentId, scope);
  }

  return scope.canCreateRootDepartments;
};

export const canDeleteDepartmentByIdAccess = (
  departmentId: string,
  departmentRecordMap: ReadonlyMap<string, DepartmentRecord>,
  scope: DepartmentRbacScope,
): boolean => {
  if (!departmentId || !departmentRecordMap.has(departmentId)) {
    return false;
  }

  return canDeleteDepartmentRecordAccess(departmentId, scope);
};
