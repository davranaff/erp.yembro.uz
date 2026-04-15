import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { type ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { baseQueryKeys } from '@/shared/api/query-keys';
import { useApiMutation, useApiQuery } from '@/shared/api/react-query';
import type * as ReactQueryModule from '@/shared/api/react-query';
import { useAuthStore } from '@/shared/auth';
import { I18nProvider } from '@/shared/i18n';

import { RoleManagementPage } from './role-management-page';

vi.mock('@/components/ui/searchable-reference-select', () => ({
  SearchableReferenceSelect: () => <div data-testid="permission-select" />,
}));

vi.mock('@/shared/api/react-query', async () => {
  const actual = await vi.importActual<typeof ReactQueryModule>('@/shared/api/react-query');

  return {
    ...actual,
    useApiQuery: vi.fn(),
    useApiMutation: vi.fn(),
  };
});

type QueryState<TData> = {
  data?: TData;
  error: Error | null;
  isError: boolean;
  isLoading: boolean;
  isFetching: boolean;
  refetch: ReturnType<typeof vi.fn>;
};

type MockQueries = {
  rolesMeta: QueryState<{
    resource: string;
    table: string;
    id_column: string;
    fields: Array<Record<string, unknown>>;
  }>;
  roles: QueryState<{
    items: Array<Record<string, unknown>>;
    total: number;
  }>;
  employees: QueryState<{
    items: Array<Record<string, unknown>>;
    total: number;
  }>;
  selectedPermissions?: Record<
    string,
    QueryState<{
      field: string;
      options: Array<{ value: string; label: string }>;
      multiple: boolean;
    }>
  >;
};

const mockedUseApiQuery = vi.mocked(useApiQuery);
const mockedUseApiMutation = vi.mocked(useApiMutation);
let mutationMutateSpy: ReturnType<typeof vi.fn>;

const permissionField = {
  name: 'permission_ids',
  label: 'Permissions',
  type: 'json',
  database_type: 'uuid[]',
  nullable: true,
  required: false,
  readonly: false,
  has_default: false,
  is_primary_key: false,
  is_foreign_key: false,
  reference: {
    table: 'permissions',
    column: 'id',
    label_column: 'code',
    options: [],
    multiple: true,
  },
};

const createQueryState = <TData,>(
  overrides: Partial<QueryState<TData>> = {},
): QueryState<TData> => ({
  data: undefined,
  error: null,
  isError: false,
  isLoading: false,
  isFetching: false,
  refetch: vi.fn(),
  ...overrides,
});

const setAuthSession = (permissions: string[]) => {
  useAuthStore.setState({
    isAuthenticated: true,
    isInitialized: true,
    isLoading: false,
    error: null,
    session: {
      employeeId: 'employee-1',
      organizationId: 'org-1',
      departmentId: null,
      headsAnyDepartment: false,
      username: 'tester',
      roles: [],
      permissions,
      accessToken: 'token',
      refreshToken: 'refresh',
      expiresAt: null,
    },
  });
};

const mockQueries = (queries: MockQueries) => {
  mockedUseApiQuery.mockImplementation(((options: { queryKey: readonly unknown[] }) => {
    const { queryKey } = options;

    if (JSON.stringify(queryKey) === JSON.stringify(baseQueryKeys.crud.meta('hr', 'roles'))) {
      return queries.rolesMeta;
    }

    if (JSON.stringify(queryKey) === JSON.stringify(baseQueryKeys.crud.resource('hr', 'roles'))) {
      return queries.roles;
    }

    if (
      Array.isArray(queryKey) &&
      queryKey[0] === 'roles-management' &&
      queryKey[1] === 'employees'
    ) {
      return queries.employees;
    }

    if (
      Array.isArray(queryKey) &&
      queryKey[0] === 'roles-management' &&
      queryKey[1] === 'selected-permissions'
    ) {
      const selectedKey = String(queryKey[2] ?? '');
      return (
        queries.selectedPermissions?.[selectedKey] ??
        createQueryState({
          data: {
            field: 'permission_ids',
            options: [],
            multiple: true,
          },
        })
      );
    }

    throw new Error(`Unhandled query key: ${JSON.stringify(queryKey)}`);
  }) as unknown as typeof useApiQuery);
};

const renderPage = (): ReturnType<typeof render> => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <I18nProvider>
        <MemoryRouter>{children}</MemoryRouter>
      </I18nProvider>
    </QueryClientProvider>
  );

  return render(<RoleManagementPage />, { wrapper });
};

beforeEach(() => {
  mutationMutateSpy = vi.fn();

  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: {
      getItem: vi.fn(() => 'ru'),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
    },
  });

  mockedUseApiMutation.mockReturnValue({
    mutate: mutationMutateSpy,
    mutateAsync: vi.fn(),
    reset: vi.fn(),
    data: undefined,
    error: null,
    variables: undefined,
    isError: false,
    isIdle: true,
    isPending: false,
    isPaused: false,
    isSuccess: false,
    status: 'idle',
    failureCount: 0,
    failureReason: null,
    submittedAt: 0,
    context: undefined,
  } as never);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('RoleManagementPage', () => {
  it('shows placeholder workspace state when no role is selected', () => {
    setAuthSession(['role.read', 'role.write']);
    mockQueries({
      rolesMeta: createQueryState({
        data: {
          resource: 'roles',
          table: 'roles',
          id_column: 'id',
          fields: [permissionField],
        },
      }),
      roles: createQueryState({
        data: {
          items: [],
          total: 0,
        },
      }),
      employees: createQueryState({
        data: {
          items: [],
          total: 0,
        },
      }),
    });

    renderPage();

    expect(screen.queryByRole('button', { name: /сохранить/i })).not.toBeInTheDocument();
    expect(
      screen.getByText('Выберите роль слева, чтобы посмотреть детали, или создайте новую роль.'),
    ).toBeInTheDocument();
  });

  it('shows loading state for employee assignments instead of empty state while employees are loading', async () => {
    setAuthSession(['role.read', 'employee.read']);
    mockQueries({
      rolesMeta: createQueryState({
        data: {
          resource: 'roles',
          table: 'roles',
          id_column: 'id',
          fields: [permissionField],
        },
      }),
      roles: createQueryState({
        data: {
          items: [
            {
              id: 'role-1',
              name: 'Warehouse lead',
              slug: 'warehouse-lead',
              description: null,
              is_active: true,
              permission_ids: [],
            },
          ],
          total: 1,
        },
      }),
      employees: createQueryState({
        isLoading: true,
      }),
    });

    renderPage();

    fireEvent.click(screen.getByRole('button', { name: 'Назначение сотрудников' }));

    await waitFor(() => {
      expect(screen.getByText('Загрузка')).toBeInTheDocument();
    });
    expect(screen.queryByText('Подходящие сотрудники не найдены.')).not.toBeInTheDocument();
  });

  it('renders human permission labels for the current role even when meta options are not preloaded', async () => {
    setAuthSession(['role.read']);
    mockQueries({
      rolesMeta: createQueryState({
        data: {
          resource: 'roles',
          table: 'roles',
          id_column: 'id',
          fields: [permissionField],
        },
      }),
      roles: createQueryState({
        data: {
          items: [
            {
              id: 'role-1',
              name: 'Finance reader',
              slug: 'finance-reader',
              description: null,
              is_active: true,
              permission_ids: ['perm-1'],
            },
          ],
          total: 1,
        },
      }),
      employees: createQueryState({
        data: {
          items: [],
          total: 0,
        },
      }),
      selectedPermissions: {
        '': createQueryState({
          data: {
            field: 'permission_ids',
            options: [],
            multiple: true,
          },
        }),
        'perm-1': createQueryState({
          data: {
            field: 'permission_ids',
            options: [{ value: 'perm-1', label: 'expense.read' }],
            multiple: true,
          },
        }),
      },
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText('expense.read')).toBeInTheDocument();
    });
    expect(screen.queryByText('perm-1')).not.toBeInTheDocument();
  });

  it('requires a second click before deleting the selected role', async () => {
    setAuthSession(['role.read', 'role.write', 'role.delete']);
    mockQueries({
      rolesMeta: createQueryState({
        data: {
          resource: 'roles',
          table: 'roles',
          id_column: 'id',
          fields: [permissionField],
        },
      }),
      roles: createQueryState({
        data: {
          items: [
            {
              id: 'role-1',
              name: 'Warehouse lead',
              slug: 'warehouse-lead',
              description: null,
              is_active: true,
              permission_ids: [],
            },
          ],
          total: 1,
        },
      }),
      employees: createQueryState({
        data: {
          items: [],
          total: 0,
        },
      }),
    });

    renderPage();

    fireEvent.click(screen.getByRole('button', { name: /изменить/i }));

    const deleteButton = await screen.findByRole('button', { name: /удалить/i });
    fireEvent.click(deleteButton);

    expect(mutationMutateSpy).not.toHaveBeenCalled();
    expect(await screen.findByRole('button', { name: /подтверждаю/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /подтверждаю/i }));

    expect(mutationMutateSpy).toHaveBeenCalledTimes(1);
    expect(mutationMutateSpy).toHaveBeenCalledWith('role-1');
  });
});
