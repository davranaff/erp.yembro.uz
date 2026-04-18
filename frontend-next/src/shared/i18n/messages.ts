import type { Messages } from './types';

export const LOCALES = ['ru', 'uz', 'en'] as const;

export const messages: Messages = {
  'app.brand': {
    ru: 'Yembro Next',
    uz: 'Yembro Next',
    en: 'Yembro Next',
  },
  'login.title': {
    ru: 'Вход в систему',
    uz: 'Tizimga kirish',
    en: 'Sign in',
  },
  'login.username': {
    ru: 'Логин',
    uz: 'Login',
    en: 'Username',
  },
  'login.password': {
    ru: 'Пароль',
    uz: 'Parol',
    en: 'Password',
  },
  'login.submit': {
    ru: 'Войти',
    uz: 'Kirish',
    en: 'Sign in',
  },
  'login.submitting': {
    ru: 'Вход…',
    uz: 'Kirilmoqda…',
    en: 'Signing in…',
  },
  'login.hint': {
    ru: 'Используйте учётные данные из основного приложения',
    uz: 'Asosiy ilovadagi hisob maʼlumotlaridan foydalaning',
    en: 'Use credentials from the main application',
  },
  'login.error': {
    ru: 'Не удалось войти: {message}',
    uz: 'Kirish amalga oshmadi: {message}',
    en: 'Sign-in failed: {message}',
  },
  'nav.dashboard': { ru: 'Дашборд', uz: 'Boshqaruv paneli', en: 'Dashboard' },
  'nav.clients': { ru: 'Клиенты', uz: 'Mijozlar', en: 'Clients' },
  'nav.finance': { ru: 'Финансы', uz: 'Moliya', en: 'Finance' },
  'nav.hr': { ru: 'Персонал', uz: 'Xodimlar', en: 'HR' },
  'nav.inventory': { ru: 'Склад', uz: 'Omborlar', en: 'Inventory' },
  'nav.settings': { ru: 'Настройки', uz: 'Sozlamalar', en: 'Settings' },
  'nav.logout': { ru: 'Выход', uz: 'Chiqish', en: 'Log out' },

  'shell.search': { ru: 'Поиск или команда… ⌘K', uz: 'Qidiruv yoki buyruq… ⌘K', en: 'Search or run… ⌘K' },
  'shell.commandPalette': { ru: 'Панель команд', uz: 'Buyruqlar paneli', en: 'Command palette' },
  'shell.empty': { ru: 'Ничего не найдено', uz: 'Hech narsa topilmadi', en: 'No results' },

  'dashboard.title': { ru: 'Главный экран', uz: 'Asosiy ekran', en: 'Overview' },
  'dashboard.period': { ru: 'Период', uz: 'Davr', en: 'Period' },
  'dashboard.loading': { ru: 'Загрузка…', uz: 'Yuklanmoqda…', en: 'Loading…' },
  'dashboard.empty': { ru: 'Нет данных за выбранный период', uz: 'Tanlangan davr uchun maʼlumot yoʻq', en: 'No data for the selected period' },
  'dashboard.noPermission': { ru: 'Нет доступа к дашборду', uz: 'Dashboardga ruxsat yoʻq', en: 'No access to the dashboard' },

  'clients.title': { ru: 'Клиенты', uz: 'Mijozlar', en: 'Clients' },
  'clients.empty': { ru: 'Клиенты не найдены', uz: 'Mijozlar topilmadi', en: 'No clients found' },
  'clients.search': { ru: 'Поиск клиентов…', uz: 'Mijozlar qidiruvi…', en: 'Search clients…' },
  'clients.column.name': { ru: 'Название', uz: 'Nomi', en: 'Name' },
  'clients.column.phone': { ru: 'Телефон', uz: 'Telefon', en: 'Phone' },
  'clients.column.email': { ru: 'Email', uz: 'Email', en: 'Email' },
  'clients.column.type': { ru: 'Тип', uz: 'Turi', en: 'Type' },
  'clients.column.balance': { ru: 'Баланс', uz: 'Balans', en: 'Balance' },
  'clients.inspector.none': { ru: 'Выберите клиента слева', uz: 'Chap tomondan mijoz tanlang', en: 'Select a client from the list' },

  'common.yes': { ru: 'Да', uz: 'Ha', en: 'Yes' },
  'common.no': { ru: 'Нет', uz: 'Yoʻq', en: 'No' },
  'common.save': { ru: 'Сохранить', uz: 'Saqlash', en: 'Save' },
  'common.cancel': { ru: 'Отмена', uz: 'Bekor qilish', en: 'Cancel' },
  'common.create': { ru: 'Создать', uz: 'Yaratish', en: 'Create' },
  'common.edit': { ru: 'Изменить', uz: 'Tahrirlash', en: 'Edit' },
  'common.delete': { ru: 'Удалить', uz: 'Oʻchirish', en: 'Delete' },
  'common.refresh': { ru: 'Обновить', uz: 'Yangilash', en: 'Refresh' },
  'common.error': { ru: 'Ошибка', uz: 'Xato', en: 'Error' },
  'common.retry': { ru: 'Повторить', uz: 'Qayta urinish', en: 'Retry' },
  'common.close': { ru: 'Закрыть', uz: 'Yopish', en: 'Close' },

  'kbd.cmdK': { ru: '⌘K', uz: '⌘K', en: '⌘K' },
  'kbd.esc': { ru: 'Esc', uz: 'Esc', en: 'Esc' },
};
