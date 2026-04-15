import type { TourProgressState } from './types';

const TOUR_PROGRESS_STORAGE_KEY = 'frontend:tour-progress';

const isBrowser = typeof window !== 'undefined';

const DEFAULT_PROGRESS_STATE: TourProgressState = {
  completed: {},
  dismissed: {},
};

const sanitizeVersionMap = (value: unknown): Record<string, number> => {
  if (!value || typeof value !== 'object') {
    return {};
  }

  const entries = Object.entries(value as Record<string, unknown>)
    .map(([tourId, version]) => {
      if (typeof tourId !== 'string' || !tourId.trim()) {
        return null;
      }

      if (typeof version !== 'number' || !Number.isFinite(version) || version <= 0) {
        return null;
      }

      return [tourId.trim(), Math.floor(version)] as const;
    })
    .filter((entry): entry is readonly [string, number] => entry !== null);

  return Object.fromEntries(entries);
};

export const loadTourProgress = (): TourProgressState => {
  if (!isBrowser) {
    return DEFAULT_PROGRESS_STATE;
  }

  const rawValue = window.localStorage.getItem(TOUR_PROGRESS_STORAGE_KEY);
  if (!rawValue) {
    return DEFAULT_PROGRESS_STATE;
  }

  try {
    const parsed = JSON.parse(rawValue) as Partial<TourProgressState>;
    return {
      completed: sanitizeVersionMap(parsed.completed),
      dismissed: sanitizeVersionMap(parsed.dismissed),
    };
  } catch {
    window.localStorage.removeItem(TOUR_PROGRESS_STORAGE_KEY);
    return DEFAULT_PROGRESS_STATE;
  }
};

export const saveTourProgress = (state: TourProgressState): void => {
  if (!isBrowser) {
    return;
  }

  window.localStorage.setItem(
    TOUR_PROGRESS_STORAGE_KEY,
    JSON.stringify({
      completed: state.completed,
      dismissed: state.dismissed,
    }),
  );
};

export const isTourCompleted = (
  state: TourProgressState,
  tourId: string,
  version: number,
): boolean => (state.completed[tourId] ?? 0) >= version;

export const isTourDismissed = (
  state: TourProgressState,
  tourId: string,
  version: number,
): boolean => (state.dismissed[tourId] ?? 0) >= version;

export const markTourCompleted = (
  state: TourProgressState,
  tourId: string,
  version: number,
): TourProgressState => ({
  completed: {
    ...state.completed,
    [tourId]: version,
  },
  dismissed: {
    ...state.dismissed,
  },
});

export const markTourDismissed = (
  state: TourProgressState,
  tourId: string,
  version: number,
): TourProgressState => ({
  completed: {
    ...state.completed,
  },
  dismissed: {
    ...state.dismissed,
    [tourId]: version,
  },
});
