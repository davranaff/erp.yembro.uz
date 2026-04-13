export const baseQueryKeys = {
  root: ['root'] as const,
  health: ['root', 'health'] as const,
  shell: ['root', 'shell'] as const,
  dashboard: {
    root: ['dashboard'] as const,
    stats: ['dashboard', 'stats'] as const,
    overview: ['dashboard', 'overview'] as const,
  },
  system: {
    root: ['system'] as const,
    audit: ['system', 'audit'] as const,
  },
  crud: {
    root: ['crud'] as const,
    module: (moduleKey: string) => ['crud', moduleKey] as const,
    meta: (moduleKey: string, resourceKey: string) =>
      ['crud', moduleKey, resourceKey, 'meta'] as const,
    resource: (moduleKey: string, resourceKey: string) =>
      ['crud', moduleKey, resourceKey] as const,
    item: (moduleKey: string, resourceKey: string, recordId: string) =>
      ['crud', moduleKey, resourceKey, recordId] as const,
    auditResource: (moduleKey: string, resourceKey: string) =>
      ['crud', moduleKey, resourceKey, 'audit'] as const,
    audit: (moduleKey: string, resourceKey: string, recordId: string) =>
      ['crud', moduleKey, resourceKey, 'audit', recordId] as const,
  },
  auth: {
    login: ['auth', 'login'] as const,
    me: ['auth', 'me'] as const,
  },
  workspace: {
    root: ['workspace'] as const,
    modules: ['workspace', 'modules'] as const,
  },
} as const;

export const toQueryKey = <T extends readonly unknown[]>(...parts: T) => parts;
