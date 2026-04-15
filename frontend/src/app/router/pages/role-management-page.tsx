import { useQueryClient } from '@tanstack/react-query';
import { Plus, Save, ShieldCheck, Trash2, UserCog, Users2, X } from 'lucide-react';
import {
  type MouseEvent as ReactMouseEvent,
  useDeferredValue,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { useNavigate } from 'react-router-dom';

import { RouteStatusScreen } from '@/app/router/ui/route-status-screen';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { CrudDrawer, CrudDrawerFooter } from '@/components/ui/crud-drawer';
import { ErrorNotice } from '@/components/ui/error-notice';
import { Input } from '@/components/ui/input';
import { SearchableReferenceSelect } from '@/components/ui/searchable-reference-select';
import { Sheet } from '@/components/ui/sheet';
import {
  createCrudRecord,
  deleteCrudRecord,
  getCrudResourceMeta,
  getCrudReferenceOptions,
  listCrudRecords,
  type CrudFieldMeta,
  updateCrudRecord,
  type CrudListResponse,
  type CrudRecord,
  type CrudResourceMeta,
} from '@/shared/api/backend-crud';
import { baseQueryKeys, toQueryKey } from '@/shared/api/query-keys';
import { useApiMutation, useApiQuery } from '@/shared/api/react-query';
import {
  canAccessRoleManagement,
  canCreateRoles,
  canDeleteRoles,
  canEditRoles,
  canReadEmployeesForRoleManagement,
  canWriteEmployeesForRoleManagement,
  useAuthStore,
} from '@/shared/auth';
import { useI18n } from '@/shared/i18n';
import { cn } from '@/shared/lib/cn';

type RoleRecord = CrudRecord & {
  id?: string;
  name?: string;
  slug?: string;
  description?: string | null;
  is_active?: boolean;
  permission_ids?: string[];
};

type EmployeeRecord = CrudRecord & {
  id?: string;
  first_name?: string;
  last_name?: string;
  organization_key?: string;
  email?: string | null;
  is_active?: boolean;
  role_ids?: string[];
};

type PermissionOption = {
  value: string;
  label: string;
};

type RoleFormState = {
  name: string;
  slug: string;
  description: string;
  is_active: boolean;
  permission_ids: string[];
};

type RoleEditorMode = 'create' | 'edit';

const EMPTY_AUTH_LIST: string[] = [];
const EMPTY_ROLE_FORM: RoleFormState = {
  name: '',
  slug: '',
  description: '',
  is_active: true,
  permission_ids: [],
};

const normalizeRolePermissionIds = (permissionIds: string[]): string[] => {
  return permissionIds
    .map((permissionId) => permissionId.trim())
    .filter(
      (permissionId, index, items) =>
        permissionId.length > 0 && items.indexOf(permissionId) === index,
    )
    .sort((left, right) => left.localeCompare(right));
};

const cloneRoleFormState = (form: RoleFormState): RoleFormState => ({
  ...form,
  permission_ids: [...form.permission_ids],
});

const areRoleFormsEqual = (left: RoleFormState, right: RoleFormState): boolean => {
  if (
    left.name !== right.name ||
    left.slug !== right.slug ||
    left.description !== right.description ||
    left.is_active !== right.is_active
  ) {
    return false;
  }

  const leftPermissionIds = normalizeRolePermissionIds(left.permission_ids);
  const rightPermissionIds = normalizeRolePermissionIds(right.permission_ids);

  if (leftPermissionIds.length !== rightPermissionIds.length) {
    return false;
  }

  return leftPermissionIds.every(
    (permissionId, index) => permissionId === rightPermissionIds[index],
  );
};

const surfaceClassName =
  'rounded-[28px] border border-border/70 bg-card shadow-[0_24px_72px_-48px_rgba(15,23,42,0.18)]';
const softPanelClassName =
  'rounded-[22px] border border-border/70 bg-background/80 shadow-[0_16px_40px_-34px_rgba(15,23,42,0.12)]';
const inputClassName =
  'flex min-h-11 w-full rounded-2xl border border-border/75 bg-background px-4 py-3 text-sm text-foreground shadow-[0_14px_32px_-26px_rgba(15,23,42,0.12)] outline-none transition focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2';
const textareaClassName = `${inputClassName} min-h-[128px] resize-y`;

const asString = (value: unknown): string => {
  return typeof value === 'string' ? value : '';
};

const asStringArray = (value: unknown): string[] => {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((item) => (typeof item === 'string' ? item.trim() : ''))
    .filter((item, index, items) => item.length > 0 && items.indexOf(item) === index);
};

const getRoleId = (role: RoleRecord): string => asString(role.id);

const getEmployeeId = (employee: EmployeeRecord): string => asString(employee.id);

const getRoleLabel = (role: RoleRecord): string => {
  return asString(role.name) || asString(role.slug) || getRoleId(role);
};

const getEmployeeLabel = (employee: EmployeeRecord): string => {
  const fullName = [asString(employee.first_name), asString(employee.last_name)]
    .filter(Boolean)
    .join(' ')
    .trim();
  return (
    fullName ||
    asString(employee.organization_key) ||
    asString(employee.email) ||
    getEmployeeId(employee)
  );
};

const toRoleFormState = (role: RoleRecord | null): RoleFormState => {
  if (!role) {
    return EMPTY_ROLE_FORM;
  }

  return {
    name: asString(role.name),
    slug: asString(role.slug),
    description: asString(role.description),
    is_active: role.is_active !== false,
    permission_ids: asStringArray(role.permission_ids),
  };
};

const buildRolePayload = (form: RoleFormState): CrudRecord => {
  return {
    name: form.name.trim(),
    slug: form.slug.trim(),
    description: form.description.trim() || null,
    is_active: form.is_active,
    permission_ids: form.permission_ids,
  };
};

const extractPermissionOptions = (meta: CrudResourceMeta | undefined): PermissionOption[] => {
  const permissionField = meta?.fields.find((field) => field.name === 'permission_ids');
  if (!permissionField?.reference?.options) {
    return [];
  }

  return permissionField.reference.options
    .map((option) => ({
      value: option.value,
      label: option.label,
    }))
    .sort((left, right) => left.label.localeCompare(right.label));
};

const filterRoles = (roles: RoleRecord[], search: string): RoleRecord[] => {
  const normalizedSearch = search.trim().toLowerCase();
  if (!normalizedSearch) {
    return roles;
  }

  return roles.filter((role) => {
    const haystack = [role.name, role.slug, role.description].map(asString).join(' ').toLowerCase();
    return haystack.includes(normalizedSearch);
  });
};

const sortRoles = (roles: RoleRecord[]): RoleRecord[] => {
  return [...roles].sort((left, right) => getRoleLabel(left).localeCompare(getRoleLabel(right)));
};

const sortEmployees = (employees: EmployeeRecord[]): EmployeeRecord[] => {
  return [...employees].sort((left, right) =>
    getEmployeeLabel(left).localeCompare(getEmployeeLabel(right)),
  );
};

export function RoleManagementPage() {
  const queryClient = useQueryClient();
  const { t } = useI18n();
  const navigate = useNavigate();
  const storedSessionRoles = useAuthStore((state) => state.session?.roles);
  const storedSessionPermissions = useAuthStore((state) => state.session?.permissions);
  const sessionRoles = storedSessionRoles ?? EMPTY_AUTH_LIST;
  const sessionPermissions = storedSessionPermissions ?? EMPTY_AUTH_LIST;
  const canOpenPage = canAccessRoleManagement(sessionRoles, sessionPermissions);
  const canCreateRole = canCreateRoles(sessionRoles, sessionPermissions);
  const canEditRole = canEditRoles(sessionRoles, sessionPermissions);
  const canDeleteRole = canDeleteRoles(sessionRoles, sessionPermissions);
  const canReadEmployees = canReadEmployeesForRoleManagement(sessionRoles, sessionPermissions);
  const canWriteEmployees = canWriteEmployeesForRoleManagement(sessionRoles, sessionPermissions);

  const [editorMode, setEditorMode] = useState<RoleEditorMode>('edit');
  const [selectedRoleId, setSelectedRoleId] = useState('');
  const [roleSearch, setRoleSearch] = useState('');
  const [employeeSearch, setEmployeeSearch] = useState('');
  const [roleForm, setRoleForm] = useState<RoleFormState>(EMPTY_ROLE_FORM);
  const [initialRoleFormSnapshot, setInitialRoleFormSnapshot] = useState<RoleFormState | null>(
    null,
  );
  const [formError, setFormError] = useState('');
  const [assignmentError, setAssignmentError] = useState('');
  const [deleteConfirmRoleId, setDeleteConfirmRoleId] = useState('');
  const [isRoleDrawerOpen, setIsRoleDrawerOpen] = useState(false);
  const [isUnsavedRoleDialogOpen, setIsUnsavedRoleDialogOpen] = useState(false);
  const [isAssignmentsDrawerOpen, setIsAssignmentsDrawerOpen] = useState(false);
  const deferredEmployeeSearch = useDeferredValue(employeeSearch);

  const rolesMetaQuery = useApiQuery<CrudResourceMeta>({
    queryKey: baseQueryKeys.crud.meta('hr', 'roles'),
    queryFn: () => getCrudResourceMeta('hr', 'roles'),
  });
  const rolesQuery = useApiQuery<CrudListResponse>({
    queryKey: baseQueryKeys.crud.resource('hr', 'roles'),
    queryFn: () => listCrudRecords('hr', 'roles'),
  });
  const employeesQuery = useApiQuery<CrudListResponse>({
    queryKey: toQueryKey('roles-management', 'employees', deferredEmployeeSearch.trim()),
    queryFn: () =>
      listCrudRecords('hr', 'employees', {
        limit: 24,
        orderBy: 'first_name',
        search: deferredEmployeeSearch.trim() || undefined,
      }),
    enabled: canReadEmployees && Boolean(selectedRoleId),
  });

  const roles = useMemo(
    () => sortRoles((rolesQuery.data?.items ?? []) as RoleRecord[]),
    [rolesQuery.data?.items],
  );
  const employees = useMemo(
    () => sortEmployees((employeesQuery.data?.items ?? []) as EmployeeRecord[]),
    [employeesQuery.data?.items],
  );
  const permissionOptions = useMemo(
    () => extractPermissionOptions(rolesMetaQuery.data),
    [rolesMetaQuery.data],
  );
  const permissionField = useMemo<CrudFieldMeta | null>(
    () => rolesMetaQuery.data?.fields.find((field) => field.name === 'permission_ids') ?? null,
    [rolesMetaQuery.data],
  );
  const selectedPermissionOptionsQuery = useApiQuery({
    queryKey: toQueryKey(
      'roles-management',
      'selected-permissions',
      roleForm.permission_ids.join(','),
    ),
    queryFn: () =>
      getCrudReferenceOptions('hr', 'roles', 'permission_ids', {
        values: roleForm.permission_ids,
        limit: Math.max(roleForm.permission_ids.length, 25),
      }),
    enabled: Boolean(permissionField?.reference) && roleForm.permission_ids.length > 0,
  });
  const permissionLabelMap = useMemo(
    () =>
      new Map(
        [...permissionOptions, ...(selectedPermissionOptionsQuery.data?.options ?? [])].map(
          (option) => [option.value, option.label] as const,
        ),
      ),
    [permissionOptions, selectedPermissionOptionsQuery.data?.options],
  );
  const visibleRoles = useMemo(() => filterRoles(roles, roleSearch), [roles, roleSearch]);
  const activeRolesCount = useMemo(
    () => roles.filter((role) => role.is_active !== false).length,
    [roles],
  );
  const selectedRole = useMemo(
    () => roles.find((role) => getRoleId(role) === selectedRoleId) ?? null,
    [roles, selectedRoleId],
  );
  const visibleEmployees = employees;
  const visibleAssignedEmployeesCount = useMemo(() => {
    if (!selectedRoleId) {
      return 0;
    }

    return visibleEmployees.filter((employee) =>
      asStringArray(employee.role_ids).includes(selectedRoleId),
    ).length;
  }, [selectedRoleId, visibleEmployees]);
  const canSaveCurrentRole =
    editorMode === 'create' ? canCreateRole : canEditRole && Boolean(selectedRoleId);
  const deleteConfirmLabel = t('common.confirm', undefined, 'Подтверждаю');
  const deleteConfirmClassName =
    'border-destructive bg-destructive text-white ring-1 ring-destructive/45 hover:bg-destructive/90 hover:text-white shadow-[0_20px_56px_-22px_rgba(220,38,38,0.78)] font-semibold';

  useEffect(() => {
    if (editorMode === 'create') {
      return;
    }

    if (roles.length === 0) {
      setSelectedRoleId('');
      return;
    }

    if (!selectedRoleId || !roles.some((role) => getRoleId(role) === selectedRoleId)) {
      setSelectedRoleId(getRoleId(roles[0]));
    }
  }, [editorMode, roles, selectedRoleId]);

  useEffect(() => {
    if (editorMode !== 'edit') {
      return;
    }

    setRoleForm(toRoleFormState(selectedRole));
    setFormError('');
  }, [editorMode, selectedRole]);

  useEffect(() => {
    if (!selectedRoleId) {
      setIsAssignmentsDrawerOpen(false);
    }
  }, [selectedRoleId]);

  const invalidateRoleManagementQueries = async (includeEmployees: boolean) => {
    await queryClient.invalidateQueries({
      queryKey: baseQueryKeys.crud.resource('hr', 'roles'),
    });

    if (includeEmployees) {
      await queryClient.invalidateQueries({
        queryKey: toQueryKey('roles-management', 'employees'),
      });
    }

    await queryClient.invalidateQueries({
      queryKey: baseQueryKeys.auth.me,
    });
  };

  const saveRoleMutation = useApiMutation<CrudRecord, Error, RoleFormState>({
    mutationKey: toQueryKey('roles-management', 'save-role'),
    mutationFn: async (form) => {
      if (editorMode === 'create' && !canCreateRole) {
        throw new Error('Недостаточно прав для создания роли.');
      }
      if (editorMode !== 'create' && (!canEditRole || !selectedRoleId)) {
        throw new Error('Недостаточно прав для редактирования роли.');
      }

      const payload = buildRolePayload(form);

      if (editorMode === 'create') {
        return createCrudRecord('hr', 'roles', payload);
      }

      return updateCrudRecord('hr', 'roles', selectedRoleId, payload);
    },
    onSuccess: async (savedRole) => {
      await invalidateRoleManagementQueries(false);
      const nextRole = savedRole as RoleRecord;
      setEditorMode('edit');
      setSelectedRoleId(getRoleId(nextRole));
      setRoleForm(toRoleFormState(nextRole));
      setFormError('');
      setDeleteConfirmRoleId('');
      setInitialRoleFormSnapshot(null);
      setIsRoleDrawerOpen(false);
    },
  });

  const deleteRoleMutation = useApiMutation<{ deleted?: boolean }, Error, string>({
    mutationKey: toQueryKey('roles-management', 'delete-role'),
    mutationFn: (roleId) => {
      if (!canDeleteRole) {
        throw new Error('Недостаточно прав для удаления роли.');
      }
      return deleteCrudRecord('hr', 'roles', roleId);
    },
    onSuccess: async () => {
      await invalidateRoleManagementQueries(true);
      setFormError('');
      setDeleteConfirmRoleId('');
      setInitialRoleFormSnapshot(null);
      setIsRoleDrawerOpen(false);
      setIsAssignmentsDrawerOpen(false);
      if (canCreateRole) {
        setEditorMode('create');
        setRoleForm(EMPTY_ROLE_FORM);
      }
      setSelectedRoleId('');
    },
  });

  const employeeRoleMutation = useApiMutation<
    CrudRecord,
    Error,
    { employeeId: string; roleIds: string[] }
  >({
    mutationKey: toQueryKey('roles-management', 'employee-role'),
    mutationFn: ({ employeeId, roleIds }) => {
      if (!canWriteEmployees) {
        throw new Error('Недостаточно прав для назначения ролей сотрудникам.');
      }
      return updateCrudRecord('hr', 'employees', employeeId, { role_ids: roleIds });
    },
    onSuccess: async () => {
      await invalidateRoleManagementQueries(true);
      setAssignmentError('');
    },
  });

  const handleSelectRole = (role: RoleRecord) => {
    setEditorMode('edit');
    setSelectedRoleId(getRoleId(role));
    setFormError('');
    setAssignmentError('');
    setDeleteConfirmRoleId('');
  };

  const handleCreateDraft = () => {
    if (!canCreateRole) {
      return;
    }

    const nextRoleForm = cloneRoleFormState(EMPTY_ROLE_FORM);

    setEditorMode('create');
    setSelectedRoleId('');
    setRoleForm(nextRoleForm);
    setInitialRoleFormSnapshot(nextRoleForm);
    setFormError('');
    setAssignmentError('');
    setDeleteConfirmRoleId('');
    setEmployeeSearch('');
    setIsRoleDrawerOpen(true);
    setIsAssignmentsDrawerOpen(false);
  };

  const handleOpenEditDrawer = () => {
    if (!canEditRole || !selectedRole) {
      return;
    }

    const nextRoleForm = toRoleFormState(selectedRole);

    setEditorMode('edit');
    setRoleForm(nextRoleForm);
    setInitialRoleFormSnapshot(cloneRoleFormState(nextRoleForm));
    setFormError('');
    setDeleteConfirmRoleId('');
    setIsRoleDrawerOpen(true);
  };

  const handleOpenAssignmentsDrawer = () => {
    if (!canReadEmployees || !selectedRoleId) {
      return;
    }

    setAssignmentError('');
    setIsAssignmentsDrawerOpen(true);
  };

  const handleRoleSave = () => {
    if (!canSaveCurrentRole) {
      return;
    }

    const trimmedName = roleForm.name.trim();
    const trimmedSlug = roleForm.slug.trim();

    if (!trimmedName) {
      setFormError(t('crud.validation.required', undefined, 'Заполните поле.'));
      return;
    }

    if (!trimmedSlug) {
      setFormError(t('crud.validation.required', undefined, 'Заполните поле.'));
      return;
    }

    setFormError('');
    saveRoleMutation.mutate(roleForm);
  };

  const commitDeleteRole = (roleId: string) => {
    if (!canDeleteRole || !roleId) {
      return;
    }

    setDeleteConfirmRoleId('');
    deleteRoleMutation.mutate(roleId);
  };

  const armDeleteRole = (roleId: string) => {
    if (!roleId) {
      return;
    }

    setSelectedRoleId(roleId);
    setDeleteConfirmRoleId(roleId);
  };

  const handleRoleDelete = (event: ReactMouseEvent<HTMLButtonElement>) => {
    event.preventDefault();
    event.stopPropagation();

    if (!canDeleteRole || !selectedRoleId) {
      return;
    }

    if (deleteConfirmRoleId === selectedRoleId) {
      commitDeleteRole(selectedRoleId);
      return;
    }

    armDeleteRole(selectedRoleId);
  };

  const handleEmployeeRoleToggle = (employee: EmployeeRecord) => {
    if (!canWriteEmployees || !selectedRoleId) {
      return;
    }

    const employeeId = getEmployeeId(employee);
    if (!employeeId) {
      return;
    }

    const currentRoleIds = asStringArray(employee.role_ids);
    const nextRoleIds = currentRoleIds.includes(selectedRoleId)
      ? currentRoleIds.filter((roleId) => roleId !== selectedRoleId)
      : [...currentRoleIds, selectedRoleId];

    setAssignmentError('');
    employeeRoleMutation.mutate({
      employeeId,
      roleIds: nextRoleIds,
    });
  };

  const deleteRoleRequiresSecondClick =
    Boolean(selectedRoleId) && deleteConfirmRoleId === selectedRoleId;
  const selectedRolePermissionIds = useMemo(
    () => asStringArray(selectedRole?.permission_ids),
    [selectedRole],
  );
  const selectedRoleDescription = asString(selectedRole?.description).trim();
  const isRoleFormDirty = useMemo(
    () =>
      isRoleDrawerOpen &&
      initialRoleFormSnapshot !== null &&
      !areRoleFormsEqual(roleForm, initialRoleFormSnapshot),
    [initialRoleFormSnapshot, isRoleDrawerOpen, roleForm],
  );
  const unsavedRoleFormWarningMessage = t(
    'common.unsavedChangesConfirm',
    undefined,
    'Есть несохранённые изменения. Закрыть форму без сохранения?',
  );
  const closeRoleDrawer = () => {
    setIsUnsavedRoleDialogOpen(false);
    setDeleteConfirmRoleId('');
    setIsRoleDrawerOpen(false);
    setInitialRoleFormSnapshot(null);
  };
  const requestCloseRoleDrawer = () => {
    if (saveRoleMutation.isPending || deleteRoleMutation.isPending) {
      return;
    }

    if (isRoleFormDirty) {
      setIsUnsavedRoleDialogOpen(true);
      return;
    }

    closeRoleDrawer();
  };

  if (!canOpenPage) {
    return (
      <RouteStatusScreen
        label={t('nav.roleManagement')}
        title={t('route.forbiddenTitle')}
        description={t('route.roleManagementForbiddenDescription')}
        status="forbidden"
        actionLabel={t('common.back')}
        onAction={() => navigate(-1)}
      />
    );
  }

  return (
    <div className="space-y-6" data-tour="roles-page">
      <Card
        className="relative overflow-hidden rounded-[34px] border border-border/70 bg-card shadow-[0_32px_96px_-56px_rgba(15,23,42,0.16)]"
        data-tour="roles-hero"
      >
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 opacity-90"
          style={{
            background:
              'radial-gradient(circle at top left, hsl(var(--primary) / 0.16), transparent 28%), radial-gradient(circle at top right, hsl(var(--secondary) / 0.2), transparent 30%), linear-gradient(180deg, hsl(var(--canvas)), hsl(var(--background)))',
          }}
        />
        <CardContent className="relative space-y-5 p-5 sm:p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-2">
              <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
                <ShieldCheck className="h-3.5 w-3.5" />
                {t('nav.roleManagement', undefined, 'Управление ролями')}
              </div>
              <CardTitle className="text-2xl sm:text-3xl">
                {t('rolesManagement.title', undefined, 'Матрица ролей и назначений')}
              </CardTitle>
            </div>

            <div className="flex flex-wrap gap-2">
              {canCreateRole ? (
                <Button
                  type="button"
                  className="rounded-full"
                  onClick={handleCreateDraft}
                  data-tour="roles-open-editor-drawer-create"
                >
                  <Plus className="h-4 w-4" />
                  {t('rolesManagement.newRole', undefined, 'Новая роль')}
                </Button>
              ) : null}
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            <div className={cn(softPanelClassName, 'p-4')}>
              <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                {t('rolesManagement.totalRoles', undefined, 'Всего ролей')}
              </p>
              <p className="mt-3 text-3xl font-semibold text-foreground">{roles.length}</p>
            </div>
            <div className={cn(softPanelClassName, 'p-4')}>
              <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                {t('rolesManagement.activeRoles', undefined, 'Активных')}
              </p>
              <p className="mt-3 text-3xl font-semibold text-foreground">{activeRolesCount}</p>
            </div>
            <div className={cn(softPanelClassName, 'p-4')}>
              <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                {t('rolesManagement.permissionsPool', undefined, 'Доступные права')}
              </p>
              <p className="mt-3 text-3xl font-semibold text-foreground">
                {permissionOptions.length}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[340px_minmax(0,1fr)]">
        <Card className={surfaceClassName} data-tour="roles-list">
          <CardHeader className="gap-4">
            <div className="flex items-start justify-between gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <CardTitle className="text-xl">
                  {t('rolesManagement.rolesListTitle', undefined, 'Роли')}
                </CardTitle>
                <span className="rounded-full border border-border/70 bg-background px-3 py-1 text-xs text-muted-foreground">
                  {visibleRoles.length}/{roles.length}
                </span>
              </div>
            </div>
            <div className="relative" data-tour="roles-search">
              <Input
                value={roleSearch}
                onChange={(event) => setRoleSearch(event.target.value)}
                placeholder={t(
                  'rolesManagement.roleSearch',
                  undefined,
                  'Поиск по названию или коду роли',
                )}
                className="pr-11"
              />
              {roleSearch.trim().length > 0 ? (
                <button
                  type="button"
                  className="absolute right-3 top-1/2 inline-flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground transition-colors hover:text-foreground"
                  onClick={() => setRoleSearch('')}
                  aria-label={t('common.clearSelection', undefined, 'Очистить выбор')}
                >
                  <X className="h-4 w-4" />
                </button>
              ) : null}
            </div>
          </CardHeader>
          <CardContent className="space-y-2.5">
            {rolesQuery.isError ? (
              <ErrorNotice error={rolesQuery.error} />
            ) : rolesQuery.isLoading ? (
              <div className={cn(softPanelClassName, 'p-4 text-sm text-muted-foreground')}>
                {t('common.loadingLabel')}
              </div>
            ) : visibleRoles.length === 0 ? (
              <div className={cn(softPanelClassName, 'p-4 text-sm text-muted-foreground')}>
                {t('rolesManagement.emptyRoles', undefined, 'Подходящие роли не найдены.')}
              </div>
            ) : (
              visibleRoles.map((role) => {
                const roleId = getRoleId(role);
                const isActive = editorMode === 'edit' && roleId === selectedRoleId;
                const permissionCount = asStringArray(role.permission_ids).length;

                return (
                  <button
                    key={roleId}
                    type="button"
                    onClick={() => handleSelectRole(role)}
                    className={cn(
                      softPanelClassName,
                      'w-full p-3.5 text-left transition',
                      isActive
                        ? 'border-primary/35 bg-primary/10 shadow-[0_18px_48px_-36px_rgba(234,88,12,0.28)]'
                        : 'hover:border-primary/20 hover:bg-primary/5',
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-foreground">
                          {getRoleLabel(role)}
                        </p>
                        <p className="truncate text-xs text-muted-foreground">
                          {asString(role.slug) || '—'}
                        </p>
                      </div>
                      <div className="flex flex-wrap justify-end gap-2">
                        <span
                          className={cn(
                            'rounded-full px-2.5 py-1 text-[11px] font-medium',
                            role.is_active !== false
                              ? 'bg-emerald-500/10 text-emerald-700'
                              : 'bg-muted text-muted-foreground',
                          )}
                        >
                          {role.is_active !== false
                            ? t('rolesManagement.active', undefined, 'Активна')
                            : t('rolesManagement.inactive', undefined, 'Неактивна')}
                        </span>
                        <span className="rounded-full border border-border/70 bg-background px-2.5 py-1 text-[11px] text-muted-foreground">
                          {t(
                            'rolesManagement.permissionCount',
                            { count: permissionCount },
                            '{count} прав',
                          )}
                        </span>
                      </div>
                    </div>
                  </button>
                );
              })
            )}
          </CardContent>
        </Card>

        <Card className={surfaceClassName} data-tour="roles-workspace">
          <CardHeader className="gap-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <CardTitle className="text-xl">
                  {t('rolesManagement.roleWorkspaceTitle', undefined, 'Карточка роли')}
                </CardTitle>
              </div>
              <div className="flex flex-wrap gap-2" data-tour="roles-workspace-actions">
                {selectedRoleId && canEditRole ? (
                  <Button
                    type="button"
                    className="rounded-full"
                    onClick={handleOpenEditDrawer}
                    data-tour="roles-open-editor-drawer-edit"
                  >
                    <Save className="h-4 w-4" />
                    {t('common.edit')}
                  </Button>
                ) : null}
                {selectedRoleId && canReadEmployees ? (
                  <Button
                    type="button"
                    variant="outline"
                    className="rounded-full"
                    onClick={handleOpenAssignmentsDrawer}
                    data-tour="roles-open-assignments-drawer"
                  >
                    <Users2 className="h-4 w-4" />
                    {t('rolesManagement.assignmentsTitle', undefined, 'Назначение сотрудников')}
                  </Button>
                ) : null}
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {rolesMetaQuery.isError ? <ErrorNotice error={rolesMetaQuery.error} /> : null}
            {rolesQuery.isError ? <ErrorNotice error={rolesQuery.error} /> : null}
            {!selectedRole ? (
              <div className={cn(softPanelClassName, 'p-5 text-sm text-muted-foreground')}>
                {t(
                  'rolesManagement.selectRolePlaceholderDescription',
                  undefined,
                  'Выберите роль слева, чтобы посмотреть детали, или создайте новую роль.',
                )}
              </div>
            ) : (
              <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.95fr)]">
                <div className={cn(softPanelClassName, 'space-y-4 p-4')}>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-lg font-semibold text-foreground">
                        {getRoleLabel(selectedRole)}
                      </p>
                      <p className="mt-1 truncate text-sm text-muted-foreground">
                        {asString(selectedRole.slug) || '—'}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <span
                        className={cn(
                          'rounded-full px-2.5 py-1 text-[11px] font-medium',
                          selectedRole.is_active !== false
                            ? 'bg-emerald-500/10 text-emerald-700'
                            : 'bg-muted text-muted-foreground',
                        )}
                      >
                        {selectedRole.is_active !== false
                          ? t('rolesManagement.active', undefined, 'Активна')
                          : t('rolesManagement.inactive', undefined, 'Неактивна')}
                      </span>
                      <span className="rounded-full border border-border/70 px-2.5 py-1 text-[11px] text-muted-foreground">
                        {t(
                          'rolesManagement.membersCount',
                          { count: visibleAssignedEmployeesCount },
                          '{count} назначено в текущей выборке',
                        )}
                      </span>
                      <span className="rounded-full border border-border/70 px-2.5 py-1 text-[11px] text-muted-foreground">
                        {t(
                          'rolesManagement.selectedPermissionsCount',
                          { count: selectedRolePermissionIds.length },
                          '{count} выбрано',
                        )}
                      </span>
                    </div>
                  </div>
                  {selectedRoleDescription ? (
                    <p className="text-sm leading-6 text-foreground">{selectedRoleDescription}</p>
                  ) : null}
                </div>
                <div
                  className={cn(softPanelClassName, 'space-y-3 p-4')}
                  data-tour="roles-permissions-preview"
                >
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <p className="text-sm font-medium text-foreground">
                      {t('rolesManagement.currentPermissionSet', undefined, 'Текущий набор прав')}
                    </p>
                    <span className="rounded-full border border-border/70 px-3 py-1 text-xs text-muted-foreground">
                      {t(
                        'rolesManagement.selectedPermissionsCount',
                        { count: selectedRolePermissionIds.length },
                        '{count} выбрано',
                      )}
                    </span>
                  </div>
                  {selectedRolePermissionIds.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      {t(
                        'rolesManagement.permissionsEmpty',
                        undefined,
                        'Справочник permissions пока пуст.',
                      )}
                    </p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {selectedRolePermissionIds.map((permissionId) => (
                        <span
                          key={permissionId}
                          className="rounded-full border border-border/70 bg-background px-3 py-1 text-xs text-foreground"
                        >
                          {permissionLabelMap.get(permissionId) ?? permissionId}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Sheet
        open={isRoleDrawerOpen}
        onOpenChange={(open) => {
          if (open) {
            setIsUnsavedRoleDialogOpen(false);
            setIsRoleDrawerOpen(true);
            setInitialRoleFormSnapshot(
              (currentSnapshot) => currentSnapshot ?? cloneRoleFormState(roleForm),
            );
            return;
          }

          requestCloseRoleDrawer();
        }}
      >
        <CrudDrawer
          dataTour="roles-editor-drawer"
          title={
            editorMode === 'create'
              ? t('rolesManagement.createTitle', undefined, 'Создание роли')
              : t('rolesManagement.editTitle', undefined, 'Редактирование роли')
          }
          formProps={{
            onSubmit: (event) => {
              event.preventDefault();
              handleRoleSave();
            },
          }}
          footer={
            <CrudDrawerFooter
              closeLabel={t('common.close')}
              closeDisabled={saveRoleMutation.isPending || deleteRoleMutation.isPending}
              onClose={requestCloseRoleDrawer}
              align="between"
            >
              {editorMode === 'edit' && selectedRoleId && canDeleteRole ? (
                <Button
                  type="button"
                  variant={deleteRoleRequiresSecondClick ? 'destructive' : 'outline'}
                  className={cn(
                    !deleteRoleRequiresSecondClick &&
                      'border-destructive/25 bg-destructive/5 text-destructive hover:bg-destructive/10 hover:text-destructive',
                    deleteRoleRequiresSecondClick && deleteConfirmClassName,
                  )}
                  disabled={deleteRoleMutation.isPending}
                  onClick={handleRoleDelete}
                >
                  <Trash2 className="h-4 w-4" />
                  {deleteRoleRequiresSecondClick ? deleteConfirmLabel : t('common.delete')}
                </Button>
              ) : null}
              <Button
                type="submit"
                className="rounded-full"
                disabled={!canSaveCurrentRole || saveRoleMutation.isPending}
              >
                <Save className="h-4 w-4" />
                {editorMode === 'create' ? t('common.create') : t('common.save')}
              </Button>
            </CrudDrawerFooter>
          }
        >
          <div className="space-y-5">
            <div
              className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_220px]"
              data-tour="roles-editor-main-fields"
            >
              <div className="space-y-2">
                <label htmlFor="role-name" className="text-sm font-medium text-foreground">
                  {t('fields.name')}
                </label>
                <Input
                  id="role-name"
                  value={roleForm.name}
                  disabled={!canSaveCurrentRole}
                  onChange={(event) =>
                    setRoleForm((current) => ({
                      ...current,
                      name: event.target.value,
                    }))
                  }
                  placeholder={t(
                    'rolesManagement.roleNamePlaceholder',
                    undefined,
                    'Например, Руководитель HR',
                  )}
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="role-slug" className="text-sm font-medium text-foreground">
                  {t('fields.slug')}
                </label>
                <Input
                  id="role-slug"
                  value={roleForm.slug}
                  disabled={!canSaveCurrentRole}
                  onChange={(event) =>
                    setRoleForm((current) => ({
                      ...current,
                      slug: event.target.value,
                    }))
                  }
                  placeholder={t('rolesManagement.roleSlugPlaceholder', undefined, 'менеджер-hr')}
                />
              </div>
              <div
                className={cn(softPanelClassName, 'flex items-center justify-between gap-3 p-4')}
              >
                <p className="text-sm font-medium text-foreground">{t('fields.is_active')}</p>
                <label className="inline-flex items-center gap-3 text-sm text-foreground">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-border"
                    checked={roleForm.is_active}
                    disabled={!canSaveCurrentRole}
                    onChange={(event) =>
                      setRoleForm((current) => ({
                        ...current,
                        is_active: event.target.checked,
                      }))
                    }
                  />
                  {roleForm.is_active
                    ? t('rolesManagement.active', undefined, 'Активна')
                    : t('rolesManagement.inactive', undefined, 'Неактивна')}
                </label>
              </div>
            </div>

            <div className="space-y-2">
              <label htmlFor="role-description" className="text-sm font-medium text-foreground">
                {t('fields.description')}
              </label>
              <textarea
                id="role-description"
                className={textareaClassName}
                value={roleForm.description}
                disabled={!canSaveCurrentRole}
                onChange={(event) =>
                  setRoleForm((current) => ({
                    ...current,
                    description: event.target.value,
                  }))
                }
                placeholder={t(
                  'rolesManagement.roleDescriptionPlaceholder',
                  undefined,
                  'Коротко опишите, за что отвечает эта роль и какой доступ получает.',
                )}
              />
            </div>

            <div className="space-y-3" data-tour="roles-editor-permissions">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-medium text-foreground">
                  {t('rolesManagement.permissionsTitle', undefined, 'Права внутри роли')}
                </p>
                <div className="rounded-full border border-border/70 px-3 py-1 text-xs text-muted-foreground">
                  {t(
                    'rolesManagement.selectedPermissionsCount',
                    { count: roleForm.permission_ids.length },
                    '{count} выбрано',
                  )}
                </div>
              </div>

              {rolesMetaQuery.isError ? (
                <ErrorNotice
                  error={rolesMetaQuery.error}
                  className={cn(softPanelClassName, 'p-4')}
                />
              ) : rolesMetaQuery.isLoading ? (
                <div className={cn(softPanelClassName, 'p-4 text-sm text-muted-foreground')}>
                  {t('common.loadingLabel')}
                </div>
              ) : !permissionField?.reference ? (
                <div className={cn(softPanelClassName, 'p-4 text-sm text-muted-foreground')}>
                  {t(
                    'rolesManagement.permissionsEmpty',
                    undefined,
                    'Справочник permissions пока пуст.',
                  )}
                </div>
              ) : (
                <div className={cn(softPanelClassName, 'space-y-3 p-4')}>
                  <SearchableReferenceSelect
                    moduleKey="hr"
                    resourcePath="roles"
                    field={permissionField}
                    value={roleForm.permission_ids}
                    onChange={(nextValue) =>
                      setRoleForm((current) => ({
                        ...current,
                        permission_ids: Array.isArray(nextValue) ? nextValue : [],
                      }))
                    }
                    disabled={!canSaveCurrentRole}
                    placeholder={t(
                      'rolesManagement.permissionsSelectPlaceholder',
                      undefined,
                      'Начните вводить код или описание permission',
                    )}
                    searchPlaceholder={t(
                      'rolesManagement.permissionsSearch',
                      undefined,
                      'Поиск по code, resource, action, description',
                    )}
                    emptySearchLabel={t(
                      'rolesManagement.permissionsEmpty',
                      undefined,
                      'Справочник permissions пока пуст.',
                    )}
                  />
                </div>
              )}
            </div>

            {roleForm.permission_ids.length > 0 ? (
              <div className={cn(softPanelClassName, 'space-y-3 p-4')}>
                <p className="text-sm font-medium text-foreground">
                  {t('rolesManagement.currentPermissionSet', undefined, 'Текущий набор прав')}
                </p>
                <div className="flex flex-wrap gap-2">
                  {roleForm.permission_ids.map((permissionId) => (
                    <span
                      key={permissionId}
                      className="rounded-full border border-border/70 bg-background px-3 py-1 text-xs text-foreground"
                    >
                      {permissionLabelMap.get(permissionId) ?? permissionId}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}

            {formError ? <ErrorNotice error={formError} /> : null}
            {saveRoleMutation.isError ? <ErrorNotice error={saveRoleMutation.error} /> : null}
            {deleteRoleMutation.isError ? <ErrorNotice error={deleteRoleMutation.error} /> : null}
          </div>
        </CrudDrawer>
      </Sheet>
      <ConfirmDialog
        open={isUnsavedRoleDialogOpen}
        onOpenChange={setIsUnsavedRoleDialogOpen}
        title={t('common.unsavedChangesTitle', undefined, 'Несохранённые изменения')}
        description={unsavedRoleFormWarningMessage}
        cancelLabel={t('common.stay', undefined, 'Остаться')}
        confirmLabel={t('common.discard', undefined, 'Не сохранять')}
        confirmVariant="destructive"
        onConfirm={closeRoleDrawer}
      />

      <Sheet
        open={isAssignmentsDrawerOpen}
        onOpenChange={(open) => {
          setIsAssignmentsDrawerOpen(open);
          if (!open) {
            setEmployeeSearch('');
            setAssignmentError('');
          }
        }}
      >
        <CrudDrawer
          dataTour="roles-assignments-drawer"
          size="wide"
          title={t('rolesManagement.assignmentsTitle', undefined, 'Назначение сотрудников')}
          footer={
            <CrudDrawerFooter
              closeLabel={t('common.close')}
              onClose={() => setIsAssignmentsDrawerOpen(false)}
            />
          }
        >
          <div className="space-y-4">
            {!selectedRoleId ? (
              <div className={cn(softPanelClassName, 'p-4 text-sm text-muted-foreground')}>
                {t(
                  'rolesManagement.selectRoleFirst',
                  undefined,
                  'Сначала выберите или создайте роль, затем появится список сотрудников для назначения.',
                )}
              </div>
            ) : !canReadEmployees ? (
              <div className={cn(softPanelClassName, 'p-4 text-sm text-muted-foreground')}>
                {t(
                  'rolesManagement.employeesAccessMissing',
                  undefined,
                  'У текущего пользователя нет прав на просмотр сотрудников, поэтому блок назначений скрыт.',
                )}
              </div>
            ) : (
              <>
                <div className={cn(softPanelClassName, 'space-y-3 p-4')}>
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-foreground">
                        {getRoleLabel(selectedRole ?? {})}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {t(
                          'rolesManagement.membersCount',
                          { count: visibleAssignedEmployeesCount },
                          '{count} назначено в текущей выборке',
                        )}
                      </p>
                    </div>
                    <span className="rounded-full border border-border/70 px-3 py-1 text-xs text-muted-foreground">
                      {visibleAssignedEmployeesCount}
                    </span>
                  </div>

                  <div className="relative" data-tour="roles-assignments-search">
                    <Input
                      value={employeeSearch}
                      onChange={(event) => setEmployeeSearch(event.target.value)}
                      placeholder={t(
                        'rolesManagement.employeeSearch',
                        undefined,
                        'Поиск по имени, логину или email',
                      )}
                      className="pr-11"
                    />
                    {employeeSearch.trim().length > 0 ? (
                      <button
                        type="button"
                        className="absolute right-3 top-1/2 inline-flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground transition-colors hover:text-foreground"
                        onClick={() => setEmployeeSearch('')}
                        aria-label={t('common.clearSelection', undefined, 'Очистить выбор')}
                      >
                        <X className="h-4 w-4" />
                      </button>
                    ) : null}
                  </div>
                </div>

                {employeesQuery.isError ? (
                  <ErrorNotice error={employeesQuery.error} />
                ) : employeesQuery.isLoading ? (
                  <div className={cn(softPanelClassName, 'p-4 text-sm text-muted-foreground')}>
                    {t('common.loadingLabel')}
                  </div>
                ) : visibleEmployees.length === 0 ? (
                  <div className={cn(softPanelClassName, 'p-4 text-sm text-muted-foreground')}>
                    {t(
                      'rolesManagement.noEmployees',
                      undefined,
                      'Подходящие сотрудники не найдены.',
                    )}
                  </div>
                ) : (
                  <div className="space-y-3" data-tour="roles-assignments-list">
                    {visibleEmployees.map((employee) => {
                      const employeeId = getEmployeeId(employee);
                      const assigned = asStringArray(employee.role_ids).includes(selectedRoleId);

                      return (
                        <div
                          key={employeeId}
                          className={cn(
                            softPanelClassName,
                            'flex flex-col gap-3 p-3.5 sm:flex-row sm:items-center sm:justify-between',
                            assigned && 'border-primary/28 bg-primary/8',
                          )}
                        >
                          <div className="min-w-0">
                            <p className="truncate text-sm font-medium text-foreground">
                              {getEmployeeLabel(employee)}
                            </p>
                            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                              {asString(employee.organization_key) ? (
                                <span>{asString(employee.organization_key)}</span>
                              ) : null}
                              {asString(employee.email) ? (
                                <span>{asString(employee.email)}</span>
                              ) : null}
                              {employee.is_active === false ? (
                                <span className="rounded-full bg-muted px-2 py-0.5">
                                  {t('rolesManagement.inactiveEmployee', undefined, 'Неактивный')}
                                </span>
                              ) : null}
                            </div>
                          </div>

                          <Button
                            type="button"
                            variant={assigned ? 'default' : 'outline'}
                            className="w-full rounded-full sm:w-auto"
                            disabled={!canWriteEmployees || employeeRoleMutation.isPending}
                            onClick={() => handleEmployeeRoleToggle(employee)}
                          >
                            <UserCog className="h-4 w-4" />
                            {assigned
                              ? t('rolesManagement.removeFromRole', undefined, 'Снять роль')
                              : t('rolesManagement.assignToRole', undefined, 'Назначить')}
                          </Button>
                        </div>
                      );
                    })}
                  </div>
                )}
              </>
            )}

            {assignmentError ? <ErrorNotice error={assignmentError} /> : null}
            {employeeRoleMutation.isError ? (
              <ErrorNotice error={employeeRoleMutation.error} />
            ) : null}
          </div>
        </CrudDrawer>
      </Sheet>
    </div>
  );
}
