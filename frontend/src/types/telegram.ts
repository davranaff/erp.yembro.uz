/**
 * Shared типы для window.Telegram.WebApp.
 *
 * Используем минимальное подмножество API: загружать @types/telegram-web-app
 * ради ~20 полей оверкилл. Расширяем по мере необходимости.
 */

export interface TgInset {
  top: number;
  bottom: number;
  left: number;
  right: number;
}

export interface TgWebApp {
  initData?: string;
  version?: string;
  isFullscreen?: boolean;
  safeAreaInset?: TgInset;
  contentSafeAreaInset?: TgInset;
  ready?: () => void;
  expand?: () => void;
  /** Bot API 8.0+. На desktop / старых клиентах метода может не быть. */
  requestFullscreen?: () => void;
  /** Bot API 8.0+. Отключает iOS swipe-down (предотвращает случайное сворачивание). */
  disableVerticalSwipes?: () => void;
  isVersionAtLeast?: (v: string) => boolean;
  onEvent?: (event: string, cb: () => void) => void;
  offEvent?: (event: string, cb: () => void) => void;
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TgWebApp };
  }
}

export {};
