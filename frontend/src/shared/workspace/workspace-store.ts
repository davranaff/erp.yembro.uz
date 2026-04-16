import { create } from 'zustand';

import type { WorkspaceModuleConfig, WorkspaceResourceConfig } from '@/shared/api/backend-crud';
import { getUnknownErrorLabel } from '@/shared/i18n/fallbacks';

export type BackendResourceConfig = {
  id: string;
  moduleKey: string;
  key: string;
  label: string;
  translationKey?: string;
  path: string;
  description: string;
  permissionPrefix: string;
  apiModuleKey?: string;
  sortOrder: number;
  isHeadVisible: boolean;
  isActive: boolean;
};

export type BackendModuleConfig = {
  id: string;
  key: string;
  label: string;
  description: string;
  icon?: string | null;
  sortOrder: number;
  isDepartmentAssignable: boolean;
  analyticsSectionKey?: string | null;
  implicitReadPermissions: string[];
  analyticsReadPermissions: string[];
  isActive: boolean;
  resources: BackendResourceConfig[];
};

type WorkspaceStore = {
  isLoaded: boolean;
  status: 'idle' | 'loading' | 'ready' | 'error';
  error: string | null;
  reloadToken: number;
  modules: BackendModuleConfig[];
  moduleMap: Record<string, BackendModuleConfig>;
  sharedPermissionPrefixes: Set<string>;
  startLoading: () => void;
  setModules: (modules: WorkspaceModuleConfig[]) => void;
  setError: (message: string) => void;
  requestReload: () => void;
  clearModules: () => void;
};

const normalizeString = (value: unknown, fallback = ''): string => {
  if (typeof value !== 'string') {
    return fallback;
  }
  return value.trim();
};

const normalizeStringArray = (values: unknown): string[] => {
  if (!Array.isArray(values)) {
    return [];
  }
  return values
    .map((value) => normalizeString(value).toLowerCase())
    .filter((value, index, collection) => value.length > 0 && collection.indexOf(value) === index);
};

const normalizeResource = (
  resource: WorkspaceResourceConfig,
  moduleKey: string,
): BackendResourceConfig => {
  const apiModuleKey = normalizeString(resource.api_module_key ?? undefined);
  return {
    id: normalizeString(resource.id),
    moduleKey,
    key: normalizeString(resource.key),
    label: normalizeString(resource.label || resource.name || resource.key),
    translationKey: undefined,
    path: normalizeString(resource.path),
    description: normalizeString(resource.description, ''),
    permissionPrefix: normalizeString(resource.permission_prefix).toLowerCase(),
    apiModuleKey: apiModuleKey || undefined,
    sortOrder: typeof resource.sort_order === 'number' ? resource.sort_order : 100,
    isHeadVisible: Boolean(resource.is_head_visible),
    isActive: resource.is_active !== false,
  };
};

const normalizeModule = (moduleConfig: WorkspaceModuleConfig): BackendModuleConfig => {
  const moduleKey = normalizeString(moduleConfig.key).toLowerCase();
  const moduleIcon = normalizeString(moduleConfig.icon ?? undefined);
  const analyticsSectionKey = normalizeString(moduleConfig.analytics_section_key ?? undefined);
  const resources = Array.isArray(moduleConfig.resources)
    ? moduleConfig.resources
        .map((resource) => normalizeResource(resource, moduleKey))
        .filter(
          (resource) => resource.key.length > 0 && resource.path.length > 0 && resource.isActive,
        )
        .sort((left, right) =>
          left.sortOrder === right.sortOrder
            ? left.label.localeCompare(right.label)
            : left.sortOrder - right.sortOrder,
        )
    : [];

  return {
    id: normalizeString(moduleConfig.id),
    key: moduleKey,
    label: normalizeString(moduleConfig.label || moduleConfig.name || moduleKey),
    description: normalizeString(moduleConfig.description, ''),
    icon: moduleIcon || undefined,
    sortOrder: typeof moduleConfig.sort_order === 'number' ? moduleConfig.sort_order : 100,
    isDepartmentAssignable: moduleConfig.is_department_assignable !== false,
    analyticsSectionKey: analyticsSectionKey || undefined,
    implicitReadPermissions: normalizeStringArray(moduleConfig.implicit_read_permissions),
    analyticsReadPermissions: normalizeStringArray(moduleConfig.analytics_read_permissions),
    isActive: moduleConfig.is_active !== false,
    resources,
  };
};

const buildModuleMap = (modules: BackendModuleConfig[]): Record<string, BackendModuleConfig> =>
  Object.fromEntries(modules.map((moduleConfig) => [moduleConfig.key, moduleConfig]));

const buildSharedPermissionPrefixes = (modules: BackendModuleConfig[]): Set<string> => {
  const prefixCount = new Map<string, number>();
  for (const module of modules) {
    for (const resource of module.resources) {
      prefixCount.set(
        resource.permissionPrefix,
        (prefixCount.get(resource.permissionPrefix) ?? 0) + 1,
      );
    }
  }
  const shared = new Set<string>();
  for (const [prefix, count] of prefixCount) {
    if (count > 1) {
      shared.add(prefix);
    }
  }
  return shared;
};

export const useWorkspaceStore = create<WorkspaceStore>((set) => ({
  isLoaded: false,
  status: 'idle',
  error: null,
  reloadToken: 0,
  modules: [],
  moduleMap: {},
  sharedPermissionPrefixes: new Set<string>(),
  startLoading: () =>
    set((state) => ({
      isLoaded: state.modules.length > 0,
      status: 'loading',
      error: null,
    })),
  setModules: (modules) => {
    const normalizedModules = modules
      .map(normalizeModule)
      .filter((moduleConfig) => moduleConfig.key.length > 0 && moduleConfig.isActive)
      .sort((left, right) =>
        left.sortOrder === right.sortOrder
          ? left.label.localeCompare(right.label)
          : left.sortOrder - right.sortOrder,
      );

    set({
      isLoaded: true,
      status: 'ready',
      error: null,
      modules: normalizedModules,
      moduleMap: buildModuleMap(normalizedModules),
      sharedPermissionPrefixes: buildSharedPermissionPrefixes(normalizedModules),
    });
  },
  setError: (message) =>
    set((state) => ({
      isLoaded: state.modules.length > 0,
      status: 'error',
      error: message.trim() || getUnknownErrorLabel(),
    })),
  requestReload: () =>
    set((state) => ({
      reloadToken: state.reloadToken + 1,
    })),
  clearModules: () =>
    set({
      isLoaded: false,
      status: 'idle',
      error: null,
      modules: [],
      moduleMap: {},
      sharedPermissionPrefixes: new Set<string>(),
    }),
}));
