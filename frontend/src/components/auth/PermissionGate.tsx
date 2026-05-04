'use client';

import { ReactNode } from 'react';

import { useHasLevel } from '@/hooks/usePermissions';
import { ModuleLevel } from '@/types/auth';

interface Props {
  module: string;
  min?: ModuleLevel;
  fallback?: ReactNode;
  children: ReactNode;
}

/**
 * Скрывает children если у юзера в активной организации уровень доступа на модуль ниже `min`.
 *
 *   <PermissionGate module="feed" min="rw">
 *     <button>Создать рецепт</button>
 *   </PermissionGate>
 */
export default function PermissionGate({ module, min = 'r', fallback = null, children }: Props) {
  const hasLevel = useHasLevel();
  return hasLevel(module, min) ? <>{children}</> : <>{fallback}</>;
}
