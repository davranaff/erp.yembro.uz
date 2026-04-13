export const ROUTES = {
  home: '/',
  login: '/login',
  publicMedicineBatch: (token = ':token') => `/public/medicine/${token}`,
  dashboard: '/dashboard',
  dashboardModule: (moduleKey: string) => `/dashboard/${moduleKey}`,
  dashboardModuleForDepartment: (moduleKey: string, departmentId?: string | null) => {
    const pathname = `/dashboard/${moduleKey}`;
    if (!departmentId) {
      return pathname;
    }

    const searchParams = new URLSearchParams({ department: departmentId });
    return `${pathname}?${searchParams.toString()}`;
  },
  settings: '/settings',
  roleManagement: '/roles',
  audit: '/audit',
  app: '/app',
  notFound: '*',
} as const;
