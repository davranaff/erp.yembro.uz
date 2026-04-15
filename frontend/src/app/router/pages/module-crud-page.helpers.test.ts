import { describe, expect, it } from 'vitest';

import type { CrudFieldMeta } from '@/shared/api/backend-crud';

import {
  buildFormValues,
  getDisplayValue,
  getFieldInputKind,
  getInputType,
  getReferenceOptionLabel,
  getResourceUiConfig,
} from './module-crud-page.helpers';

const buildField = (overrides?: Partial<CrudFieldMeta>): CrudFieldMeta => ({
  name: 'work_start_time',
  label: 'Work start time',
  type: 'time',
  database_type: 'time without time zone',
  nullable: true,
  required: false,
  readonly: false,
  has_default: false,
  is_primary_key: false,
  is_foreign_key: false,
  reference: null,
  ...overrides,
});

describe('module CRUD field helpers', () => {
  it('treats database time fields as time inputs', () => {
    const field = buildField();

    expect(getFieldInputKind(field)).toBe('time');
    expect(getInputType(field)).toBe('time');
  });

  it('normalizes stored time values for the form and display', () => {
    const field = buildField();
    const values = buildFormValues([field], {
      work_start_time: '09:00:00',
    });

    expect(values.work_start_time).toBe('09:00');
    expect(getDisplayValue(field, '18:30:00', 'Yes', 'No', '—')).toBe('18:30');
  });

  it('keeps positions org-level in the module editor UI', () => {
    const config = getResourceUiConfig('hr', 'positions');

    expect(config?.hiddenFields).toContain('department_id');
    expect(config?.hideOrganizationFieldWhenScoped).toBe(true);
  });

  it('keeps poultry types org-level in the module editor UI', () => {
    const config = getResourceUiConfig('core', 'poultry-types');

    expect(config?.tableOrder).toEqual(['name', 'code', 'description', 'is_active']);
    expect(config?.hideOrganizationFieldWhenScoped).toBe(true);
  });

  it('translates static client debt statuses', () => {
    const field = buildField({
      name: 'status',
      label: 'Status',
      type: 'string',
      database_type: 'character varying',
      reference: {
        table: '__static__',
        column: 'value',
        label_column: 'label',
        options: [],
      },
    });

    const translate = (
      key: string,
      _params?: Record<string, string | number>,
      fallback?: string,
    ) => (key === 'clientDebtStatuses.partially_paid' ? 'Частично оплачен' : (fallback ?? key));

    expect(getReferenceOptionLabel(field, 'partially_paid', 'partially_paid', translate)).toBe(
      'Частично оплачен',
    );
  });
});
