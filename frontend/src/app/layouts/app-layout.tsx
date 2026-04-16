import {
  BarChart3,
  BookOpen,
  Building2,
  CircleHelp,
  ChevronDown,
  History,
  LogOut,
  Settings,
  type LucideIcon,
} from 'lucide-react';
import { type ReactNode, useEffect, useMemo, useState } from 'react';
import { NavLink, Outlet, type To, useLocation, useNavigate } from 'react-router-dom';

import { LanguageSwitcher } from '@/app/ui/language-switcher';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Separator } from '@/components/ui/separator';
import { listVisibleDepartments, type CrudListResponse } from '@/shared/api/backend-crud';
import { useApiQuery } from '@/shared/api/react-query';
import {
  AccessGate,
  canAccessDashboard,
  canAccessModuleKey,
  hasModuleManagerRole,
  hasPrivilegedAccessRole,
  canReadAuditLogs,
  useAuthStore,
} from '@/shared/auth';
import { getDepartmentIcon } from '@/shared/config/department-icons';
import { ROUTES } from '@/shared/config/routes';
import { useI18n } from '@/shared/i18n';
import { cn } from '@/shared/lib/cn';
import {
  buildDepartmentTree,
  flattenDepartmentTree,
  type DepartmentTreeNode,
} from '@/shared/lib/departments';
import { isValidUuid } from '@/shared/lib/uuid';
import { useTour } from '@/shared/tour';
import { useWorkspaceStore, type BackendModuleConfig } from '@/shared/workspace';

const EMPTY_AUTH_LIST: string[] = [];

type AppLayoutProps = {
  children?: ReactNode;
};

type DepartmentNavRecord = {
  id?: string;
  name?: string;
  code?: string;
  icon?: string | null;
  module_key?: string;
  parent_department_id?: string | null;
};

type DepartmentNavTreeNode = DepartmentTreeNode<DepartmentNavRecord>;

type TopNavLinkProps = {
  to: To;
  icon: LucideIcon;
  label: string;
  end?: boolean;
  isActiveOverride?: (location: ReturnType<typeof useLocation>) => boolean;
};

const primaryNavLinkClassName =
  'flex w-full min-w-0 items-center gap-2 rounded-full border px-4 py-2.5 text-sm font-medium transition-colors';
const departmentNavLinkClassName =
  'flex w-full min-w-0 items-center gap-2 rounded-full border px-3 py-2 text-sm font-medium transition-colors';
const CORE_MODULE_KEY = 'core';

const getWorkspaceModuleConfig = (
  moduleMap: Record<string, BackendModuleConfig>,
  moduleKey: string,
): BackendModuleConfig | null =>
  moduleKey && Object.prototype.hasOwnProperty.call(moduleMap, moduleKey)
    ? moduleMap[moduleKey]
    : null;

const getDepartmentLabel = (department: DepartmentNavRecord): string => {
  if (typeof department.name === 'string' && department.name) {
    return department.name;
  }

  if (typeof department.code === 'string' && department.code) {
    return department.code;
  }

  if (typeof department.id === 'string' && department.id) {
    return department.id;
  }

  return '';
};

const copySearchParam = (source: URLSearchParams, target: URLSearchParams, key: string) => {
  const value = source.get(key);
  if (value) {
    target.set(key, value);
  }
};

const buildModuleTarget = ({
  moduleKey,
  currentModuleKey,
  currentDepartmentId,
  currentSearchParams,
  departmentId,
}: {
  moduleKey: string;
  currentModuleKey: string;
  currentDepartmentId: string;
  currentSearchParams: URLSearchParams;
  departmentId?: string;
}): To => {
  const nextSearchParams = new URLSearchParams();
  const currentView = currentSearchParams.get('view') ?? '';
  const currentResourceKey = currentSearchParams.get('resource') ?? '';
  const isSameDepartment = currentDepartmentId === (departmentId ?? '');

  if (currentView === 'stats') {
    nextSearchParams.set('view', 'stats');
  }

  copySearchParam(currentSearchParams, nextSearchParams, 'startDate');
  copySearchParam(currentSearchParams, nextSearchParams, 'endDate');

  if (currentModuleKey === moduleKey && isSameDepartment && currentResourceKey) {
    nextSearchParams.set('resource', currentResourceKey);
  }

  if (departmentId) {
    nextSearchParams.set('department', departmentId);
  }

  const nextSearch = nextSearchParams.toString();

  return {
    pathname: ROUTES.dashboardModule(moduleKey),
    search: nextSearch ? `?${nextSearch}` : '',
  };
};

const buildOverviewTarget = (currentSearchParams: URLSearchParams): To => {
  const nextSearchParams = new URLSearchParams();

  copySearchParam(currentSearchParams, nextSearchParams, 'startDate');
  copySearchParam(currentSearchParams, nextSearchParams, 'endDate');

  const nextSearch = nextSearchParams.toString();

  return {
    pathname: ROUTES.dashboard,
    search: nextSearch ? `?${nextSearch}` : '',
  };
};

const buildSettingsTarget = (): To => ({
  pathname: ROUTES.settings,
});

const buildAuditTarget = (): To => ({
  pathname: ROUTES.audit,
});

function TopNavLink({ to, icon: Icon, label, end = false, isActiveOverride }: TopNavLinkProps) {
  const location = useLocation();

  return (
    <NavLink to={to} end={end} className="block min-w-0">
      {({ isActive }) => (
        <div
          className={cn(
            primaryNavLinkClassName,
            (isActiveOverride ? isActiveOverride(location) : isActive)
              ? 'border-primary/30 bg-primary/10 text-foreground shadow-[0_16px_40px_-28px_rgba(234,88,12,0.18)]'
              : 'border-slate-200 bg-white text-muted-foreground shadow-[0_14px_34px_-28px_rgba(15,23,42,0.12)] hover:border-slate-300 hover:bg-slate-50 hover:text-foreground',
          )}
        >
          <Icon className="h-4 w-4" />
          <span className="min-w-0 flex-1 truncate">{label}</span>
        </div>
      )}
    </NavLink>
  );
}

function DepartmentNavLink({
  currentDepartmentId,
  currentModuleKey,
  currentSearchParams,
  department,
}: {
  currentDepartmentId: string;
  currentModuleKey: string;
  currentSearchParams: URLSearchParams;
  department: DepartmentNavRecord;
}) {
  const { t } = useI18n();
  const moduleMap = useWorkspaceStore((state) => state.moduleMap);
  const departmentId = typeof department.id === 'string' ? department.id : '';
  const moduleKey = typeof department.module_key === 'string' ? department.module_key : '';
  const moduleConfig = getWorkspaceModuleConfig(moduleMap, moduleKey);
  const DepartmentIcon = getDepartmentIcon(department.icon, moduleConfig?.icon);
  const departmentLabel = getDepartmentLabel(department);
  const navLabel = moduleKey
    ? t(`modules.${moduleKey}.label`, undefined, departmentLabel)
    : departmentLabel;
  const isActive =
    departmentId !== '' && currentDepartmentId === departmentId && currentModuleKey === moduleKey;

  return (
    <NavLink
      to={buildModuleTarget({
        moduleKey,
        currentModuleKey,
        currentDepartmentId,
        currentSearchParams,
        departmentId: departmentId || undefined,
      })}
      className="block min-w-0"
    >
      <div
        className={cn(
          departmentNavLinkClassName,
          isActive
            ? 'border-primary/30 bg-primary/10 text-foreground shadow-[0_16px_38px_-28px_rgba(234,88,12,0.18)]'
            : 'border-slate-200 bg-white text-muted-foreground shadow-[0_14px_34px_-28px_rgba(15,23,42,0.1)] hover:border-slate-300 hover:bg-slate-50 hover:text-foreground',
        )}
      >
        <span
          className={cn(
            'flex h-7 w-7 shrink-0 items-center justify-center rounded-full border',
            isActive
              ? 'border-primary/28 bg-primary/14 text-primary'
              : 'border-slate-200 bg-slate-50 text-primary',
          )}
        >
          {DepartmentIcon ? (
            <DepartmentIcon className="h-3.5 w-3.5" />
          ) : (
            <Building2 className="h-3.5 w-3.5" />
          )}
        </span>
        <span className="min-w-0 flex-1 truncate">{navLabel}</span>
      </div>
    </NavLink>
  );
}

function DepartmentNavDropdown({
  rootNode,
  currentDepartmentId,
  currentRootDepartmentId,
  currentModuleKey,
  currentSearchParams,
  isOpen,
  onOpenChange,
}: {
  rootNode: DepartmentNavTreeNode;
  currentDepartmentId: string;
  currentRootDepartmentId: string;
  currentModuleKey: string;
  currentSearchParams: URLSearchParams;
  isOpen: boolean;
  onOpenChange: (nextOpen: boolean) => void;
}) {
  const { t } = useI18n();
  const moduleMap = useWorkspaceStore((state) => state.moduleMap);
  const rootDepartment = rootNode.record;
  const moduleKey = typeof rootDepartment.module_key === 'string' ? rootDepartment.module_key : '';
  const rootModuleConfig = getWorkspaceModuleConfig(moduleMap, moduleKey);
  const RootIcon = getDepartmentIcon(rootDepartment.icon, rootModuleConfig?.icon);
  const childNodes = useMemo(() => flattenDepartmentTree(rootNode.children), [rootNode.children]);
  const rootDepartmentLabel = rootNode.label;
  const navLabel = moduleKey
    ? t(`modules.${moduleKey}.label`, undefined, rootDepartmentLabel)
    : rootDepartmentLabel;
  const isActive =
    rootNode.id !== '' && currentRootDepartmentId === rootNode.id && currentModuleKey === moduleKey;

  return (
    <Popover open={isOpen} onOpenChange={onOpenChange}>
      <PopoverTrigger
        className={cn(
          departmentNavLinkClassName,
          isActive
            ? 'border-primary/30 bg-primary/10 text-foreground shadow-[0_16px_38px_-28px_rgba(234,88,12,0.18)]'
            : 'border-slate-200 bg-white text-muted-foreground shadow-[0_14px_34px_-28px_rgba(15,23,42,0.1)] hover:border-slate-300 hover:bg-slate-50 hover:text-foreground',
        )}
      >
        <span
          className={cn(
            'flex h-7 w-7 shrink-0 items-center justify-center rounded-full border',
            isActive
              ? 'border-primary/28 bg-primary/14 text-primary'
              : 'border-slate-200 bg-slate-50 text-primary',
          )}
        >
          {RootIcon ? <RootIcon className="h-3.5 w-3.5" /> : <Building2 className="h-3.5 w-3.5" />}
        </span>
        <span className="min-w-0 flex-1 truncate">{navLabel}</span>
        <ChevronDown className="h-3.5 w-3.5 opacity-70" />
      </PopoverTrigger>
      <PopoverContent
        align="start"
        sideOffset={10}
        className="w-[min(20rem,calc(100vw-1.5rem))] max-w-[calc(100vw-1.5rem)] rounded-[28px] border border-slate-200 bg-white p-2 shadow-[0_30px_84px_-48px_rgba(15,23,42,0.18)]"
      >
        <div className="space-y-1">
          <NavLink
            to={buildModuleTarget({
              moduleKey,
              currentModuleKey,
              currentDepartmentId,
              currentSearchParams,
              departmentId: rootNode.id || undefined,
            })}
          >
            <div
              className={cn(
                'flex items-center gap-3 rounded-2xl px-3 py-3 transition-colors',
                currentDepartmentId === rootNode.id && currentModuleKey === moduleKey
                  ? 'bg-primary/8 text-foreground shadow-[0_12px_30px_-26px_rgba(15,23,42,0.12)]'
                  : 'bg-transparent text-muted-foreground hover:bg-slate-50 hover:text-foreground',
              )}
            >
              <span
                className={cn(
                  'flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl border',
                  currentDepartmentId === rootNode.id && currentModuleKey === moduleKey
                    ? 'border-primary/28 bg-primary/14 text-primary'
                    : 'border-slate-200 bg-slate-50 text-primary',
                )}
              >
                {RootIcon ? <RootIcon className="h-4 w-4" /> : <Building2 className="h-4 w-4" />}
              </span>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-foreground">{navLabel}</p>
                <p className="text-xs text-muted-foreground">
                  {rootDepartmentLabel !== navLabel
                    ? rootDepartmentLabel
                    : typeof rootDepartment.code === 'string' && rootDepartment.code
                      ? rootDepartment.code
                      : moduleKey}
                </p>
              </div>
            </div>
          </NavLink>

          {childNodes.length > 0 ? <Separator className="my-2" /> : null}

          {childNodes.map((childNode) => {
            const childDepartment = childNode.record;
            const childModuleKey =
              typeof childDepartment.module_key === 'string'
                ? childDepartment.module_key
                : moduleKey;
            const childModuleConfig = getWorkspaceModuleConfig(moduleMap, childModuleKey);
            const ChildIcon = getDepartmentIcon(childDepartment.icon, childModuleConfig?.icon);
            const relativeDepth = Math.max(0, childNode.depth - rootNode.depth - 1);

            return (
              <NavLink
                key={childNode.id}
                to={buildModuleTarget({
                  moduleKey: childModuleKey,
                  currentModuleKey,
                  currentDepartmentId,
                  currentSearchParams,
                  departmentId: childNode.id || undefined,
                })}
              >
                <div
                  className={cn(
                    'flex items-center gap-3 rounded-2xl px-3 py-2.5 transition-colors',
                    currentDepartmentId === childNode.id && currentModuleKey === childModuleKey
                      ? 'bg-primary/8 text-foreground shadow-[0_12px_30px_-26px_rgba(15,23,42,0.12)]'
                      : 'bg-transparent text-muted-foreground hover:bg-slate-50 hover:text-foreground',
                  )}
                  style={{ paddingLeft: `${0.75 + relativeDepth * 1}rem` }}
                >
                  <span
                    className={cn(
                      'flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border',
                      currentDepartmentId === childNode.id && currentModuleKey === childModuleKey
                        ? 'border-primary/28 bg-primary/14 text-primary'
                        : 'border-slate-200 bg-slate-50 text-primary',
                    )}
                  >
                    {ChildIcon ? (
                      <ChildIcon className="h-3.5 w-3.5" />
                    ) : (
                      <Building2 className="h-3.5 w-3.5" />
                    )}
                  </span>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-foreground">
                      {childNode.label}
                    </p>
                    {typeof childDepartment.code === 'string' && childDepartment.code ? (
                      <p className="truncate text-xs text-muted-foreground">
                        {childDepartment.code}
                      </p>
                    ) : null}
                  </div>
                </div>
              </NavLink>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}

function WorkspaceNavigation() {
  const navigate = useNavigate();
  const location = useLocation();
  const clearSession = useAuthStore((state) => state.clearSession);
  const sessionEmployeeId = useAuthStore((state) => state.session?.employeeId ?? '');
  const storedSessionRoles = useAuthStore((state) => state.session?.roles);
  const storedSessionPermissions = useAuthStore((state) => state.session?.permissions);
  const sessionRoles = storedSessionRoles ?? EMPTY_AUTH_LIST;
  const sessionPermissions = storedSessionPermissions ?? EMPTY_AUTH_LIST;
  const sessionDepartmentModuleKey = useAuthStore(
    (state) => state.session?.departmentModuleKey ?? null,
  );
  const workspaceModuleMap = useWorkspaceStore((state) => state.moduleMap);
  const { t } = useI18n();
  const { hasContextTour, contextTourTitle, startContextTour, isActive: isTourActive } = useTour();
  const currentSearchParams = useMemo(
    () => new URLSearchParams(location.search),
    [location.search],
  );
  const isSettingsRoute = location.pathname === ROUTES.settings;
  const isRoleManagementRoute = location.pathname === ROUTES.roleManagement;
  const isAuditRoute = location.pathname === ROUTES.audit;
  const requestedDepartmentId = currentSearchParams.get('department') ?? '';
  const currentModuleKey = useMemo(() => {
    if (!location.pathname.startsWith(`${ROUTES.dashboard}/`)) {
      return '';
    }

    return location.pathname.slice(`${ROUTES.dashboard}/`.length);
  }, [location.pathname]);

  const departmentsQuery = useApiQuery<CrudListResponse>({
    queryKey: ['crud', 'core', 'visible-departments', 'workspace-nav'],
    queryFn: () => listVisibleDepartments(),
    enabled: sessionEmployeeId.length > 0,
  });

  const allDepartments = useMemo(() => {
    const items = (departmentsQuery.data?.items ?? []) as DepartmentNavRecord[];

    return [...items]
      .filter((department) => {
        const moduleKey = typeof department.module_key === 'string' ? department.module_key : '';
        const departmentId = typeof department.id === 'string' ? department.id : '';
        const moduleConfig = getWorkspaceModuleConfig(workspaceModuleMap, moduleKey);

        return (
          isValidUuid(departmentId) &&
          moduleKey !== '' &&
          Boolean(moduleConfig?.isDepartmentAssignable) &&
          canAccessModuleKey(
            moduleKey,
            sessionRoles,
            sessionPermissions,
            sessionDepartmentModuleKey,
          )
        );
      })
      .sort((leftDepartment, rightDepartment) => {
        const leftModuleKey =
          typeof leftDepartment.module_key === 'string' ? leftDepartment.module_key : '';
        const rightModuleKey =
          typeof rightDepartment.module_key === 'string' ? rightDepartment.module_key : '';
        const leftOrder =
          getWorkspaceModuleConfig(workspaceModuleMap, leftModuleKey)?.sortOrder ??
          Number.MAX_SAFE_INTEGER;
        const rightOrder =
          getWorkspaceModuleConfig(workspaceModuleMap, rightModuleKey)?.sortOrder ??
          Number.MAX_SAFE_INTEGER;

        if (leftOrder !== rightOrder) {
          return leftOrder - rightOrder;
        }

        return getDepartmentLabel(leftDepartment).localeCompare(
          getDepartmentLabel(rightDepartment),
        );
      });
  }, [
    departmentsQuery.data,
    sessionDepartmentModuleKey,
    sessionPermissions,
    sessionRoles,
    workspaceModuleMap,
  ]);

  const departmentTree = useMemo(
    () => buildDepartmentTree(allDepartments, getDepartmentLabel),
    [allDepartments],
  );
  const departmentNodes = useMemo(() => flattenDepartmentTree(departmentTree), [departmentTree]);
  const departmentNodeMap = useMemo(
    () => new Map(departmentNodes.map((node) => [node.id, node] as const)),
    [departmentNodes],
  );
  const currentDepartmentId = useMemo(
    () =>
      isValidUuid(requestedDepartmentId) && departmentNodeMap.has(requestedDepartmentId)
        ? requestedDepartmentId
        : '',
    [departmentNodeMap, requestedDepartmentId],
  );

  useEffect(() => {
    if (!departmentsQuery.isSuccess && !departmentsQuery.isError) {
      return;
    }

    if (!requestedDepartmentId || isValidUuid(requestedDepartmentId)) {
      if (!requestedDepartmentId || currentDepartmentId === requestedDepartmentId) {
        return;
      }
    }

    const nextSearchParams = new URLSearchParams(location.search);
    nextSearchParams.delete('department');
    const nextSearch = nextSearchParams.toString();

    navigate(
      {
        pathname: location.pathname,
        search: nextSearch ? `?${nextSearch}` : '',
      },
      { replace: true },
    );
  }, [
    currentDepartmentId,
    departmentsQuery.isError,
    departmentsQuery.isSuccess,
    location.pathname,
    location.search,
    navigate,
    requestedDepartmentId,
  ]);
  const currentDepartmentNode = currentDepartmentId
    ? (departmentNodeMap.get(currentDepartmentId) ?? null)
    : null;
  const currentModuleConfig = getWorkspaceModuleConfig(workspaceModuleMap, currentModuleKey);
  const canAccessCoreModule = useMemo(
    () =>
      hasPrivilegedAccessRole(sessionRoles) ||
      hasModuleManagerRole(sessionRoles) ||
      canAccessModuleKey(
        CORE_MODULE_KEY,
        sessionRoles,
        sessionPermissions,
        sessionDepartmentModuleKey,
      ),
    [sessionDepartmentModuleKey, sessionPermissions, sessionRoles],
  );
  const currentModuleRootNodes = useMemo(
    () =>
      departmentTree.filter((rootNode) => {
        const moduleKey =
          typeof rootNode.record.module_key === 'string' ? rootNode.record.module_key : '';
        return moduleKey === currentModuleKey;
      }),
    [currentModuleKey, departmentTree],
  );
  const currentDepartmentLabel = currentDepartmentNode
    ? currentDepartmentNode.label
    : isSettingsRoute
      ? t('nav.settings', undefined, 'Настройки')
      : isRoleManagementRoute
        ? t('nav.roleManagement', undefined, 'Роли')
        : isAuditRoute
          ? t('nav.audit', undefined, 'Аудит')
          : currentModuleRootNodes.length === 1
            ? currentModuleRootNodes[0].label
            : currentModuleKey
              ? t(
                  `modules.${currentModuleKey}.label`,
                  undefined,
                  getWorkspaceModuleConfig(workspaceModuleMap, currentModuleKey)?.label ??
                    currentModuleKey,
                )
              : t('nav.dashboard', undefined, 'Дашборд');
  const currentRootDepartmentId =
    currentDepartmentNode?.rootId ??
    (currentModuleRootNodes.length === 1 ? currentModuleRootNodes[0].id : '');
  const [openDropdownDepartmentId, setOpenDropdownDepartmentId] = useState('');
  const hasDepartmentNavigation = departmentTree.length > 0;
  const isStandaloneModuleRoute =
    !currentDepartmentNode &&
    Boolean(currentModuleKey) &&
    currentModuleConfig?.isDepartmentAssignable === false;
  const currentContextDescription = isStandaloneModuleRoute
    ? t(
        `modules.${currentModuleKey}.label`,
        undefined,
        currentModuleConfig.label || currentModuleKey,
      )
    : hasDepartmentNavigation
      ? t('resources.departments.label', undefined, 'Отделы')
      : t('settings.description', undefined, 'Профиль и параметры доступа.');

  useEffect(() => {
    setOpenDropdownDepartmentId('');
  }, [location.pathname, location.search]);

  const handleLogout = () => {
    clearSession();
    navigate(ROUTES.login, { replace: true });
  };

  return (
    <div className="sticky top-3 z-30 sm:top-4" data-tour="workspace-nav">
      <div className="overflow-hidden rounded-[26px] border border-slate-200 bg-white shadow-[0_28px_84px_-54px_rgba(15,23,42,0.16)] sm:rounded-[30px]">
        <div className="flex flex-col gap-3 p-3 sm:gap-4 sm:p-5">
          <div className="flex flex-col gap-3 sm:gap-4 xl:flex-row xl:items-start xl:justify-between">
            <div className="min-w-0 space-y-2">
              <Badge variant="muted" className="w-fit border-slate-200 bg-slate-50">
                {t('nav.heading', undefined, 'Навигация')}
              </Badge>
              <div className="space-y-1">
                <p className="truncate text-xl font-semibold tracking-[-0.03em] text-foreground">
                  {currentDepartmentLabel || t('nav.dashboard', undefined, 'Дашборд')}
                </p>
                <p className="text-sm text-muted-foreground">{currentContextDescription}</p>
              </div>
            </div>

            <div
              className="flex w-full flex-wrap items-center gap-2 self-start xl:w-auto xl:self-auto"
              data-tour="workspace-session-tools"
            >
              {hasContextTour ? (
                <Button
                  type="button"
                  variant="outline"
                  className="rounded-full border-slate-200 bg-white px-4 shadow-[0_14px_32px_-26px_rgba(15,23,42,0.1)]"
                  onClick={startContextTour}
                  disabled={isTourActive}
                  title={contextTourTitle || t('common.help', undefined, 'Помощь')}
                >
                  <CircleHelp className="h-4 w-4" />
                  {t('common.help', undefined, 'Помощь')}
                </Button>
              ) : null}
              <LanguageSwitcher />
              <Button
                type="button"
                variant="outline"
                className="rounded-full border-slate-200 bg-white px-4 shadow-[0_14px_32px_-26px_rgba(15,23,42,0.1)]"
                onClick={handleLogout}
              >
                <LogOut className="h-4 w-4" />
                {t('common.logout')}
              </Button>
            </div>
          </div>

          <div className="grid gap-3 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.55fr)]">
            <section
              className="min-w-0 rounded-[24px] border border-slate-200 bg-slate-50 px-3.5 py-3.5"
              data-tour="workspace-primary-nav"
            >
              <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                {t('nav.heading', undefined, 'Навигация')}
              </p>
              <div className="grid min-w-0 grid-cols-1 gap-2 sm:[grid-template-columns:repeat(auto-fit,minmax(11rem,1fr))]">
                <AccessGate
                  access={{
                    predicate: (context) => canAccessDashboard(context.roles, context.permissions),
                  }}
                >
                  <TopNavLink
                    to={buildOverviewTarget(currentSearchParams)}
                    end
                    icon={BarChart3}
                    label={t('nav.dashboard', undefined, 'Дашборд')}
                  />
                </AccessGate>
                <TopNavLink
                  to={buildSettingsTarget()}
                  end
                  icon={Settings}
                  label={t('nav.settings', undefined, 'Настройки')}
                />
                {canAccessCoreModule ? (
                  <TopNavLink
                    to={buildModuleTarget({
                      moduleKey: CORE_MODULE_KEY,
                      currentModuleKey,
                      currentDepartmentId,
                      currentSearchParams,
                    })}
                    icon={BookOpen}
                    label={t('modules.core.label', undefined, 'Справочники')}
                  />
                ) : null}
                <AccessGate
                  access={{
                    predicate: (context) => canReadAuditLogs(context.roles, context.permissions),
                  }}
                >
                  <TopNavLink
                    to={buildAuditTarget()}
                    end
                    icon={History}
                    label={t('nav.audit', undefined, 'Аудит')}
                  />
                </AccessGate>
              </div>
            </section>

            <div data-tour="module-department-filter">
              <section
                className="min-w-0 rounded-[24px] border border-slate-200 bg-slate-50 px-3.5 py-3.5"
                data-tour="workspace-department-nav"
              >
                <div className="mb-3 flex items-center justify-between gap-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                    {t('resources.departments.label', undefined, 'Отделы')}
                  </p>
                  {hasDepartmentNavigation ? (
                    <Badge
                      variant="outline"
                      className="border-slate-200 bg-white normal-case tracking-normal"
                    >
                      {departmentTree.length}
                    </Badge>
                  ) : null}
                </div>
                {hasDepartmentNavigation ? (
                  <div className="grid min-w-0 grid-cols-1 gap-2 sm:[grid-template-columns:repeat(auto-fit,minmax(13rem,1fr))]">
                    {departmentTree.map((rootNode) =>
                      rootNode.children.length > 0 ? (
                        <DepartmentNavDropdown
                          key={rootNode.id}
                          rootNode={rootNode}
                          currentDepartmentId={currentDepartmentId}
                          currentRootDepartmentId={currentRootDepartmentId}
                          currentModuleKey={currentModuleKey}
                          currentSearchParams={currentSearchParams}
                          isOpen={openDropdownDepartmentId === rootNode.id}
                          onOpenChange={(nextOpen) => {
                            setOpenDropdownDepartmentId(nextOpen ? rootNode.id : '');
                          }}
                        />
                      ) : (
                        <DepartmentNavLink
                          key={rootNode.id}
                          currentDepartmentId={currentDepartmentId}
                          currentModuleKey={currentModuleKey}
                          currentSearchParams={currentSearchParams}
                          department={rootNode.record}
                        />
                      ),
                    )}
                  </div>
                ) : (
                  <div className="rounded-2xl border border-dashed border-slate-200 bg-white px-4 py-4 text-sm text-muted-foreground">
                    {t('crud.currentPageRangeEmpty', undefined, 'На этой странице пока нет строк.')}
                  </div>
                )}
              </section>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function AppLayout({ children }: AppLayoutProps) {
  const location = useLocation();
  const showWorkspaceNav =
    location.pathname === ROUTES.dashboard ||
    location.pathname.startsWith(`${ROUTES.dashboard}/`) ||
    location.pathname === ROUTES.settings ||
    location.pathname === ROUTES.roleManagement ||
    location.pathname === ROUTES.audit;

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,hsl(var(--primary)/0.14),transparent_24%),radial-gradient(circle_at_top_right,hsl(var(--accent)/0.12),transparent_26%),radial-gradient(circle_at_bottom,hsl(var(--secondary)/0.24),transparent_34%),linear-gradient(180deg,hsl(var(--canvas)),hsl(var(--background)))]">
      <div className="mx-auto flex min-h-screen w-full max-w-[1760px] flex-col gap-3 px-3 py-3 sm:gap-4 sm:px-6 sm:py-5 xl:px-8">
        {showWorkspaceNav ? <WorkspaceNavigation /> : null}
        <main className="min-w-0 flex-1">{children ?? <Outlet />}</main>
      </div>
    </div>
  );
}
