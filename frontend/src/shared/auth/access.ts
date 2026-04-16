import {
  getBackendModuleMap,
  getBackendModules,
  getSharedPermissionPrefixes,
  type BackendModuleConfig,
  type BackendResourceConfig,
} from '@/shared/config/backend-modules';

type CrudAccessAction = 'read' | 'create' | 'write' | 'delete';

const PRIVILEGED_ACCESS_ROLES = new Set(['admin', 'super_admin', 'manager']);
const ROLE_MANAGEMENT_READ_PERMISSIONS = new Set(['role.read']);
const ROLE_MANAGEMENT_CREATE_PERMISSIONS = new Set(['role.create']);
const ROLE_MANAGEMENT_WRITE_PERMISSIONS = new Set(['role.write']);
const ROLE_MANAGEMENT_DELETE_PERMISSIONS = new Set(['role.delete']);
const EMPLOYEE_READ_PERMISSIONS = new Set(['employee.read']);
const EMPLOYEE_WRITE_PERMISSIONS = new Set(['employee.write']);
const AUDIT_READ_PERMISSIONS = new Set(['audit.read']);
const DEPARTMENT_READ_PERMISSIONS = new Set([
  'department.read',
  'department.create',
  'department.write',
  'department.delete',
]);
const DASHBOARD_OVERVIEW_PERMISSIONS = new Set(['dashboard.read']);

const normalizeValues = (values: readonly string[]): string[] => {
  return values.map((value) => value.trim().toLowerCase()).filter((value) => value.length > 0);
};

const hasAnyMatchingValue = (
  values: readonly string[],
  allowedValues: ReadonlySet<string>,
): boolean => {
  return normalizeValues(values).some((value) => allowedValues.has(value));
};

const hasAllValues = (values: readonly string[], requiredValues: readonly string[]): boolean => {
  const normalizedValueSet = new Set(normalizeValues(values));
  return requiredValues.every((value) => normalizedValueSet.has(value.trim().toLowerCase()));
};

export const buildCrudPermission = (permissionPrefix: string, action: CrudAccessAction): string =>
  `${permissionPrefix.trim().toLowerCase()}.${action}`;

export const hasPrivilegedAccessRole = (roles: readonly string[]): boolean => {
  return hasAnyMatchingValue(roles, PRIVILEGED_ACCESS_ROLES);
};

export const hasPermissionCode = (permissions: readonly string[], permission: string): boolean => {
  return normalizeValues(permissions).includes(permission.trim().toLowerCase());
};

export const hasAnyPermissionCode = (
  permissions: readonly string[],
  requiredPermissions: readonly string[],
): boolean => {
  if (requiredPermissions.length === 0) {
    return false;
  }

  const normalizedPermissionSet = new Set(normalizeValues(permissions));
  return requiredPermissions.some((permission) =>
    normalizedPermissionSet.has(permission.trim().toLowerCase()),
  );
};

export const hasAllPermissionCodes = (
  permissions: readonly string[],
  requiredPermissions: readonly string[],
): boolean => {
  return hasAllValues(permissions, requiredPermissions);
};

const getModuleConfig = (moduleKey: string): BackendModuleConfig | undefined => {
  const normalizedModuleKey = moduleKey.trim().toLowerCase();
  if (!normalizedModuleKey) {
    return undefined;
  }

  return getBackendModuleMap()[normalizedModuleKey];
};

const hasImplicitDepartmentReadAccess = (
  moduleKey: string,
  departmentModuleKey: string | null | undefined,
  permissionPrefix: string,
): boolean => {
  if (!moduleKey || !departmentModuleKey) {
    return false;
  }

  const normalizedModuleKey = moduleKey.trim().toLowerCase();
  const normalizedDepartmentModuleKey = departmentModuleKey.trim().toLowerCase();

  if (normalizedModuleKey !== normalizedDepartmentModuleKey) {
    return false;
  }

  const moduleConfig = getModuleConfig(normalizedDepartmentModuleKey);
  if (!moduleConfig || moduleConfig.implicitReadPermissions.length === 0) {
    return false;
  }

  return moduleConfig.implicitReadPermissions.includes(
    buildCrudPermission(permissionPrefix, 'read'),
  );
};

export const canReadCrudResource = (
  roles: readonly string[],
  permissions: readonly string[],
  moduleKey: string,
  resource: BackendResourceConfig,
  departmentModuleKey?: string | null,
): boolean => {
  if (hasPrivilegedAccessRole(roles)) {
    return true;
  }

  return (
    hasPermissionCode(permissions, buildCrudPermission(resource.permissionPrefix, 'read')) ||
    hasImplicitDepartmentReadAccess(moduleKey, departmentModuleKey, resource.permissionPrefix)
  );
};

export const canCreateCrudResource = (
  roles: readonly string[],
  permissions: readonly string[],
  resource: BackendResourceConfig,
): boolean => {
  if (hasPrivilegedAccessRole(roles)) {
    return true;
  }

  return hasPermissionCode(permissions, buildCrudPermission(resource.permissionPrefix, 'create'));
};

export const canEditCrudResource = (
  roles: readonly string[],
  permissions: readonly string[],
  resource: BackendResourceConfig,
): boolean => {
  if (hasPrivilegedAccessRole(roles)) {
    return true;
  }

  return hasPermissionCode(permissions, buildCrudPermission(resource.permissionPrefix, 'write'));
};

export const canDeleteCrudResource = (
  roles: readonly string[],
  permissions: readonly string[],
  resource: BackendResourceConfig,
): boolean => {
  if (hasPrivilegedAccessRole(roles)) {
    return true;
  }

  return hasPermissionCode(permissions, buildCrudPermission(resource.permissionPrefix, 'delete'));
};

export const getAccessibleModuleResources = (
  roles: readonly string[],
  permissions: readonly string[],
  moduleKey: string,
  resources: readonly BackendResourceConfig[],
  departmentModuleKey?: string | null,
): BackendResourceConfig[] => {
  return resources.filter((resource) =>
    canReadCrudResource(roles, permissions, moduleKey, resource, departmentModuleKey),
  );
};

export const canAccessModule = (
  roles: readonly string[],
  permissions: readonly string[],
  moduleConfig: BackendModuleConfig,
  departmentModuleKey?: string | null,
): boolean => {
  if (hasPrivilegedAccessRole(roles)) {
    return true;
  }

  const sharedPrefixes = getSharedPermissionPrefixes();
  const primaryResources = moduleConfig.resources.filter(
    (r) => !sharedPrefixes.has(r.permissionPrefix),
  );
  const resourcesToCheck = primaryResources.length > 0 ? primaryResources : moduleConfig.resources;

  return (
    getAccessibleModuleResources(
      roles,
      permissions,
      moduleConfig.key,
      resourcesToCheck,
      departmentModuleKey,
    ).length > 0
  );
};

export const canAccessModuleKey = (
  moduleKey: string,
  roles: readonly string[],
  permissions: readonly string[],
  departmentModuleKey?: string | null,
): boolean => {
  const moduleConfig = getModuleConfig(moduleKey);
  if (!moduleConfig) {
    return false;
  }

  return canAccessModule(roles, permissions, moduleConfig, departmentModuleKey);
};

export const getFirstAccessibleModuleKey = (
  roles: readonly string[],
  permissions: readonly string[],
  departmentModuleKey?: string | null,
): string => {
  return (
    getBackendModules().find((moduleConfig) =>
      canAccessModule(roles, permissions, moduleConfig, departmentModuleKey),
    )?.key ?? ''
  );
};

export const canAccessModuleAnalytics = (
  moduleKey: string,
  roles: readonly string[],
  permissions: readonly string[],
): boolean => {
  if (hasPrivilegedAccessRole(roles)) {
    return true;
  }

  const moduleConfig = getModuleConfig(moduleKey);
  if (!moduleConfig || moduleConfig.analyticsReadPermissions.length === 0) {
    return false;
  }

  return hasAllPermissionCodes(permissions, moduleConfig.analyticsReadPermissions);
};

export const canAccessDashboard = (
  roles: readonly string[],
  permissions: readonly string[],
): boolean => {
  return (
    hasPrivilegedAccessRole(roles) ||
    hasAnyMatchingValue(permissions, DASHBOARD_OVERVIEW_PERMISSIONS)
  );
};

export const canReadDepartmentsDirectory = (
  roles: readonly string[],
  permissions: readonly string[],
  headsAnyDepartment = false,
): boolean => {
  if (hasPrivilegedAccessRole(roles) || headsAnyDepartment) {
    return true;
  }

  return hasAnyMatchingValue(permissions, DEPARTMENT_READ_PERMISSIONS);
};

export const canWriteDepartmentsGlobally = (
  roles: readonly string[],
  permissions: readonly string[],
): boolean => {
  if (hasPrivilegedAccessRole(roles)) {
    return true;
  }

  return hasPermissionCode(permissions, 'department.write');
};

export const canCreateDepartmentsGlobally = (
  roles: readonly string[],
  permissions: readonly string[],
): boolean => {
  if (hasPrivilegedAccessRole(roles)) {
    return true;
  }

  return hasPermissionCode(permissions, 'department.create');
};

export const canDeleteDepartmentsGlobally = (
  roles: readonly string[],
  permissions: readonly string[],
): boolean => {
  if (hasPrivilegedAccessRole(roles)) {
    return true;
  }

  return hasPermissionCode(permissions, 'department.delete');
};

export const canAccessRoleManagement = (
  roles: readonly string[],
  permissions: readonly string[],
): boolean => {
  return (
    hasPrivilegedAccessRole(roles) ||
    hasAnyMatchingValue(permissions, ROLE_MANAGEMENT_READ_PERMISSIONS)
  );
};

export const canCreateRoles = (
  roles: readonly string[],
  permissions: readonly string[],
): boolean => {
  return (
    hasPrivilegedAccessRole(roles) ||
    hasAnyMatchingValue(permissions, ROLE_MANAGEMENT_CREATE_PERMISSIONS)
  );
};

export const canEditRoles = (roles: readonly string[], permissions: readonly string[]): boolean => {
  return (
    hasPrivilegedAccessRole(roles) ||
    hasAnyMatchingValue(permissions, ROLE_MANAGEMENT_WRITE_PERMISSIONS)
  );
};

export const canDeleteRoles = (
  roles: readonly string[],
  permissions: readonly string[],
): boolean => {
  return (
    hasPrivilegedAccessRole(roles) ||
    hasAnyMatchingValue(permissions, ROLE_MANAGEMENT_DELETE_PERMISSIONS)
  );
};

export const canReadEmployeesForRoleManagement = (
  roles: readonly string[],
  permissions: readonly string[],
): boolean => {
  return (
    hasPrivilegedAccessRole(roles) || hasAnyMatchingValue(permissions, EMPLOYEE_READ_PERMISSIONS)
  );
};

export const canWriteEmployeesForRoleManagement = (
  roles: readonly string[],
  permissions: readonly string[],
): boolean => {
  return (
    hasPrivilegedAccessRole(roles) || hasAnyMatchingValue(permissions, EMPLOYEE_WRITE_PERMISSIONS)
  );
};

export const canReadAuditLogs = (
  roles: readonly string[],
  permissions: readonly string[],
): boolean => {
  return hasPrivilegedAccessRole(roles) || hasAnyMatchingValue(permissions, AUDIT_READ_PERMISSIONS);
};
