/**
 * Единая инвентаризация навигации.
 *
 * Используется в трёх местах: Sidebar, CommandPalette (⌘K) и FavoritesMenu.
 * Если меняешь — затрагивает все три.
 */

import type { ModuleLevel } from '@/types/auth';

export interface NavItem {
  key: string;
  label: string;
  icon: string;
  href: string;
  count?: number;
  pin?: boolean;
  /** module_code для проверки прав; если undefined — пункт виден всем. */
  module?: string;
  min?: ModuleLevel;
  /**
   * Cross-module гейт: пункт виден если у пользователя есть `r+` хотя бы на
   * один модуль из списка. Используется для «сборных» страниц (Сводка,
   * Касса и банк, Токены продавцов) — чтобы их не видел тот, у кого вообще
   * нет смежных модулей (например HR_MANAGER с одним hr-модулем).
   */
  requireAnyModule?: string[];
  /**
   * Альтернативные термины для поиска (palette). Например для «Касса и банк» —
   * ['платёж', 'оплата', 'банк'].
   */
  aliases?: string[];
}

export interface NavGroup {
  group: string;
}

export type NavEntry = NavItem | NavGroup;

export const NAV: NavEntry[] = [
  // ── Главное (без группы) ────────────────────────────────────────────
  // Сводка показывает KPI по производству, финансам, продажам. Скрыта от
  // ролей, у которых только узкий модуль (например HR_MANAGER с hr=admin
  // и без остальных модулей).
  { key: 'dash',         label: 'Сводка',             icon: 'grid',  href: '/dashboard',
    requireAnyModule: ['core', 'ledger', 'reports', 'sales', 'purchases', 'stock',
      'feed', 'feedlot', 'matochnik', 'incubation', 'slaughter', 'vet', 'admin'],
    aliases: ['dashboard', 'главная', 'kpi'] },

  // ── Справочники ─────────────────────────────────────────────────────
  { group: 'Ядро' },
  { key: 'nomenclature',   label: 'Номенклатура', icon: 'box',     href: '/nomenclature',   module: 'core',
    aliases: ['товары', 'sku', 'позиции'] },
  { key: 'blocks',         label: 'Блоки',        icon: 'factory', href: '/blocks',         module: 'core',
    aliases: ['корпус', 'птичник', 'шкаф', 'линия'] },

  // ── Люди ────────────────────────────────────────────────────────────
  { group: 'Люди' },
  { key: 'counterparties', label: 'Контрагенты',  icon: 'users',   href: '/counterparties', module: 'core',
    aliases: ['клиенты', 'поставщики', 'покупатели'] },
  // Сотрудники: cross-module (без module-гейта). Backend в MembershipViewSet
  // фильтрует список — head видит только сотрудников с пересечением модулей,
  // org-admin видит всех.
  { key: 'people',         label: 'Сотрудники',   icon: 'users',   href: '/people',
    aliases: ['пользователи', 'membership'] },

  // ── Зарплата ────────────────────────────────────────────────────────
  { group: 'Зарплата' },
  { key: 'payroll-runs', label: 'Ведомости', icon: 'book', href: '/payroll/runs', module: 'hr',
    aliases: ['ведомость', 'массовая выплата', 'payroll run'] },
  { key: 'schedule-templates', label: 'Графики работы', icon: 'chart', href: '/payroll/templates', module: 'hr',
    aliases: ['график', 'шаблон', 'смены', 'табель'] },

  // ── Производство ────────────────────────────────────────────────────
  { group: 'Производство' },
  { key: 'matochnik',  label: 'Маточник',         icon: 'egg',       href: '/matochnik',  module: 'matochnik',
    aliases: ['родители', 'яйца', 'breeding'] },
  { key: 'incubation', label: 'Инкубация',        icon: 'incubator', href: '/incubation', module: 'incubation',
    aliases: ['инкубатор', 'вывод'] },
  { key: 'feedlot',    label: 'Фабрика откорма',  icon: 'factory',   href: '/feedlot',    module: 'feedlot',
    aliases: ['откорм', 'птичник', 'feedlot'] },
  { key: 'slaughter',  label: 'Убойня',           icon: 'building',  href: '/slaughter',  module: 'slaughter',
    aliases: ['разделка', 'тушка'] },
  // Передачи между модулями — только admin.
  { key: 'transfers',  label: 'Межмод. передачи', icon: 'chart',     href: '/transfers',  module: 'admin', min: 'admin',
    aliases: ['передача', 'transfer'] },

  // ── Обеспечение ─────────────────────────────────────────────────────
  { group: 'Обеспечение' },
  { key: 'feed',       label: 'Корма',            icon: 'bag',       href: '/feed',       module: 'feed',
    aliases: ['комбикорм', 'рецепт'] },
  { key: 'feed-shrinkage', label: 'Профили усушки', icon: 'settings', href: '/feed/shrinkage-profiles', module: 'feed',
    aliases: ['усушка', 'shrinkage', 'потери', 'испарение'] },
  { key: 'vet', label: 'Вет. аптека', icon: 'pharma', href: '/vet', module: 'vet',
    aliases: ['ветеринар', 'препараты', 'лекарства'] },
  // Токены — это API-доступ к vet-сканеру для продавцов. Показываем только
  // тем, у кого есть отношение к vet или sales.
  { key: 'seller-tokens', label: 'Токены продавцов', icon: 'users', href: '/vet/seller-tokens',
    requireAnyModule: ['vet', 'sales', 'admin'],
    aliases: ['токен', 'api', 'продавец', 'scan'] },

  // ── Операции (движения денег и товаров) ─────────────────────────────
  { group: 'Операции' },
  { key: 'stock',     label: 'Склад и движения', icon: 'box',   href: '/stock',           module: 'stock',
    aliases: ['склад', 'движение', 'инвентаризация'] },
  { key: 'purchases', label: 'Закупки',          icon: 'bag',   href: '/purchases',       module: 'purchases',
    aliases: ['закуп', 'поставка', 'po'] },
  { key: 'sales',     label: 'Продажи',          icon: 'bag',   href: '/sales',           module: 'sales',
    aliases: ['продажа', 'отгрузка', 'so'] },
  { key: 'tasks',     label: 'Задачи по долгам', icon: 'bag',   href: '/tasks',           module: 'sales',
    aliases: ['обзвон', 'напоминание', 'collection', 'follow-up'] },
  // Касса и банк: cross-module, фильтрация платежей по модулям внутри viewset.
  // Скрываем для тех, у кого только узкий модуль (например HR).
  { key: 'cashbox',   label: 'Касса и банк',     icon: 'book',  href: '/finance/cashbox',
    requireAnyModule: ['ledger', 'purchases', 'sales', 'vet', 'feed', 'admin'],
    aliases: ['платёж', 'оплата', 'банк', 'касса'] },
  // История оповещений: журнал SMS+TG (для админов и sales-руководителей).
  { key: 'notifications', label: 'Оповещения',  icon: 'inbox', href: '/notifications',
    module: 'admin', min: 'admin',
    aliases: ['уведомления', 'sms', 'telegram', 'история', 'отправлено'] },

  // ── Аналитика (всё отчётно-аналитическое) ───────────────────────────
  { group: 'Аналитика' },
  { key: 'traceability', label: 'Трассировка партий', icon: 'chart', href: '/traceability', module: 'core',
    aliases: ['партия', 'путь партии', 'себестоимость'] },
  { key: 'reports',   label: 'Отчёты (P&L, ОСВ)', icon: 'chart', href: '/reports',         module: 'ledger',
    aliases: ['осв', 'p&l', 'pl', 'trial balance', 'aging'] },
  { key: 'payroll-balances', label: 'Аналитика ЗП', icon: 'chart', href: '/payroll/balances', module: 'hr',
    aliases: ['зарплата', 'долги', 'баланс', 'фонд', 'явка'] },
  { key: 'holding', label: 'Холдинг (сводно)', icon: 'building', href: '/holding', module: 'admin', min: 'admin',
    aliases: ['холдинг', 'консолидация', 'все компании'] },
  { key: 'rates',     label: 'Курсы валют',      icon: 'chart', href: '/finance/rates',   module: 'ledger',
    aliases: ['валюта', 'usd', 'cbu'] },
  { key: 'accounts',  label: 'План счетов',      icon: 'book',  href: '/accounts',        module: 'ledger',
    aliases: ['gl', 'субсчета'] },
  { key: 'ledger',    label: 'Проводки',         icon: 'book',  href: '/ledger',          module: 'ledger',
    aliases: ['журнал', 'je', 'gl'] },
  { key: 'audit',   label: 'Журнал аудита',    icon: 'book',     href: '/audit-log', module: 'admin',
    aliases: ['аудит', 'история действий', 'audit log'] },

  // ── Администрирование ──────────────────────────────────────────────
  { group: 'Администрирование' },
  { key: 'roles',   label: 'Роли и права',     icon: 'users',    href: '/roles',     module: 'admin',
    aliases: ['rbac', 'доступ', 'права'] },
];

export const NAV_FOOTER: NavItem[] = [
  { key: 'profile',  label: 'Профиль',   icon: 'users',    href: '/profile' },
  { key: 'settings', label: 'Настройки', icon: 'settings', href: '/settings' },
];

export function isGroup(entry: NavEntry): entry is NavGroup {
  return 'group' in entry;
}

/** Плоский список всех NavItem (без групп). */
export function flatItems(): NavItem[] {
  return NAV.filter((e): e is NavItem => !isGroup(e)).concat(NAV_FOOTER);
}

/** Найти label для роута. Используется для breadcrumb / favorites. */
export function labelForHref(href: string): string | null {
  const item = flatItems().find((i) => i.href === href);
  return item?.label ?? null;
}
