'use client';

import { useAuth } from '@/contexts/AuthContext';
import { LEVEL_ORDER, ModuleLevel } from '@/types/auth';

/**
 * Возвращает {module_code: level} для активной организации.
 */
export function usePermissions(): Record<string, ModuleLevel> {
  return useAuth().permissions;
}

/**
 * `hasLevel('feed', 'rw')` — true если у юзера в активной org права 'rw' или 'admin' на модуль feed.
 */
export function useHasLevel() {
  return useAuth().hasLevel;
}

export function compareLevel(actual: ModuleLevel | undefined, min: ModuleLevel): boolean {
  return LEVEL_ORDER[actual ?? 'none'] >= LEVEL_ORDER[min];
}
