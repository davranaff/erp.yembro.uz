import { describe, expect, it } from 'vitest';

import { evaluateRbacAccess, type RbacContext } from './rbac';

const buildContext = (overrides?: Partial<RbacContext>): RbacContext => ({
  isAuthenticated: true,
  roles: ['manager'],
  permissions: ['dashboard.read', 'role.read', 'employee.write'],
  session: null,
  ...overrides,
});

describe('evaluateRbacAccess', () => {
  it('blocks unauthenticated access by default', () => {
    expect(
      evaluateRbacAccess(buildContext({ isAuthenticated: false }), {
        permission: 'dashboard.read',
      }),
    ).toBe(false);
  });

  it('allows unauthenticated checks when explicitly configured', () => {
    expect(
      evaluateRbacAccess(buildContext({ isAuthenticated: false }), {
        requireAuthenticated: false,
        permission: 'dashboard.read',
      }),
    ).toBe(true);
  });

  it('supports role and permission combinations', () => {
    expect(
      evaluateRbacAccess(buildContext(), {
        allRoles: ['manager'],
        anyPermission: ['unknown.permission', 'role.read'],
      }),
    ).toBe(true);
    expect(
      evaluateRbacAccess(buildContext(), {
        allPermissions: ['dashboard.read', 'employee.write'],
      }),
    ).toBe(true);
    expect(
      evaluateRbacAccess(buildContext(), {
        allPermissions: ['dashboard.read', 'audit.read'],
      }),
    ).toBe(false);
  });

  it('supports custom predicates', () => {
    expect(
      evaluateRbacAccess(buildContext(), {
        predicate: (context) => context.roles.includes('manager'),
      }),
    ).toBe(true);
    expect(
      evaluateRbacAccess(buildContext(), {
        predicate: (context) => context.permissions.includes('audit.read'),
      }),
    ).toBe(false);
  });
});
