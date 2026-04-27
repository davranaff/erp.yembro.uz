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
  { key: 'dash',         label: 'Сводка',             icon: 'grid',  href: '/dashboard',
    aliases: ['dashboard', 'главная', 'kpi'] },
  { key: 'traceability', label: 'Трассировка партий', icon: 'chart', href: '/traceability', module: 'core',
    aliases: ['партия', 'путь партии', 'себестоимость'] },

  { group: 'Ядро' },
  { key: 'counterparties', label: 'Контрагенты',  icon: 'users',   href: '/counterparties', module: 'core',
    aliases: ['клиенты', 'поставщики', 'покупатели'] },
  { key: 'nomenclature',   label: 'Номенклатура', icon: 'box',     href: '/nomenclature',   module: 'core',
    aliases: ['товары', 'sku', 'позиции'] },
  { key: 'accounts',       label: 'План счетов',  icon: 'book',    href: '/accounts',       module: 'ledger',
    aliases: ['gl', 'субсчета'] },
  { key: 'people',         label: 'Сотрудники',   icon: 'users',   href: '/people',         module: 'admin',
    aliases: ['пользователи', 'membership'] },
  { key: 'blocks',         label: 'Блоки',        icon: 'factory', href: '/blocks',         module: 'core',
    aliases: ['корпус', 'птичник', 'шкаф', 'линия'] },

  { group: 'Производство' },
  { key: 'matochnik',  label: 'Маточник',         icon: 'egg',       href: '/matochnik',  module: 'matochnik',
    aliases: ['родители', 'яйца', 'breeding'] },
  { key: 'incubation', label: 'Инкубация',        icon: 'incubator', href: '/incubation', module: 'incubation',
    aliases: ['инкубатор', 'вывод'] },
  { key: 'feedlot',    label: 'Фабрика откорма',  icon: 'factory',   href: '/feedlot',    module: 'feedlot',
    aliases: ['откорм', 'птичник', 'feedlot'] },
  { key: 'slaughter',  label: 'Убойня',           icon: 'building',  href: '/slaughter',  module: 'slaughter',
    aliases: ['разделка', 'тушка'] },
  { key: 'transfers',  label: 'Межмод. передачи', icon: 'chart',     href: '/transfers',  module: 'stock',
    aliases: ['передача', 'transfer'] },

  { group: 'Обеспечение' },
  { key: 'feed',       label: 'Корма',            icon: 'bag',       href: '/feed',       module: 'feed',
    aliases: ['комбикорм', 'рецепт'] },
  { key: 'vet', label: 'Вет. аптека', icon: 'pharma', href: '/vet', module: 'vet',
    aliases: ['ветеринар', 'препараты', 'лекарства'] },
  { key: 'vet-tokens', label: 'Токены продавцов', icon: 'users', href: '/vet/seller-tokens', module: 'vet',
    aliases: ['токен', 'api'] },

  { group: 'Учёт и отчёты' },
  { key: 'stock',     label: 'Склад и движения', icon: 'box',   href: '/stock',           module: 'stock',
    aliases: ['склад', 'движение', 'инвентаризация'] },
  { key: 'purchases', label: 'Закупки',          icon: 'bag',   href: '/purchases',       module: 'purchases',
    aliases: ['закуп', 'поставка', 'po'] },
  { key: 'sales',     label: 'Продажи',          icon: 'bag',   href: '/sales',           module: 'sales',
    aliases: ['продажа', 'отгрузка', 'so'] },
  { key: 'cashbox',   label: 'Касса и банк',     icon: 'book',  href: '/finance/cashbox', module: 'ledger',
    aliases: ['платёж', 'оплата', 'банк', 'касса'] },
  { key: 'ledger',    label: 'Проводки',         icon: 'book',  href: '/ledger',          module: 'ledger',
    aliases: ['журнал', 'je', 'gl'] },
  { key: 'rates',     label: 'Курсы валют',      icon: 'chart', href: '/finance/rates',   module: 'ledger',
    aliases: ['валюта', 'usd', 'cbu'] },
  { key: 'reports',   label: 'Отчёты',           icon: 'chart', href: '/reports',         module: 'ledger',
    aliases: ['осв', 'p&l', 'pl', 'trial balance'] },

  { group: 'Администрирование' },
  { key: 'roles',   label: 'Роли и права',     icon: 'users',    href: '/roles',     module: 'admin',
    aliases: ['rbac', 'доступ', 'права'] },
  { key: 'audit',   label: 'Журнал аудита',    icon: 'book',     href: '/audit-log', module: 'admin',
    aliases: ['аудит', 'история действий', 'audit log'] },
  { key: 'holding', label: 'Холдинг (сводно)', icon: 'building', href: '/holding',
    aliases: ['холдинг', 'консолидация', 'все компании'] },
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
