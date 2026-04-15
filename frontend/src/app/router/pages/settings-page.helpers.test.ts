import { describe, expect, it } from 'vitest';

import {
  canCreateSubdepartmentForAccess,
  canDeleteDepartmentByIdAccess,
  canDeleteDepartmentRecordAccess,
  canManageDepartmentRecordAccess,
  canSaveDepartmentDraftAccess,
  defaultDepartmentForm,
  type DepartmentFormState,
  type DepartmentRbacScope,
  type DepartmentRecord,
} from './settings-page.helpers';

const buildScope = (overrides?: Partial<DepartmentRbacScope>): DepartmentRbacScope => ({
  canWriteAllDepartments: false,
  canCreateRootDepartments: false,
  canDeleteAnyDepartment: false,
  managedDepartmentIds: new Set(['dept-managed', 'dept-child']),
  headedDepartmentIds: new Set(['dept-managed']),
  ...overrides,
});

const buildForm = (overrides?: Partial<DepartmentFormState>): DepartmentFormState => ({
  ...defaultDepartmentForm,
  ...overrides,
});

const buildDepartment = (id: string): DepartmentRecord => ({ id, name: id });

describe('settings RBAC helpers', () => {
  it('checks manage and create scopes for department ids', () => {
    const scope = buildScope();

    expect(canManageDepartmentRecordAccess('dept-managed', scope)).toBe(true);
    expect(canManageDepartmentRecordAccess('dept-other', scope)).toBe(false);
    expect(canCreateSubdepartmentForAccess('dept-child', scope)).toBe(true);
    expect(canCreateSubdepartmentForAccess('dept-other', scope)).toBe(false);
  });

  it('blocks deleting headed departments without global delete access', () => {
    const scope = buildScope();

    expect(canDeleteDepartmentRecordAccess('dept-managed', scope)).toBe(false);
    expect(canDeleteDepartmentRecordAccess('dept-child', scope)).toBe(true);
    expect(
      canDeleteDepartmentRecordAccess('dept-managed', buildScope({ canDeleteAnyDepartment: true })),
    ).toBe(true);
  });

  it('enforces edit and create rules in save drafts', () => {
    const departmentRecordMap = new Map<string, DepartmentRecord>([
      ['dept-managed', buildDepartment('dept-managed')],
      ['dept-other', buildDepartment('dept-other')],
    ]);
    const scope = buildScope();

    expect(
      canSaveDepartmentDraftAccess({
        departmentForm: buildForm(),
        departmentSheetMode: 'edit',
        departmentEditingId: 'dept-managed',
        departmentRecordMap,
        scope,
      }),
    ).toBe(true);
    expect(
      canSaveDepartmentDraftAccess({
        departmentForm: buildForm(),
        departmentSheetMode: 'edit',
        departmentEditingId: 'dept-other',
        departmentRecordMap,
        scope,
      }),
    ).toBe(false);
    expect(
      canSaveDepartmentDraftAccess({
        departmentForm: buildForm({ parentDepartmentId: 'dept-managed' }),
        departmentSheetMode: 'create',
        departmentEditingId: '',
        departmentRecordMap,
        scope,
      }),
    ).toBe(true);
    expect(
      canSaveDepartmentDraftAccess({
        departmentForm: buildForm(),
        departmentSheetMode: 'create',
        departmentEditingId: '',
        departmentRecordMap,
        scope,
      }),
    ).toBe(false);
    expect(
      canSaveDepartmentDraftAccess({
        departmentForm: buildForm(),
        departmentSheetMode: 'create',
        departmentEditingId: '',
        departmentRecordMap,
        scope: buildScope({ canCreateRootDepartments: true }),
      }),
    ).toBe(true);
  });

  it('checks delete-by-id through known records map', () => {
    const departmentRecordMap = new Map<string, DepartmentRecord>([
      ['dept-managed', buildDepartment('dept-managed')],
      ['dept-child', buildDepartment('dept-child')],
    ]);
    const scope = buildScope();

    expect(canDeleteDepartmentByIdAccess('dept-child', departmentRecordMap, scope)).toBe(true);
    expect(canDeleteDepartmentByIdAccess('dept-managed', departmentRecordMap, scope)).toBe(false);
    expect(canDeleteDepartmentByIdAccess('dept-unknown', departmentRecordMap, scope)).toBe(false);
  });
});
