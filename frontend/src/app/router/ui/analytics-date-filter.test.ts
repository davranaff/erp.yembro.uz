import { describe, expect, it } from 'vitest';

import {
  buildAnalyticsDateFilterValue,
  normalizeAnalyticsDateRange,
} from './analytics-date-filter';

describe('analytics date filter helpers', () => {
  it('treats a single selected date as a one-day range', () => {
    const selectedDate = new Date('2026-04-12T00:00:00');

    expect(buildAnalyticsDateFilterValue({ from: selectedDate })).toEqual({
      startDate: '2026-04-12',
      endDate: '2026-04-12',
    });
  });

  it('normalizes reversed dates before applying the range', () => {
    const from = new Date('2026-04-12T00:00:00');
    const to = new Date('2026-04-01T00:00:00');

    expect(normalizeAnalyticsDateRange({ from, to })).toEqual({
      from: to,
      to: from,
    });
  });
});
