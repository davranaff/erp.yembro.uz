import { canAccessRoleManagement, canReadAuditLogs } from '@/shared/auth';

import type {
  TourAccessContext,
  TourDefinition,
  TourRouteMatcher,
  TourStepDefinition,
} from './types';

const DASHBOARD_ROUTE_MATCHER: TourRouteMatcher = /^\/dashboard$/;
const MODULE_ROUTE_MATCHER: TourRouteMatcher = /^\/dashboard\/[^/]+$/;
const CORE_MODULE_ROUTE_MATCHER: TourRouteMatcher = /^\/dashboard\/core$/;
const INVENTORY_MODULE_ROUTE_MATCHER: TourRouteMatcher = /^\/dashboard\/inventory$/;
const LOGIN_ROUTE_MATCHER: TourRouteMatcher = '/login';
const APP_ROUTE_MATCHER: TourRouteMatcher = /^\/(?:dashboard(?:\/[^/]+)?|settings|roles|audit)$/;

const normalizePathname = (pathname: string): string => {
  if (!pathname || pathname === '/') {
    return '/';
  }

  return pathname.endsWith('/') ? pathname.replace(/\/+$/, '') : pathname;
};

const normalizeSet = (values: readonly string[]): Set<string> =>
  new Set(values.map((value) => value.trim().toLowerCase()).filter((value) => value.length > 0));

const hasAnyValue = (values: readonly string[], requiredValues: readonly string[]): boolean => {
  if (requiredValues.length === 0) {
    return true;
  }

  const normalizedValues = normalizeSet(values);
  return requiredValues.some((requiredValue) =>
    normalizedValues.has(requiredValue.trim().toLowerCase()),
  );
};

export const matchesTourRoute = (matcher: TourRouteMatcher, pathname: string): boolean => {
  const normalizedPathname = normalizePathname(pathname);

  if (typeof matcher === 'string') {
    return matcher === normalizedPathname;
  }

  if (matcher instanceof RegExp) {
    return matcher.test(normalizedPathname);
  }

  return matcher(normalizedPathname);
};

const KNOWN_ROUTE_MATCHERS: readonly TourRouteMatcher[] = [
  '/',
  LOGIN_ROUTE_MATCHER,
  DASHBOARD_ROUTE_MATCHER,
  MODULE_ROUTE_MATCHER,
  '/settings',
  '/roles',
  '/audit',
  '/app',
];

const NOT_FOUND_ROUTE_MATCHER: TourRouteMatcher = (pathname) =>
  !KNOWN_ROUTE_MATCHERS.some((matcher) => matchesTourRoute(matcher, pathname));

export const isTourDefinitionAvailable = (
  definition: TourDefinition,
  context: TourAccessContext,
): boolean => {
  if (!context.isAuthenticated && !definition.allowUnauthenticated) {
    return false;
  }

  if (definition.isAvailable && !definition.isAvailable(context)) {
    return false;
  }

  return true;
};

export const isTourStepAvailable = (
  step: TourStepDefinition,
  context: TourAccessContext,
): boolean => {
  if (step.route && !matchesTourRoute(step.route, context.pathname)) {
    return false;
  }

  if (
    step.requiredRoles &&
    step.requiredRoles.length > 0 &&
    !hasAnyValue(context.roles, step.requiredRoles)
  ) {
    return false;
  }

  if (
    step.requiredPermissions &&
    step.requiredPermissions.length > 0 &&
    !hasAnyValue(context.permissions, step.requiredPermissions)
  ) {
    return false;
  }

  return true;
};

export const TOUR_DEFINITIONS: readonly TourDefinition[] = [
  {
    id: 'platform-intro',
    version: 2,
    titleKey: 'tour.tours.platform.title',
    descriptionKey: 'tour.tours.platform.description',
    titleFallback: 'Быстрый тур по платформе',
    descriptionFallback: 'Короткий обзор навигации, отделов и рабочих инструментов.',
    route: APP_ROUTE_MATCHER,
    priority: 20,
    autoStart: true,
    steps: [
      {
        id: 'workspace-nav',
        target: '[data-tour="workspace-nav"]',
        titleKey: 'tour.steps.workspaceNav.title',
        descriptionKey: 'tour.steps.workspaceNav.description',
        titleFallback: 'Рабочая панель',
        descriptionFallback: 'Здесь находится основная панель с текущим рабочим контекстом.',
      },
      {
        id: 'workspace-primary-nav',
        target: '[data-tour="workspace-primary-nav"]',
        titleKey: 'tour.steps.primaryNavigation.title',
        descriptionKey: 'tour.steps.primaryNavigation.description',
        titleFallback: 'Основная навигация',
        descriptionFallback: 'Отсюда вы переходите в главные разделы приложения.',
      },
      {
        id: 'workspace-departments',
        target: '[data-tour="workspace-department-nav"]',
        titleKey: 'tour.steps.departmentNavigation.title',
        descriptionKey: 'tour.steps.departmentNavigation.description',
        titleFallback: 'Навигация по отделам',
        descriptionFallback: 'Выбор отдела сразу меняет данные, с которыми вы работаете.',
      },
      {
        id: 'workspace-session-tools',
        target: '[data-tour="workspace-session-tools"]',
        titleKey: 'tour.steps.sessionTools.title',
        descriptionKey: 'tour.steps.sessionTools.description',
        titleFallback: 'Инструменты сессии',
        descriptionFallback: 'Здесь находятся язык, запуск тура и выход из аккаунта.',
      },
    ],
  },
  {
    id: 'dashboard-tour',
    version: 2,
    titleKey: 'tour.tours.dashboard.title',
    descriptionKey: 'tour.tours.dashboard.description',
    titleFallback: 'Тур по дашборду',
    descriptionFallback: 'Покажет ключевые блоки аналитики и управления отображением данных.',
    route: DASHBOARD_ROUTE_MATCHER,
    priority: 120,
    steps: [
      {
        id: 'dashboard-hero',
        target: '[data-tour="dashboard-hero"]',
        titleKey: 'tour.steps.dashboardHero.title',
        descriptionKey: 'tour.steps.dashboardHero.description',
        titleFallback: 'Общая картина',
        descriptionFallback: 'Здесь виден выбранный период и текущее состояние показателей.',
      },
      {
        id: 'dashboard-filters',
        target: '[data-tour="dashboard-filters"]',
        titleKey: 'tour.steps.dashboardFilters.title',
        descriptionKey: 'tour.steps.dashboardFilters.description',
        titleFallback: 'Фильтры',
        descriptionFallback: 'Через этот блок можно менять данные, которые попадут в отчёт.',
      },
      {
        id: 'dashboard-quick-ranges',
        target: '[data-tour="dashboard-quick-ranges"]',
        titleKey: 'tour.steps.dashboardQuickRanges.title',
        descriptionKey: 'tour.steps.dashboardQuickRanges.description',
        titleFallback: 'Быстрые периоды',
        descriptionFallback: 'Готовые периоды для быстрого переключения отчёта.',
      },
      {
        id: 'dashboard-department-filter',
        target: '[data-tour="dashboard-department-filter"]',
        titleKey: 'tour.steps.dashboardDepartmentFilter.title',
        descriptionKey: 'tour.steps.dashboardDepartmentFilter.description',
        titleFallback: 'Фильтр по отделу',
        descriptionFallback: 'Выберите отдел, чтобы смотреть данные только по нему.',
        skipIfTargetMissing: true,
      },
      {
        id: 'dashboard-date-filter',
        target: '[data-tour="dashboard-date-filter"]',
        titleKey: 'tour.steps.dashboardDateFilter.title',
        descriptionKey: 'tour.steps.dashboardDateFilter.description',
        titleFallback: 'Выбор дат',
        descriptionFallback: 'Точный диапазон дат для отчёта.',
      },
      {
        id: 'dashboard-summary',
        target: '[data-tour="dashboard-summary"]',
        titleKey: 'tour.steps.dashboardSummary.title',
        descriptionKey: 'tour.steps.dashboardSummary.description',
        titleFallback: 'Ключевые карточки',
        descriptionFallback: 'Главные цифры по выбранному периоду.',
      },
      {
        id: 'dashboard-sections',
        target: '[data-tour="dashboard-sections"]',
        titleKey: 'tour.steps.dashboardSections.title',
        descriptionKey: 'tour.steps.dashboardSections.description',
        titleFallback: 'Разделы отчёта',
        descriptionFallback: 'Подробная аналитика по направлениям деятельности.',
      },
    ],
  },
  {
    id: 'module-tour',
    version: 9,
    titleKey: 'tour.tours.module.title',
    descriptionKey: 'tour.tours.module.description',
    titleFallback: 'Тур по разделу',
    descriptionFallback: 'Покажет полный цикл работы с данными в выбранном разделе.',
    route: MODULE_ROUTE_MATCHER,
    priority: 115,
    steps: [
      {
        id: 'module-view-switch',
        target: '[data-tour="module-view-switch"]',
        titleKey: 'tour.steps.moduleViewSwitch.title',
        descriptionKey: 'tour.steps.moduleViewSwitch.description',
        titleFallback: 'Переключение режимов',
        descriptionFallback: 'Здесь можно переключаться между списком данных и аналитикой.',
        skipIfTargetMissing: true,
      },
      {
        id: 'module-actions',
        target: '[data-tour="module-actions"]',
        titleKey: 'tour.steps.moduleActions.title',
        descriptionKey: 'tour.steps.moduleActions.description',
        titleFallback: 'Быстрые действия',
        descriptionFallback: 'Обновление данных, переход в финансовый центр и добавление записи.',
      },
      {
        id: 'module-tab-core-clients',
        target: '[data-tour="module-tab-core-clients"]',
        titleKey: 'tour.steps.coreClientsTab.title',
        descriptionKey: 'tour.steps.coreClientsTab.description',
        titleFallback: 'Раздел клиентов',
        descriptionFallback:
          'Перейдите в клиентов, чтобы отправлять персональные и массовые уведомления.',
        route: CORE_MODULE_ROUTE_MATCHER,
        requiredPermissions: ['client.read'],
        autoActions: [
          {
            type: 'click',
            selector: '[data-tour="module-resource-group-people-clients"]',
            maxAttempts: 8,
            intervalMs: 130,
          },
        ],
        skipIfTargetMissing: true,
      },
      {
        id: 'module-bulk-client-notification',
        target: '[data-tour="module-bulk-client-notification"]',
        titleKey: 'tour.steps.bulkClientNotification.title',
        descriptionKey: 'tour.steps.bulkClientNotification.description',
        titleFallback: 'Массовое уведомление',
        descriptionFallback:
          'Запускает массовую отправку: каждому клиенту уходит персонализированное сообщение.',
        route: CORE_MODULE_ROUTE_MATCHER,
        requiredPermissions: ['client.write'],
        autoActions: [
          {
            type: 'click',
            selector: '[data-tour="module-tab-core-clients"]',
            maxAttempts: 8,
            intervalMs: 130,
          },
        ],
        skipIfTargetMissing: true,
      },
      {
        id: 'client-row-notify-action',
        target: '[data-tour="client-row-notify-action"]',
        titleKey: 'tour.steps.clientRowNotifyAction.title',
        descriptionKey: 'tour.steps.clientRowNotifyAction.description',
        titleFallback: 'Уведомление клиенту',
        descriptionFallback:
          'Кнопка в строке клиента открывает персональное уведомление с данными по долгам и покупкам.',
        route: CORE_MODULE_ROUTE_MATCHER,
        requiredPermissions: ['client.write'],
        autoActions: [
          {
            type: 'click',
            selector: '[data-tour="module-tab-core-clients"]',
            maxAttempts: 8,
            intervalMs: 130,
          },
        ],
        skipIfTargetMissing: true,
      },
      {
        id: 'client-notification-drawer',
        target: '[data-tour="client-notification-drawer"]',
        titleKey: 'tour.steps.clientNotificationDrawer.title',
        descriptionKey: 'tour.steps.clientNotificationDrawer.description',
        titleFallback: 'Панель уведомлений',
        descriptionFallback:
          'В боковой панели выбирается шаблон, редактируется текст и выполняется отправка в Telegram.',
        route: CORE_MODULE_ROUTE_MATCHER,
        requiredPermissions: ['client.write'],
        autoActions: [
          {
            type: 'click',
            selector: '[data-tour="client-row-notify-action"]',
            maxAttempts: 8,
            intervalMs: 130,
          },
          {
            type: 'click',
            selector: '[data-tour="module-bulk-client-notification"]',
            maxAttempts: 8,
            intervalMs: 130,
          },
        ],
        skipIfTargetMissing: true,
      },
      {
        id: 'client-notification-context',
        target: '[data-tour="client-notification-context"]',
        titleKey: 'tour.steps.clientNotificationContext.title',
        descriptionKey: 'tour.steps.clientNotificationContext.description',
        titleFallback: 'Контекст уведомления',
        descriptionFallback:
          'Показывает данные для персонализации: текущий долг, а в персональном режиме и последние покупки.',
        route: CORE_MODULE_ROUTE_MATCHER,
        requiredPermissions: ['client.write'],
        skipIfTargetMissing: true,
      },
      {
        id: 'client-notification-template-tabs',
        target: '[data-tour="client-notification-template-tabs"]',
        titleKey: 'tour.steps.clientNotificationTemplateTabs.title',
        descriptionKey: 'tour.steps.clientNotificationTemplateTabs.description',
        titleFallback: 'Шаблоны сообщений',
        descriptionFallback: 'Выбирайте тип сообщения: долг, уведомление о товаре или общий текст.',
        route: CORE_MODULE_ROUTE_MATCHER,
        requiredPermissions: ['client.write'],
        skipIfTargetMissing: true,
      },
      {
        id: 'client-notification-message-field',
        target: '[data-tour="client-notification-message-field"]',
        titleKey: 'tour.steps.clientNotificationMessageField.title',
        descriptionKey: 'tour.steps.clientNotificationMessageField.description',
        titleFallback: 'Текст сообщения',
        descriptionFallback:
          'Сообщение можно доработать вручную перед отправкой клиенту или массовой рассылкой.',
        route: CORE_MODULE_ROUTE_MATCHER,
        requiredPermissions: ['client.write'],
        skipIfTargetMissing: true,
      },
      {
        id: 'client-notification-send-button',
        target: '[data-tour="client-notification-send-button"]',
        titleKey: 'tour.steps.clientNotificationSendButton.title',
        descriptionKey: 'tour.steps.clientNotificationSendButton.description',
        titleFallback: 'Отправка уведомления',
        descriptionFallback:
          'Финальный шаг отправки сообщения в Telegram по выбранному клиенту или по списку клиентов.',
        route: CORE_MODULE_ROUTE_MATCHER,
        requiredPermissions: ['client.write'],
        skipIfTargetMissing: true,
      },
      {
        id: 'module-inventory-tools',
        target: '[data-tour="module-inventory-tools"]',
        titleKey: 'tour.steps.inventoryQuickActions.title',
        descriptionKey: 'tour.steps.inventoryQuickActions.description',
        titleFallback: 'Быстрые операции',
        descriptionFallback: 'Здесь открываются простые формы прихода, расхода и перемещения.',
        route: INVENTORY_MODULE_ROUTE_MATCHER,
        autoActions: [
          {
            type: 'click',
            selector: '[data-tour="module-resource-group-operations"]',
            maxAttempts: 8,
            intervalMs: 130,
          },
          {
            type: 'click',
            selector: '[data-tour="module-tab-inventory-movements"]',
            maxAttempts: 8,
            intervalMs: 130,
          },
        ],
        skipIfTargetMissing: true,
      },
      {
        id: 'module-resource-groups',
        target: '[data-tour="module-resource-groups"]',
        titleKey: 'tour.steps.moduleResourceGroups.title',
        descriptionKey: 'tour.steps.moduleResourceGroups.description',
        titleFallback: 'Категории данных',
        descriptionFallback: 'Данные сгруппированы по смыслу для удобной навигации.',
      },
      {
        id: 'module-resource-group-switch',
        target: '[data-tour="module-resource-group-switch"]',
        titleKey: 'tour.steps.moduleGroupSwitch.title',
        descriptionKey: 'tour.steps.moduleGroupSwitch.description',
        titleFallback: 'Группы разделов',
        descriptionFallback: 'Переключение между группами данных внутри текущего блока.',
        skipIfTargetMissing: true,
      },
      {
        id: 'module-resource-tabs',
        target: '[data-tour="module-resource-tabs"]',
        titleKey: 'tour.steps.moduleTabs.title',
        descriptionKey: 'tour.steps.moduleTabs.description',
        titleFallback: 'Внутренние разделы',
        descriptionFallback: 'Выберите конкретный раздел, с которым будете работать.',
        skipIfTargetMissing: true,
      },
      {
        id: 'module-department-filter',
        target: '[data-tour="module-department-filter"]',
        titleKey: 'tour.steps.moduleDepartmentFilter.title',
        descriptionKey: 'tour.steps.moduleDepartmentFilter.description',
        titleFallback: 'Фильтр по отделу',
        descriptionFallback: 'Ограничивает список данных выбранным отделом.',
        skipIfTargetMissing: true,
      },
      {
        id: 'module-summary-pills',
        target: '[data-tour="module-summary-pills"]',
        titleKey: 'tour.steps.moduleSummaryPills.title',
        descriptionKey: 'tour.steps.moduleSummaryPills.description',
        titleFallback: 'Короткая сводка',
        descriptionFallback: 'Показывает объём данных и текущий контекст просмотра.',
      },
      {
        id: 'module-new-record',
        target: '[data-tour="module-new-record"]',
        titleKey: 'tour.steps.moduleCreateRecord.title',
        descriptionKey: 'tour.steps.moduleCreateRecord.description',
        titleFallback: 'Новая запись',
        descriptionFallback: 'Кнопка открытия формы для добавления новой записи.',
        skipIfTargetMissing: true,
      },
      {
        id: 'module-records',
        target: '[data-tour="module-records"]',
        titleKey: 'tour.steps.moduleRecords.title',
        descriptionKey: 'tour.steps.moduleRecords.description',
        titleFallback: 'Область данных',
        descriptionFallback: 'Основной блок текущего раздела.',
      },
      {
        id: 'module-table',
        target: '[data-tour="module-table"]',
        titleKey: 'tour.steps.moduleTable.title',
        descriptionKey: 'tour.steps.moduleTable.description',
        titleFallback: 'Таблица записей',
        descriptionFallback: 'Здесь отображаются все найденные записи.',
      },
      {
        id: 'warehouses-list',
        target: '[data-tour="warehouses-list"]',
        titleKey: 'tour.steps.warehousesList.title',
        descriptionKey: 'tour.steps.warehousesList.description',
        titleFallback: 'Список складов',
        descriptionFallback: 'Здесь отображаются склады текущего отдела и их основные параметры.',
        autoActions: [
          {
            type: 'click',
            selector: '[data-tour="module-resource-group-operations"]',
            maxAttempts: 8,
            intervalMs: 130,
          },
          {
            type: 'click',
            selector: '[data-tour="module-tab-core-warehouses"]',
            maxAttempts: 8,
            intervalMs: 130,
          },
        ],
        skipIfTargetMissing: true,
      },
      {
        id: 'inventory-movements-list',
        target: '[data-tour="inventory-movements-list"]',
        titleKey: 'tour.steps.inventoryMovementsList.title',
        descriptionKey: 'tour.steps.inventoryMovementsList.description',
        titleFallback: 'Журнал движений',
        descriptionFallback: 'Здесь видны приход, расход и перемещение по складам.',
        route: INVENTORY_MODULE_ROUTE_MATCHER,
        autoActions: [
          {
            type: 'click',
            selector: '[data-tour="module-resource-group-operations"]',
            maxAttempts: 8,
            intervalMs: 130,
          },
          {
            type: 'click',
            selector: '[data-tour="module-tab-inventory-movements"]',
            maxAttempts: 8,
            intervalMs: 130,
          },
        ],
        skipIfTargetMissing: true,
      },
      {
        id: 'module-pagination',
        target: '[data-tour="module-pagination"]',
        titleKey: 'tour.steps.modulePagination.title',
        descriptionKey: 'tour.steps.modulePagination.description',
        titleFallback: 'Переключение страниц',
        descriptionFallback: 'Переход между страницами списка.',
      },
      {
        id: 'module-form-drawer',
        target: '[data-tour="module-form-drawer"]',
        titleKey: 'tour.steps.moduleFormDrawer.title',
        descriptionKey: 'tour.steps.moduleFormDrawer.description',
        titleFallback: 'Форма записи',
        descriptionFallback: 'Боковая форма для создания и изменения записи.',
        autoActions: [
          {
            type: 'click',
            selector: '[data-tour="module-new-record"]',
            maxAttempts: 8,
            intervalMs: 130,
          },
        ],
        skipIfTargetMissing: true,
      },
      {
        id: 'module-form-fields',
        target: '[data-tour="module-form-fields"]',
        titleKey: 'tour.steps.moduleFormFields.title',
        descriptionKey: 'tour.steps.moduleFormFields.description',
        titleFallback: 'Поля формы',
        descriptionFallback: 'Заполните обязательные поля перед сохранением.',
        skipIfTargetMissing: true,
      },
      {
        id: 'module-tab-core-client-debts',
        target: '[data-tour="module-tab-core-client-debts"]',
        titleKey: 'tour.steps.coreClientDebtsTab.title',
        descriptionKey: 'tour.steps.coreClientDebtsTab.description',
        titleFallback: 'Раздел долгов клиентов',
        descriptionFallback:
          'Откройте таблицу долгов, чтобы оформлять товар в долг и отслеживать задолженность.',
        route: CORE_MODULE_ROUTE_MATCHER,
        requiredPermissions: ['client_debt.read'],
        autoActions: [
          {
            type: 'click',
            selector: '[data-tour="client-notification-close-button"]',
            maxAttempts: 6,
            intervalMs: 120,
          },
          {
            type: 'click',
            selector: '[data-tour="module-resource-group-people-clients"]',
            maxAttempts: 8,
            intervalMs: 130,
          },
        ],
        skipIfTargetMissing: true,
      },
      {
        id: 'client-debt-item-key-field',
        target: '[data-tour="client-debt-item-key-field"]',
        titleKey: 'tour.steps.clientDebtItemKeyField.title',
        descriptionKey: 'tour.steps.clientDebtItemKeyField.description',
        titleFallback: 'Товар для долга',
        descriptionFallback:
          'Выберите товар из текущего отдела. Позиция подтягивается из доступной номенклатуры.',
        route: CORE_MODULE_ROUTE_MATCHER,
        requiredPermissions: ['client_debt.write', 'client_debt.create'],
        autoActions: [
          {
            type: 'click',
            selector: '[data-tour="module-tab-core-client-debts"]',
            maxAttempts: 8,
            intervalMs: 130,
          },
          {
            type: 'click',
            selector: '[data-tour="module-new-record"]',
            maxAttempts: 8,
            intervalMs: 130,
          },
        ],
        skipIfTargetMissing: true,
      },
      {
        id: 'client-debt-due-on-field',
        target: '[data-tour="client-debt-due-on-field"]',
        titleKey: 'tour.steps.clientDebtDueOnField.title',
        descriptionKey: 'tour.steps.clientDebtDueOnField.description',
        titleFallback: 'Срок погашения',
        descriptionFallback:
          'Укажите дату погашения не раньше даты выдачи долга. Изменения по долгам сохраняются в аудите.',
        route: CORE_MODULE_ROUTE_MATCHER,
        requiredPermissions: ['client_debt.write', 'client_debt.create'],
        skipIfTargetMissing: true,
      },
      {
        id: 'module-audit-drawer',
        target: '[data-tour="module-audit-drawer"]',
        titleKey: 'tour.steps.moduleAuditDrawer.title',
        descriptionKey: 'tour.steps.moduleAuditDrawer.description',
        titleFallback: 'История изменений',
        descriptionFallback: 'В этом окне можно посмотреть, кто и когда менял запись.',
        autoActions: [
          {
            type: 'click',
            selector: '[data-tour="module-open-audit-drawer"]',
            maxAttempts: 8,
            intervalMs: 130,
          },
        ],
        skipIfTargetMissing: true,
      },
      {
        id: 'module-audit-history',
        target: '[data-tour="module-audit-history"]',
        titleKey: 'tour.steps.moduleAuditHistory.title',
        descriptionKey: 'tour.steps.moduleAuditHistory.description',
        titleFallback: 'Лента изменений',
        descriptionFallback: 'Показывает историю шаг за шагом с деталями.',
        autoActions: [
          {
            type: 'click',
            selector: '[data-tour="module-open-audit-drawer"]',
            maxAttempts: 8,
            intervalMs: 130,
          },
        ],
        skipIfTargetMissing: true,
      },
      {
        id: 'module-subdepartments',
        target: '[data-tour="module-subdepartments-card"]',
        titleKey: 'tour.steps.moduleSubdepartments.title',
        descriptionKey: 'tour.steps.moduleSubdepartments.description',
        titleFallback: 'Дочерние отделы',
        descriptionFallback: 'Быстрый переход в дочерние подразделения для работы с их данными.',
        skipIfTargetMissing: true,
      },
    ],
  },
  {
    id: 'settings-tour',
    version: 3,
    titleKey: 'tour.tours.settings.title',
    descriptionKey: 'tour.tours.settings.description',
    titleFallback: 'Тур по настройкам',
    descriptionFallback: 'Покажет профиль, безопасность и управление отделами.',
    route: '/settings',
    priority: 110,
    steps: [
      {
        id: 'settings-tabs',
        target: '[data-tour="settings-tabs"]',
        titleKey: 'tour.steps.settingsTabs.title',
        descriptionKey: 'tour.steps.settingsTabs.description',
        titleFallback: 'Разделы настроек',
        descriptionFallback: 'Здесь переключаются основные блоки страницы настроек.',
      },
      {
        id: 'settings-account-profile',
        target: '[data-tour="settings-account-profile"]',
        titleKey: 'tour.steps.settingsProfile.title',
        descriptionKey: 'tour.steps.settingsProfile.description',
        titleFallback: 'Профиль',
        descriptionFallback: 'Основные данные пользователя и кнопка редактирования.',
        autoActions: [
          {
            type: 'click',
            selector: '[data-tour="settings-tab-account"]',
            maxAttempts: 6,
            intervalMs: 120,
          },
        ],
      },
      {
        id: 'settings-account-security',
        target: '[data-tour="settings-account-security"]',
        titleKey: 'tour.steps.settingsSecurity.title',
        descriptionKey: 'tour.steps.settingsSecurity.description',
        titleFallback: 'Безопасность',
        descriptionFallback: 'Управление настройками пароля и безопасностью учётной записи.',
      },
      {
        id: 'settings-departments-manager',
        target: '[data-tour="settings-departments-manager"]',
        titleKey: 'tour.steps.settingsDepartments.title',
        descriptionKey: 'tour.steps.settingsDepartments.description',
        titleFallback: 'Управление отделами',
        descriptionFallback: 'Основной блок управления структурой отделов.',
        autoActions: [
          {
            type: 'click',
            selector: '[data-tour="settings-tab-departments"]',
            maxAttempts: 8,
            intervalMs: 130,
          },
        ],
        skipIfTargetMissing: true,
      },
      {
        id: 'settings-departments-filters',
        target: '[data-tour="settings-departments-filters"]',
        titleKey: 'tour.steps.settingsDepartmentFilters.title',
        descriptionKey: 'tour.steps.settingsDepartmentFilters.description',
        titleFallback: 'Поиск и фильтры',
        descriptionFallback: 'Поиск по отделам и фильтры для быстрой навигации.',
        skipIfTargetMissing: true,
      },
      {
        id: 'settings-departments-tree',
        target: '[data-tour="settings-departments-tree"]',
        titleKey: 'tour.steps.settingsDepartmentTree.title',
        descriptionKey: 'tour.steps.settingsDepartmentTree.description',
        titleFallback: 'Структура отделов',
        descriptionFallback: 'Список отделов с иерархией и быстрым выбором.',
        skipIfTargetMissing: true,
      },
      {
        id: 'settings-department-details',
        target: '[data-tour="settings-department-details"]',
        titleKey: 'tour.steps.settingsDepartmentDetails.title',
        descriptionKey: 'tour.steps.settingsDepartmentDetails.description',
        titleFallback: 'Детали отдела',
        descriptionFallback: 'Информация о выбранном отделе и доступные действия.',
        skipIfTargetMissing: true,
      },
      {
        id: 'settings-account-drawer',
        target: '[data-tour="settings-account-drawer"]',
        titleKey: 'tour.steps.settingsAccountDrawer.title',
        descriptionKey: 'tour.steps.settingsAccountDrawer.description',
        titleFallback: 'Форма профиля',
        descriptionFallback: 'Боковая форма для обновления личных данных и пароля.',
        autoActions: [
          {
            type: 'click',
            selector: '[data-tour="settings-open-account-drawer"]',
            maxAttempts: 8,
            intervalMs: 130,
          },
        ],
        skipIfTargetMissing: true,
      },
      {
        id: 'settings-department-drawer',
        target: '[data-tour="settings-department-drawer"]',
        titleKey: 'tour.steps.settingsDepartmentDrawer.title',
        descriptionKey: 'tour.steps.settingsDepartmentDrawer.description',
        titleFallback: 'Форма отдела',
        descriptionFallback: 'Боковая форма для создания и изменения отдела.',
        autoActions: [
          {
            type: 'click',
            selector: '[data-tour="settings-open-department-drawer-edit"]',
            maxAttempts: 8,
            intervalMs: 130,
          },
          {
            type: 'click',
            selector: '[data-tour="settings-open-department-drawer-create"]',
            maxAttempts: 8,
            intervalMs: 130,
          },
        ],
        skipIfTargetMissing: true,
      },
      {
        id: 'settings-department-form-main',
        target: '[data-tour="settings-department-form-main"]',
        titleKey: 'tour.steps.settingsDepartmentFormMain.title',
        descriptionKey: 'tour.steps.settingsDepartmentFormMain.description',
        titleFallback: 'Основные поля отдела',
        descriptionFallback: 'Главные поля, которые заполняются для нового отдела.',
        skipIfTargetMissing: true,
      },
      {
        id: 'settings-department-form-icon',
        target: '[data-tour="settings-department-form-icon"]',
        titleKey: 'tour.steps.settingsDepartmentFormIcon.title',
        descriptionKey: 'tour.steps.settingsDepartmentFormIcon.description',
        titleFallback: 'Выбор иконки',
        descriptionFallback: 'Выберите визуальную иконку для отдела.',
        skipIfTargetMissing: true,
      },
      {
        id: 'settings-department-form-responsible',
        target: '[data-tour="settings-department-form-responsible"]',
        titleKey: 'tour.steps.settingsDepartmentFormResponsible.title',
        descriptionKey: 'tour.steps.settingsDepartmentFormResponsible.description',
        titleFallback: 'Ответственный сотрудник',
        descriptionFallback: 'Назначьте сотрудника, который отвечает за отдел.',
        skipIfTargetMissing: true,
      },
    ],
  },
  {
    id: 'roles-tour',
    version: 2,
    titleKey: 'tour.tours.roles.title',
    descriptionKey: 'tour.tours.roles.description',
    titleFallback: 'Тур по ролям',
    descriptionFallback: 'Пошаговый обзор управления ролями и назначениями.',
    route: '/roles',
    priority: 110,
    isAvailable: (context) => canAccessRoleManagement(context.roles, context.permissions),
    steps: [
      {
        id: 'roles-hero',
        target: '[data-tour="roles-hero"]',
        titleKey: 'tour.steps.rolesHero.title',
        descriptionKey: 'tour.steps.rolesHero.description',
        titleFallback: 'Общая сводка',
        descriptionFallback: 'Краткие показатели по ролям и доступам.',
      },
      {
        id: 'roles-list',
        target: '[data-tour="roles-list"]',
        titleKey: 'tour.steps.rolesList.title',
        descriptionKey: 'tour.steps.rolesList.description',
        titleFallback: 'Список ролей',
        descriptionFallback: 'Выберите роль для просмотра или редактирования.',
      },
      {
        id: 'roles-search',
        target: '[data-tour="roles-search"]',
        titleKey: 'tour.steps.rolesSearch.title',
        descriptionKey: 'tour.steps.rolesSearch.description',
        titleFallback: 'Поиск роли',
        descriptionFallback: 'Быстрый поиск по названию и коду роли.',
      },
      {
        id: 'roles-workspace',
        target: '[data-tour="roles-workspace"]',
        titleKey: 'tour.steps.rolesWorkspace.title',
        descriptionKey: 'tour.steps.rolesWorkspace.description',
        titleFallback: 'Рабочая зона роли',
        descriptionFallback: 'Детали выбранной роли и основные действия.',
      },
      {
        id: 'roles-workspace-actions',
        target: '[data-tour="roles-workspace-actions"]',
        titleKey: 'tour.steps.rolesWorkspaceActions.title',
        descriptionKey: 'tour.steps.rolesWorkspaceActions.description',
        titleFallback: 'Действия с ролью',
        descriptionFallback: 'Кнопки редактирования, обновления и назначения сотрудников.',
      },
      {
        id: 'roles-permissions-preview',
        target: '[data-tour="roles-permissions-preview"]',
        titleKey: 'tour.steps.rolesPermissionsPreview.title',
        descriptionKey: 'tour.steps.rolesPermissionsPreview.description',
        titleFallback: 'Текущие доступы роли',
        descriptionFallback: 'Список доступов, которые сейчас включены у роли.',
      },
      {
        id: 'roles-editor-drawer',
        target: '[data-tour="roles-editor-drawer"]',
        titleKey: 'tour.steps.rolesEditorDrawer.title',
        descriptionKey: 'tour.steps.rolesEditorDrawer.description',
        titleFallback: 'Форма роли',
        descriptionFallback: 'Боковая форма для создания и изменения роли.',
        autoActions: [
          {
            type: 'click',
            selector: '[data-tour="roles-open-editor-drawer-edit"]',
            maxAttempts: 8,
            intervalMs: 130,
          },
          {
            type: 'click',
            selector: '[data-tour="roles-open-editor-drawer-create"]',
            maxAttempts: 8,
            intervalMs: 130,
          },
        ],
        skipIfTargetMissing: true,
      },
      {
        id: 'roles-editor-main-fields',
        target: '[data-tour="roles-editor-main-fields"]',
        titleKey: 'tour.steps.rolesEditorMainFields.title',
        descriptionKey: 'tour.steps.rolesEditorMainFields.description',
        titleFallback: 'Основные поля роли',
        descriptionFallback: 'Название, код и описание роли.',
        skipIfTargetMissing: true,
      },
      {
        id: 'roles-editor-permissions',
        target: '[data-tour="roles-editor-permissions"]',
        titleKey: 'tour.steps.rolesEditorPermissions.title',
        descriptionKey: 'tour.steps.rolesEditorPermissions.description',
        titleFallback: 'Настройка доступов',
        descriptionFallback: 'Выбор доступов, которые получат сотрудники с этой ролью.',
        skipIfTargetMissing: true,
      },
      {
        id: 'roles-assignments-drawer',
        target: '[data-tour="roles-assignments-drawer"]',
        titleKey: 'tour.steps.rolesAssignmentsDrawer.title',
        descriptionKey: 'tour.steps.rolesAssignmentsDrawer.description',
        titleFallback: 'Назначение сотрудников',
        descriptionFallback: 'Боковая панель для добавления и снятия роли у сотрудников.',
        autoActions: [
          {
            type: 'click',
            selector: '[data-tour="roles-open-assignments-drawer"]',
            maxAttempts: 8,
            intervalMs: 130,
          },
        ],
        skipIfTargetMissing: true,
      },
      {
        id: 'roles-assignments-search',
        target: '[data-tour="roles-assignments-search"]',
        titleKey: 'tour.steps.rolesAssignmentsSearch.title',
        descriptionKey: 'tour.steps.rolesAssignmentsSearch.description',
        titleFallback: 'Поиск сотрудника',
        descriptionFallback: 'Поиск сотрудника по имени, логину или почте.',
        skipIfTargetMissing: true,
      },
      {
        id: 'roles-assignments-list',
        target: '[data-tour="roles-assignments-list"]',
        titleKey: 'tour.steps.rolesAssignmentsList.title',
        descriptionKey: 'tour.steps.rolesAssignmentsList.description',
        titleFallback: 'Список сотрудников',
        descriptionFallback: 'Здесь вы назначаете или снимаете роль у сотрудников.',
        skipIfTargetMissing: true,
      },
    ],
  },
  {
    id: 'audit-tour',
    version: 2,
    titleKey: 'tour.tours.audit.title',
    descriptionKey: 'tour.tours.audit.description',
    titleFallback: 'Тур по истории изменений',
    descriptionFallback: 'Покажет фильтрацию, список изменений и подробный просмотр.',
    route: '/audit',
    priority: 110,
    isAvailable: (context) => canReadAuditLogs(context.roles, context.permissions),
    steps: [
      {
        id: 'audit-hero',
        target: '[data-tour="audit-hero"]',
        titleKey: 'tour.steps.auditHero.title',
        descriptionKey: 'tour.steps.auditHero.description',
        titleFallback: 'Заголовок раздела',
        descriptionFallback: 'Кратко о разделе и общем количестве записей.',
      },
      {
        id: 'audit-filters',
        target: '[data-tour="audit-filters"]',
        titleKey: 'tour.steps.auditFilters.title',
        descriptionKey: 'tour.steps.auditFilters.description',
        titleFallback: 'Фильтры',
        descriptionFallback: 'Здесь настраивается выборка изменений.',
      },
      {
        id: 'audit-search',
        target: '[data-tour="audit-search"]',
        titleKey: 'tour.steps.auditSearch.title',
        descriptionKey: 'tour.steps.auditSearch.description',
        titleFallback: 'Поиск',
        descriptionFallback: 'Быстрый поиск по пользователю, таблице и действию.',
      },
      {
        id: 'audit-feed',
        target: '[data-tour="audit-feed"]',
        titleKey: 'tour.steps.auditFeed.title',
        descriptionKey: 'tour.steps.auditFeed.description',
        titleFallback: 'Лента изменений',
        descriptionFallback: 'Основной список всех найденных изменений.',
      },
      {
        id: 'audit-main-table',
        target: '[data-tour="audit-main-table"]',
        titleKey: 'tour.steps.auditMainTable.title',
        descriptionKey: 'tour.steps.auditMainTable.description',
        titleFallback: 'Таблица истории',
        descriptionFallback: 'Строки с временем, действием, автором и изменёнными полями.',
      },
      {
        id: 'audit-pagination',
        target: '[data-tour="audit-pagination"]',
        titleKey: 'tour.steps.auditPagination.title',
        descriptionKey: 'tour.steps.auditPagination.description',
        titleFallback: 'Переключение страниц',
        descriptionFallback: 'Переход по страницам истории изменений.',
      },
      {
        id: 'audit-details-drawer',
        target: '[data-tour="audit-details-drawer"]',
        titleKey: 'tour.steps.auditDetailsDrawer.title',
        descriptionKey: 'tour.steps.auditDetailsDrawer.description',
        titleFallback: 'Детали изменения',
        descriptionFallback: 'Боковая панель с полной информацией по выбранной записи.',
        autoActions: [
          {
            type: 'click',
            selector: '[data-tour="audit-open-details"]',
            maxAttempts: 8,
            intervalMs: 130,
          },
        ],
        skipIfTargetMissing: true,
      },
      {
        id: 'audit-details-snapshots',
        target: '[data-tour="audit-details-snapshots"]',
        titleKey: 'tour.steps.auditDetailsSnapshots.title',
        descriptionKey: 'tour.steps.auditDetailsSnapshots.description',
        titleFallback: 'До и после',
        descriptionFallback: 'Сравнение состояния данных до и после изменения.',
        skipIfTargetMissing: true,
      },
    ],
  },
  {
    id: 'not-found-tour',
    version: 1,
    titleKey: 'tour.tours.notFound.title',
    descriptionKey: 'tour.tours.notFound.description',
    titleFallback: 'Тур по странице 404',
    descriptionFallback: 'Кратко покажет, как вернуться к рабочим разделам.',
    route: NOT_FOUND_ROUTE_MATCHER,
    priority: 40,
    autoStart: true,
    allowUnauthenticated: true,
    steps: [
      {
        id: 'notfound-showcase',
        target: '[data-tour="notfound-showcase"]',
        titleKey: 'tour.steps.notFoundShowcase.title',
        descriptionKey: 'tour.steps.notFoundShowcase.description',
        titleFallback: 'Подсказки',
        descriptionFallback: 'Здесь указано, почему могла открыться эта страница.',
        skipIfTargetMissing: true,
      },
      {
        id: 'notfound-card',
        target: '[data-tour="notfound-card"]',
        titleKey: 'tour.steps.notFoundCard.title',
        descriptionKey: 'tour.steps.notFoundCard.description',
        titleFallback: 'Страница 404',
        descriptionFallback: 'Основная информация о том, что страница не найдена.',
      },
      {
        id: 'notfound-back',
        target: '[data-tour="notfound-back"]',
        titleKey: 'tour.steps.notFoundBack.title',
        descriptionKey: 'tour.steps.notFoundBack.description',
        titleFallback: 'Кнопка возврата',
        descriptionFallback: 'Используйте эту кнопку, чтобы вернуться на рабочую страницу.',
      },
    ],
  },
];
