import type { CrudFieldMeta, CrudRecord } from '@/shared/api/backend-crud';
import type { BackendModuleConfig, BackendResourceConfig } from '@/shared/workspace';

export type ClientNotificationTemplateKey = 'debt_reminder' | 'product_alert' | 'general_notice';

export const EMPTY_AUTH_LIST: string[] = [];
export const EMPTY_RESOURCE_LIST: BackendResourceConfig[] = [];
export const EMPTY_FIELD_LIST: CrudFieldMeta[] = [];
export const EMPTY_RECORD_LIST: CrudRecord[] = [];

export const getWorkspaceModuleConfig = (
  moduleMap: Record<string, BackendModuleConfig>,
  moduleKey: string,
): BackendModuleConfig | null =>
  moduleKey && Object.prototype.hasOwnProperty.call(moduleMap, moduleKey)
    ? moduleMap[moduleKey]
    : null;

export const CLIENT_NOTIFICATION_FALLBACK_TEMPLATES: Array<{
  key: ClientNotificationTemplateKey;
  title: string;
  description: string;
  message: string;
}> = [
  {
    key: 'debt_reminder',
    title: 'Qarz eslatmasi',
    description: 'Qarz bo‘yicha eslatma yuborish.',
    message:
      "Assalomu alaykum. Sizda ochiq qarzdorlik mavjud. To'lov muddatini aniqlashtirish uchun biz bilan bog'laning.",
  },
  {
    key: 'product_alert',
    title: "Tovar bo'yicha ogohlantirish",
    description: 'So‘nggi xarid asosida taklif yuborish.',
    message:
      "Assalomu alaykum. Siz uchun bo'limda yangi takliflar mavjud. Zarur hajm bo'lsa, javob yozing.",
  },
  {
    key: 'general_notice',
    title: 'Umumiy xabar',
    description: 'Ixtiyoriy shaxsiy xabar yuborish.',
    message: 'Assalomu alaykum. Siz uchun shaxsiy xabar.',
  },
];
