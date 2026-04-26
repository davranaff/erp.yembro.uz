'use client';

import { ReactNode, useMemo } from 'react';
import { usePathname } from 'next/navigation';

import Icon from '@/components/ui/Icon';
import { useAuth } from '@/contexts/AuthContext';
import { LEVEL_ORDER, type ModuleLevel } from '@/types/auth';

import { flatItems } from '../layout/nav';

/**
 * Маршруты, которые открыты ВСЕМ авторизованным (без RBAC). Расширяй
 * этот список при добавлении страниц без модуля. Все остальные роуты
 * проверяются через `nav.ts` — если в инвентаре нет `module`, страница
 * считается публичной.
 */
const PUBLIC_ROUTES = new Set<string>([
  '/dashboard',
  '/profile',
  '/settings',
  '/holding',
]);

/**
 * Дополнительные правила для подпутей, которые в `nav.ts` не описаны как
 * отдельные пункты. Смотрим по `pathname.startsWith(prefix)`.
 *
 * Например `/feed/<batchId>/print` использует тот же модуль `feed`, что и `/feed`.
 */
const PREFIX_RULES: { prefix: string; module: string; min?: ModuleLevel }[] = [
  { prefix: '/reports', module: 'ledger' },          // /reports/trial-balance, /reports/pl, /reports/gl-ledger
  { prefix: '/finance', module: 'ledger' },          // /finance/cashbox, /finance/rates
  { prefix: '/feed/',   module: 'feed' },            // /feed/<id>/print
  { prefix: '/matochnik/', module: 'matochnik' },    // /matochnik/<id>/print/...
];

/**
 * Резолвит ожидаемый модуль для текущего pathname.
 *
 * Порядок:
 *   1. PUBLIC_ROUTES — пускаем без проверки
 *   2. nav.ts (точное совпадение href)
 *   3. PREFIX_RULES (для вложенных путей которые не в nav)
 *   4. Иначе — публичный (fail-open для несуществующих и системных страниц)
 */
function resolveRequirement(
  pathname: string,
): { module: string; min: ModuleLevel } | null {
  if (PUBLIC_ROUTES.has(pathname)) return null;

  const exact = flatItems().find((i) => i.href === pathname);
  if (exact?.module) {
    return { module: exact.module, min: exact.min ?? 'r' };
  }
  if (exact && !exact.module) return null;

  for (const rule of PREFIX_RULES) {
    if (pathname.startsWith(rule.prefix)) {
      return { module: rule.module, min: rule.min ?? 'r' };
    }
  }

  return null;
}

interface Props {
  children: ReactNode;
}

/**
 * Централизованный route-level RBAC gate. Оборачивает Shell.
 *
 * Если пользователь у которого нет прав на модуль попадает на страницу
 * (например ввёл URL вручную) — показываем `NoAccess` вместо контента.
 * Sidebar уже скрывает ссылки, но эта обёртка закрывает direct-URL
 * атаку и невольные переходы.
 */
export default function RequireRouteAccess({ children }: Props) {
  const pathname = usePathname();
  const { hasLevel, permissions } = useAuth();

  const requirement = useMemo(() => resolveRequirement(pathname), [pathname]);

  if (!requirement) return <>{children}</>;
  if (hasLevel(requirement.module, requirement.min)) return <>{children}</>;

  const userLevel = permissions[requirement.module] ?? 'none';
  const requiredLevel = requirement.min;

  return (
    <NoAccess
      module={requirement.module}
      requiredLevel={requiredLevel}
      currentLevel={userLevel}
    />
  );
}

interface NoAccessProps {
  module: string;
  requiredLevel: ModuleLevel;
  currentLevel: ModuleLevel;
}

const LEVEL_LABEL: Record<ModuleLevel, string> = {
  none: 'Нет доступа',
  r: 'Просмотр',
  rw: 'Ввод документов',
  admin: 'Администратор модуля',
};

const MODULE_LABEL: Record<string, string> = {
  core: 'Ядро',
  matochnik: 'Маточник',
  incubation: 'Инкубация',
  feedlot: 'Откорм',
  slaughter: 'Убойня',
  feed: 'Корма',
  vet: 'Вет. аптека',
  stock: 'Склад',
  ledger: 'Учёт',
  reports: 'Отчёты',
  purchases: 'Закупки',
  sales: 'Продажи',
  admin: 'Администрирование',
};

function NoAccess({ module, requiredLevel, currentLevel }: NoAccessProps) {
  const moduleLabel = MODULE_LABEL[module] ?? module;
  const has = LEVEL_ORDER[currentLevel] > 0;

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Доступ ограничен</h1>
          <div className="sub">У вас нет прав на эту страницу</div>
        </div>
      </div>
      <div
        style={{
          maxWidth: 560,
          margin: '40px auto 0',
          padding: 24,
          border: '1px solid var(--border)',
          borderRadius: 8,
          background: 'var(--bg-card)',
          textAlign: 'center',
        }}
      >
        <div
          style={{
            width: 56,
            height: 56,
            margin: '0 auto 14px',
            borderRadius: '50%',
            display: 'grid',
            placeItems: 'center',
            background: 'var(--brand-orange-soft, #FFF0E6)',
            color: 'var(--brand-orange)',
          }}
        >
          <Icon name="close" size={26} />
        </div>
        <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 6 }}>
          Нет доступа к модулю «{moduleLabel}»
        </div>
        <div style={{ fontSize: 13, color: 'var(--fg-2)', lineHeight: 1.6 }}>
          Для просмотра нужен уровень{' '}
          <b>«{LEVEL_LABEL[requiredLevel]}»</b>{' '}
          или выше.
          <br />
          Ваш текущий уровень:{' '}
          <b style={{ color: has ? 'var(--fg-1)' : 'var(--danger)' }}>
            «{LEVEL_LABEL[currentLevel]}»
          </b>
          .
        </div>
        <div
          style={{
            marginTop: 18,
            padding: '10px 12px',
            background: 'var(--bg-soft)',
            borderRadius: 6,
            fontSize: 12,
            color: 'var(--fg-3)',
            textAlign: 'left',
            lineHeight: 1.5,
          }}
        >
          Если думаете, что доступ должен быть — обратитесь к администратору
          компании. Он может назначить вам роль с правами на этот модуль или
          сделать индивидуальное исключение через раздел «Роли и права».
        </div>
        <div style={{ marginTop: 16, display: 'flex', gap: 8, justifyContent: 'center' }}>
          <a href="/dashboard" className="btn btn-primary btn-sm">
            На сводку
          </a>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => {
              if (typeof window !== 'undefined' && window.history.length > 1) {
                window.history.back();
              }
            }}
          >
            Назад
          </button>
        </div>
      </div>
    </>
  );
}
