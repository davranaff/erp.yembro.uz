import { useEffect, useRef } from 'react';
import { useBlocker } from 'react-router-dom';

import { useI18n } from '@/shared/i18n';

type Counter = { value: number };

const counter: Counter = { value: 0 };
const listeners = new Set<() => void>();

const emit = () => {
  listeners.forEach((listener) => listener());
};

export const hasAnyDirtyForm = () => counter.value > 0;

export const subscribeDirtyForms = (listener: () => void) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};

export function useRegisterDirtyForm(isDirty: boolean) {
  const wasDirty = useRef(false);

  useEffect(() => {
    if (isDirty && !wasDirty.current) {
      wasDirty.current = true;
      counter.value += 1;
      emit();
    } else if (!isDirty && wasDirty.current) {
      wasDirty.current = false;
      counter.value = Math.max(0, counter.value - 1);
      emit();
    }
  }, [isDirty]);

  useEffect(() => {
    return () => {
      if (wasDirty.current) {
        wasDirty.current = false;
        counter.value = Math.max(0, counter.value - 1);
        emit();
      }
    };
  }, []);
}

export function useBeforeUnloadWhenDirty(isDirty: boolean) {
  useEffect(() => {
    if (!isDirty) {
      return;
    }
    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
      return '';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [isDirty]);
}

export function useDirtyRouteBlocker(isDirty: boolean) {
  const { t } = useI18n();
  const blocker = useBlocker(({ currentLocation, nextLocation }) => {
    if (!isDirty) {
      return false;
    }
    return (
      currentLocation.pathname + currentLocation.search !==
      nextLocation.pathname + nextLocation.search
    );
  });

  useEffect(() => {
    if (blocker.state !== 'blocked') {
      return;
    }
    const message = t(
      'common.unsavedNavigationConfirm',
      undefined,
      'В открытой форме есть несохранённые изменения. Покинуть страницу?',
    );
    if (window.confirm(message)) {
      blocker.proceed();
    } else {
      blocker.reset();
    }
  }, [blocker, t]);
}
