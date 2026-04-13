export type AuthSession = {
  employeeId: string;
  organizationId?: string;
  departmentId?: string | null;
  departmentModuleKey?: string | null;
  headsAnyDepartment?: boolean;
  roles: string[];
  permissions: string[];
  username?: string;
  accessToken?: string;
  refreshToken?: string;
  expiresAt?: string | null;
};

export type AuthCredentials = Pick<
  AuthSession,
  | 'employeeId'
  | 'organizationId'
  | 'departmentId'
  | 'departmentModuleKey'
  | 'headsAnyDepartment'
  | 'roles'
  | 'permissions'
  | 'username'
> & {
  accessToken?: string;
  refreshToken?: string;
  expiresAt?: string | null;
};

export type AuthLoginCredentials = {
  username: string;
  password: string;
};

export type AuthState = {
  isAuthenticated: boolean;
  isInitialized: boolean;
  isLoading: boolean;
  error: string | null;
  session: AuthSession | null;
};
