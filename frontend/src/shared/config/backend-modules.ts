import {
  useWorkspaceStore,
  type BackendModuleConfig,
  type BackendResourceConfig,
} from '@/shared/workspace';

export type { BackendModuleConfig, BackendResourceConfig };

export const getBackendModules = (): BackendModuleConfig[] => useWorkspaceStore.getState().modules;

export const getBackendModuleMap = (): Record<string, BackendModuleConfig> =>
  useWorkspaceStore.getState().moduleMap;
