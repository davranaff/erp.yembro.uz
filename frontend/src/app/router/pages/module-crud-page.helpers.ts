import type { CrudFieldMeta, CrudFieldReference, CrudRecord } from '@/shared/api/backend-crud';
import type { InventoryItemType } from '@/shared/api/inventory';
import type { Language } from '@/shared/i18n/types';
import { getReadableReferenceLabel } from '@/shared/lib/reference-label';
import { isValidUuid } from '@/shared/lib/uuid';

export type FormValues = Record<string, string | boolean | string[]>;
export type FormErrors = Record<string, string>;

/**
 * Per-language strings stored inline in the ResourceUiConfig. Used for
 * field helpers, section titles, and validation error messages instead
 * of full i18n-key indirection — keeps the resource config self-contained.
 */
export type LocalizedText = { ru: string; uz: string; en: string };

export function resolveLocalizedText(value: string | LocalizedText, language: Language): string {
  if (typeof value === 'string') {
    return value;
  }
  return value[language] || value.ru;
}

export type EnumOption = { value: string; label: string | LocalizedText };

/**
 * Shared labels for enum values that appear across multiple resources
 * (status codes, quality grades, transaction types, etc.). Exposed so
 * each resource's `fieldEnums` entry can reuse the same translations.
 */
export const ENUM_LABELS = {
  pending: { ru: 'Ожидает проверки', uz: 'Tekshiruv kutilmoqda', en: 'Pending' },
  passed: { ru: 'Прошёл', uz: 'O‘tdi', en: 'Passed' },
  failed: { ru: 'Не прошёл', uz: 'O‘tmadi', en: 'Failed' },
  open: { ru: 'Открыт', uz: 'Ochiq', en: 'Open' },
  partially_paid: { ru: 'Частично оплачен', uz: 'Qisman to‘langan', en: 'Partially paid' },
  closed: { ru: 'Закрыт', uz: 'Yopilgan', en: 'Closed' },
  cancelled: { ru: 'Отменён', uz: 'Bekor qilingan', en: 'Cancelled' },
  draft: { ru: 'Черновик', uz: 'Qoralama', en: 'Draft' },
  posted: { ru: 'Проведён', uz: 'O‘tkazilgan', en: 'Posted' },
  reversed: { ru: 'Сторнирован', uz: 'Storno qilingan', en: 'Reversed' },
  finalized: { ru: 'Завершён', uz: 'Yakunlangan', en: 'Finalized' },
  reconciled: { ru: 'Закрыт (сверено)', uz: 'Yopilgan', en: 'Reconciled' },
  active: { ru: 'Активен', uz: 'Faol', en: 'Active' },
  completed: { ru: 'Завершён', uz: 'Tugatilgan', en: 'Completed' },
  sent: { ru: 'Отправлено', uz: 'Jo‘natilgan', en: 'Sent' },
  received: { ru: 'Принято', uz: 'Qabul qilindi', en: 'Received' },
  discrepancy: { ru: 'Расхождение', uz: 'Nomuvofiqlik', en: 'Discrepancy' },
  factory: { ru: 'Из фабрики', uz: 'Fabrikadan', en: 'From factory' },
  external: { ru: 'Внешний поставщик', uz: 'Tashqi yetkazib beruvchi', en: 'External supplier' },
  first: { ru: '1 сорт', uz: '1-nav', en: '1st grade' },
  second: { ru: '2 сорт', uz: '2-nav', en: '2nd grade' },
  mixed: { ru: 'Смешанный', uz: 'Aralash', en: 'Mixed' },
  byproduct: { ru: 'Субпродукт', uz: 'Yon mahsulot', en: 'By-product' },
  premium: { ru: 'Премиум', uz: 'Premium', en: 'Premium' },
  rejected: { ru: 'Отбраковано', uz: 'Brak', en: 'Rejected' },
  large: { ru: 'Крупные', uz: 'Yirik', en: 'Large' },
  medium: { ru: 'Средние', uz: 'O‘rta', en: 'Medium' },
  small: { ru: 'Мелкие', uz: 'Mayda', en: 'Small' },
  defective: { ru: 'Брак', uz: 'Brak', en: 'Defective' },
  income: { ru: 'Приход', uz: 'Kirim', en: 'Income' },
  expense: { ru: 'Расход', uz: 'Chiqim', en: 'Expense' },
  transfer_in: { ru: 'Входящий перевод', uz: 'Kiruvchi ko‘chirish', en: 'Transfer in' },
  transfer_out: { ru: 'Исходящий перевод', uz: 'Chiquvchi ko‘chirish', en: 'Transfer out' },
  adjustment: { ru: 'Корректировка', uz: 'Tuzatish', en: 'Adjustment' },
  egg: { ru: 'Яйца', uz: 'Tuxumlar', en: 'Eggs' },
  chick: { ru: 'Птенцы', uz: 'Jo‘jalar', en: 'Chicks' },
  feed: { ru: 'Корм', uz: 'Em', en: 'Feed' },
  feed_raw: { ru: 'Сырьё для корма', uz: 'Em xomashyosi', en: 'Feed raw material' },
  medicine: { ru: 'Лекарства', uz: 'Dorilar', en: 'Medicine' },
  semi_product: { ru: 'Полуфабрикаты', uz: 'Yarim tayyor mahsulotlar', en: 'Semi-products' },
  incoming: { ru: 'Приход', uz: 'Kirim', en: 'Incoming' },
  outgoing: { ru: 'Расход', uz: 'Chiqim', en: 'Outgoing' },
  adjustment_in: { ru: 'Корректировка +', uz: 'Tuzatish +', en: 'Adjustment in' },
  adjustment_out: { ru: 'Корректировка -', uz: 'Tuzatish -', en: 'Adjustment out' },
  cash: { ru: 'Наличные', uz: 'Naqd', en: 'Cash' },
  bank: { ru: 'Банк', uz: 'Bank', en: 'Bank' },
  card: { ru: 'Карта', uz: 'Karta', en: 'Card' },
  transfer: { ru: 'Перевод', uz: 'Ko‘chirish', en: 'Transfer' },
  offset: { ru: 'Взаимозачёт', uz: 'O‘zaro hisob', en: 'Offset' },
  other: { ru: 'Другое', uz: 'Boshqa', en: 'Other' },
} as const satisfies Record<string, LocalizedText>;

export function enumOptions(values: readonly (keyof typeof ENUM_LABELS)[]): EnumOption[] {
  return values.map((value) => ({ value, label: ENUM_LABELS[value] }));
}

export type SubmitMode = 'create' | 'update';
export type ModuleViewMode = 'records' | 'stats';
export type ResourceCategoryGroupId =
  | 'finance'
  | 'people_clients'
  | 'warehouse'
  | 'operations'
  | 'catalogs'
  | 'analytics';
export type ResourceDetailPanelKey = 'debt_summary' | 'flock_kpi' | 'advance_balance';
export type ResourceUiConfig = {
  formOrder?: string[];
  tableOrder?: string[];
  hiddenFields?: string[];
  /**
   * Fields hidden from the create/edit form but still shown in the
   * records table. Use for data that's owned by downstream events —
   * e.g. receipt acknowledgement on shipments: `received_quantity`,
   * `acknowledged_at`, `acknowledged_by`, `status` are set by the
   * acknowledge dialog and have no meaning at shipment creation.
   */
  formHiddenFields?: string[];
  hideDepartmentFieldWhenScoped?: boolean;
  hideOrganizationFieldWhenScoped?: boolean;
  detailPanelKey?: ResourceDetailPanelKey;
  /**
   * When true, the resource is treated as system-generated: "New record",
   * Edit and Delete are suppressed in the UI. Useful for read-only
   * tables that are upserted by Taskiq jobs and must not be hand-edited.
   */
  readOnly?: boolean;
  /**
   * Short helper line shown under the input to explain non-obvious fields.
   * Values can be a plain string (treated as pre-localized) or a
   * LocalizedText object with ru/uz/en variants.
   */
  fieldHelpers?: Record<string, string | LocalizedText>;
  /**
   * Enum-style fields that should render as a select instead of a free
   * text input. Keys are field names; values are the allowed options
   * (value is sent to the backend, label is shown to the user). Use the
   * `enumOptions([...])` helper with keys from `ENUM_LABELS` to keep
   * labels consistent across resources.
   */
  fieldEnums?: Record<string, EnumOption[]>;
  /**
   * Groups form fields under section headers. Fields not listed in any
   * section are rendered as a tail group without a title. Titles accept
   * a plain string or a LocalizedText object.
   */
  formSections?: Array<{ title: string | LocalizedText; fields: string[] }>;
  /**
   * Cross-field validation executed in handleSubmit after buildPayload.
   * Returns a map of { fieldName: errorMessage } to merge into formErrors.
   * Messages can be plain strings or LocalizedText objects.
   */
  crossFieldValidator?: (values: FormValues) => Record<string, string | LocalizedText>;
};
export type DepartmentRecord = CrudRecord & {
  id?: string;
  name?: string;
  code?: string;
  module_key?: string;
  organization_id?: string;
  parent_department_id?: string | null;
};
export type AuditSnapshot = Record<string, unknown>;
export type ResourceCategoryCandidate = {
  key: string;
  permissionPrefix: string;
  moduleKey?: string;
};

export const EMPTY_TEXT = '';
export const MASKED_PASSWORD_VALUE = '********';
export const FORM_HIDDEN_FIELDS = new Set([
  'is_active',
  // measurement_unit_id is the FK mirror of the `unit` string column —
  // a Postgres trigger keeps them in sync. Exposing both in the form
  // would force operators to pick the unit twice; we only render the
  // `unit` field (which uses the MeasurementUnitSelect dropdown).
  'measurement_unit_id',
]);
const MODULE_DEFAULT_INVENTORY_ITEM_TYPES: Record<string, InventoryItemType> = {
  egg: 'egg',
  incubation: 'chick',
  factory: 'chick',
  feed: 'feed',
  medicine: 'medicine',
  slaughter: 'semi_product',
};
const FINANCE_RESOURCE_PERMISSION_PREFIXES = new Set([
  'expense_category',
  'expense',
  'cash_account',
  'cash_transaction',
  'client_debt',
  'supplier_debt',
  'debt_payment',
  'currency',
]);
const PEOPLE_RESOURCE_PERMISSION_PREFIXES = new Set(['employee', 'position', 'client']);
const PEOPLE_RESOURCE_KEYS = new Set(['factory-clients']);
const WAREHOUSE_RESOURCE_PERMISSION_PREFIXES = new Set(['warehouse', 'stock_movement']);
const CATALOG_MODULE_RESOURCE_KEYS = new Set<string>([
  'feed:types',
  'feed:ingredients',
  'feed:formulas',
  'feed:formula-ingredients',
  'medicine:types',
  'core:poultry-types',
  'core:measurement-units',
  'core:client-categories',
  'hr:roles',
  'hr:permissions',
]);
export const isPasswordFieldName = (fieldName: string): boolean =>
  fieldName.toLowerCase().includes('password');
export const getDefaultInventoryItemTypeForModule = (
  moduleKey: string,
  fallback: InventoryItemType = 'egg',
): InventoryItemType => {
  const normalizedModuleKey = moduleKey.trim().toLowerCase();
  return MODULE_DEFAULT_INVENTORY_ITEM_TYPES[normalizedModuleKey] ?? fallback;
};
export const isCodeFieldName = (fieldName: string): boolean => {
  const normalizedFieldName = fieldName.trim().toLowerCase();
  return normalizedFieldName === 'code' || normalizedFieldName.endsWith('_code');
};

const CYRILLIC_TO_LATIN_MAP: Record<string, string> = {
  а: 'a',
  б: 'b',
  в: 'v',
  г: 'g',
  д: 'd',
  е: 'e',
  ё: 'e',
  ж: 'zh',
  з: 'z',
  и: 'i',
  й: 'y',
  к: 'k',
  л: 'l',
  м: 'm',
  н: 'n',
  о: 'o',
  п: 'p',
  р: 'r',
  с: 's',
  т: 't',
  у: 'u',
  ф: 'f',
  х: 'x',
  ц: 'ts',
  ч: 'ch',
  ш: 'sh',
  щ: 'sh',
  ъ: '',
  ы: 'y',
  ь: '',
  э: 'e',
  ю: 'yu',
  я: 'ya',
};
const AUTO_CODE_SOURCE_GROUPS = [
  ['resource', 'action'],
  ['title'],
  ['name'],
  ['label'],
  ['part_name'],
  ['first_name', 'last_name'],
  ['last_name', 'first_name'],
] as const;

const resourceUiConfigs: Record<string, ResourceUiConfig> = {
  'hr:employees': {
    formOrder: [
      'first_name',
      'last_name',
      'phone',
      'email',
      'organization_key',
      'password',
      'department_id',
      'position_id',
      'salary',
      'work_start_time',
      'work_end_time',
      'role_ids',
      'is_active',
    ],
    tableOrder: [
      'first_name',
      'last_name',
      'organization_key',
      'email',
      'department_id',
      'position_id',
    ],
    formSections: [
      {
        title: { ru: 'Личные данные', uz: 'Shaxsiy ma’lumotlar', en: 'Personal details' },
        fields: ['first_name', 'last_name', 'phone', 'email'],
      },
      {
        title: { ru: 'Учётная запись', uz: 'Hisob', en: 'Account' },
        fields: ['organization_key', 'password'],
      },
      {
        title: { ru: 'Работа', uz: 'Ish', en: 'Employment' },
        fields: [
          'department_id',
          'position_id',
          'salary',
          'work_start_time',
          'work_end_time',
          'role_ids',
        ],
      },
    ],
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'hr:roles': {
    formOrder: ['name', 'slug', 'description', 'permission_ids', 'is_active'],
    tableOrder: ['name', 'slug', 'description', 'is_active'],
    hideOrganizationFieldWhenScoped: true,
  },
  'hr:positions': {
    formOrder: ['title', 'slug', 'description', 'min_salary', 'max_salary', 'is_active'],
    tableOrder: ['title', 'slug', 'min_salary', 'max_salary', 'is_active'],
    hiddenFields: ['department_id'],
    hideOrganizationFieldWhenScoped: true,
  },
  'hr:permissions': {
    formOrder: ['code', 'resource', 'action', 'description', 'is_active'],
    tableOrder: ['code', 'resource', 'action', 'is_active'],
    hideOrganizationFieldWhenScoped: true,
  },
  'core:currencies': {
    formOrder: ['code', 'name', 'symbol', 'description', 'sort_order', 'is_default', 'is_active'],
    tableOrder: ['code', 'name', 'symbol', 'is_default', 'is_active'],
    hideOrganizationFieldWhenScoped: true,
  },
  'core:poultry-types': {
    formOrder: ['name', 'code', 'description', 'is_active'],
    tableOrder: ['name', 'code', 'description', 'is_active'],
    hideOrganizationFieldWhenScoped: true,
  },
  'core:measurement-units': {
    formOrder: ['code', 'name', 'description', 'sort_order', 'is_active'],
    tableOrder: ['code', 'name', 'description', 'sort_order', 'is_active'],
    hideOrganizationFieldWhenScoped: true,
  },
  'core:client-categories': {
    formOrder: ['code', 'name', 'description', 'sort_order', 'is_active'],
    tableOrder: ['code', 'name', 'description', 'sort_order', 'is_active'],
    hideOrganizationFieldWhenScoped: true,
  },
  'core:warehouses': {
    formOrder: ['department_id', 'name', 'code', 'is_default', 'is_active', 'description'],
    tableOrder: ['name', 'department_id', 'code', 'is_default', 'is_active'],
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'core:clients': {
    formOrder: ['first_name', 'last_name', 'email', 'phone', 'company_name', 'address'],
    tableOrder: ['first_name', 'last_name', 'phone', 'email', 'company_name'],
    // Legacy free-form fields: `category` is unused (superseded by
    // client_categories + client_categories links), `client_code` is
    // operator-generated and confusing, `telegram_chat_id` should be
    // bound via a one-link invite (backend has the endpoint; the UI
    // will surface a "Пригласить в Telegram" button later).
    formHiddenFields: ['category', 'client_code', 'telegram_chat_id'],
    formSections: [
      {
        title: { ru: 'Контакт', uz: 'Aloqa', en: 'Contact' },
        fields: ['first_name', 'last_name', 'email', 'phone'],
      },
      {
        title: { ru: 'Дополнительно', uz: 'Qo‘shimcha', en: 'Extras' },
        fields: ['company_name', 'address'],
      },
    ],
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'core:client-debts': {
    formOrder: [
      'client_id',
      'department_id',
      'item_type',
      'item_key',
      'quantity',
      'unit',
      'amount_total',
      'amount_paid',
      'currency_id',
      'issued_on',
      'due_on',
      'status',
      'posting_status',
      'note',
      'is_active',
    ],
    tableOrder: [
      'issued_on',
      'due_on',
      'client_id',
      'item_type',
      'item_key',
      'quantity',
      'unit',
      'amount_total',
      'amount_paid',
      'currency_id',
      'status',
      'posting_status',
    ],
    fieldHelpers: {
      item_type: {
        ru: 'Что продали клиенту: chick (птенцы), bird (взрослая птица), egg, feed, medicine, meat и т.п.',
        uz: 'Mijozga nima sotilgan: chick (jo‘jalar), bird (katta parranda), egg, feed, medicine, meat va h.k.',
        en: 'What was sold to the client: chick, bird, egg, feed, medicine, meat, etc.',
      },
      item_key: {
        ru: 'Ссылка на конкретную отгрузку/партию. Обычно подставляется автоматически при создании из документа.',
        uz: 'Aniq jo‘natma/partiyaga havola. Odatda hujjatdan avtomatik to‘ldiriladi.',
        en: 'Link to the specific shipment/batch. Usually filled automatically when created from a document.',
      },
      amount_total: {
        ru: 'Полная сумма задолженности. После проведения документ становится неизменяемым.',
        uz: 'Qarzning umumiy summasi. Hujjat o‘tkazilgandan so‘ng o‘zgartirilmaydi.',
        en: 'Total debt amount. Once posted, the document becomes immutable.',
      },
      amount_paid: {
        ru: 'Сумма уже полученной оплаты. Увеличивается при регистрации платежей.',
        uz: 'Olingan to‘lov summasi. To‘lovlar ro‘yxatga olinganda ortadi.',
        en: 'Amount already paid. Increases as payments are registered.',
      },
      due_on: {
        ru: 'Крайняя дата оплаты. Долг с просроченной датой попадает в отчёт по просрочке.',
        uz: 'To‘lov oxirgi muddati. Muddati o‘tgan qarzlar muddati o‘tgan hisobotga tushadi.',
        en: 'Payment due date. Overdue debts appear in the overdue report.',
      },
      posting_status: {
        ru: 'Черновик — можно редактировать и удалять. Проведён — учтён в отчётности, изменения только через сторнирование.',
        uz: 'Qoralama — tahrirlash va o‘chirish mumkin. O‘tkazilgan — hisobotda hisobga olingan, o‘zgartirish faqat storno orqali.',
        en: 'Draft — editable and deletable. Posted — recorded in reports, changes only via reversal.',
      },
    },
    formSections: [
      {
        title: { ru: 'Клиент и предмет', uz: 'Mijoz va mahsulot', en: 'Client and subject' },
        fields: ['client_id', 'department_id', 'item_type', 'item_key'],
      },
      {
        title: { ru: 'Сумма', uz: 'Summa', en: 'Amount' },
        fields: ['quantity', 'unit', 'amount_total', 'amount_paid', 'currency_id'],
      },
      {
        title: { ru: 'Даты и статус', uz: 'Sanalar va holat', en: 'Dates and status' },
        fields: ['issued_on', 'due_on', 'status', 'posting_status'],
      },
      {
        title: { ru: 'Дополнительно', uz: 'Qo‘shimcha', en: 'Extras' },
        fields: ['note', 'is_active'],
      },
    ],
    fieldEnums: {
      status: enumOptions(['open', 'partially_paid', 'closed', 'cancelled']),
      posting_status: enumOptions(['draft', 'posted', 'reversed']),
    },
    crossFieldValidator: (values) => {
      const errors: Record<string, LocalizedText> = {};
      const issuedOn = typeof values.issued_on === 'string' ? values.issued_on : '';
      const dueOn = typeof values.due_on === 'string' ? values.due_on : '';
      if (issuedOn && dueOn && dueOn < issuedOn) {
        errors.due_on = {
          ru: 'Дата оплаты не может быть раньше даты выставления.',
          uz: 'To‘lov sanasi chiqarilgan sanadan oldin bo‘lishi mumkin emas.',
          en: 'Due date cannot be earlier than the issue date.',
        };
      }
      const amountTotal = Number(values.amount_total);
      const amountPaid = Number(values.amount_paid);
      if (Number.isFinite(amountTotal) && Number.isFinite(amountPaid) && amountPaid > amountTotal) {
        errors.amount_paid = {
          ru: 'Оплата не может превышать общую сумму долга.',
          uz: 'To‘lov qarzning umumiy summasidan oshmasligi kerak.',
          en: 'Payment cannot exceed the total debt amount.',
        };
      }
      return errors;
    },
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
    detailPanelKey: 'debt_summary',
  },
  'finance:supplier-debts': {
    formOrder: [
      'client_id',
      'department_id',
      'item_type',
      'item_key',
      'quantity',
      'unit',
      'amount_total',
      'amount_paid',
      'currency_id',
      'issued_on',
      'due_on',
      'status',
      'posting_status',
      'note',
      'is_active',
    ],
    tableOrder: [
      'issued_on',
      'due_on',
      'client_id',
      'item_type',
      'item_key',
      'quantity',
      'unit',
      'amount_total',
      'amount_paid',
      'currency_id',
      'status',
      'posting_status',
    ],
    fieldHelpers: {
      client_id: {
        ru: 'Поставщик, перед которым возникла задолженность.',
        uz: 'Qarzdor bo‘lgan yetkazib beruvchi.',
        en: 'Supplier to whom the debt is owed.',
      },
      item_type: {
        ru: 'Категория закупки: raw (сырьё), medicine, service и т.д. Обычно подставляется автоматически из прихода.',
        uz: 'Xarid toifasi: raw (xomashyo), medicine, service va h.k. Odatda kirimdan avtomatik to‘ldiriladi.',
        en: 'Purchase category: raw, medicine, service, etc. Usually auto-filled from the goods receipt.',
      },
      amount_total: {
        ru: 'Сумма нашей задолженности перед поставщиком.',
        uz: 'Yetkazib beruvchiga bo‘lgan qarzimiz summasi.',
        en: 'Amount we owe the supplier.',
      },
      amount_paid: {
        ru: 'Сколько уже оплачено поставщику. Пополняется при регистрации исходящих платежей.',
        uz: 'Yetkazib beruvchiga to‘langan summa. Chiquvchi to‘lovlarda yangilanadi.',
        en: 'How much has been paid to the supplier. Updated as outgoing payments are registered.',
      },
      posting_status: {
        ru: 'Черновик — можно редактировать и удалять. Проведён — учтён в отчётности, изменения только через сторнирование.',
        uz: 'Qoralama — tahrirlash va o‘chirish mumkin. O‘tkazilgan — hisobotda hisobga olingan, o‘zgartirish faqat storno orqali.',
        en: 'Draft — editable and deletable. Posted — recorded in reports, changes only via reversal.',
      },
    },
    formSections: [
      {
        title: {
          ru: 'Поставщик и предмет',
          uz: 'Yetkazib beruvchi va mahsulot',
          en: 'Supplier and subject',
        },
        fields: ['client_id', 'department_id', 'item_type', 'item_key'],
      },
      {
        title: { ru: 'Сумма', uz: 'Summa', en: 'Amount' },
        fields: ['quantity', 'unit', 'amount_total', 'amount_paid', 'currency_id'],
      },
      {
        title: { ru: 'Даты и статус', uz: 'Sanalar va holat', en: 'Dates and status' },
        fields: ['issued_on', 'due_on', 'status', 'posting_status'],
      },
      {
        title: { ru: 'Дополнительно', uz: 'Qo‘shimcha', en: 'Extras' },
        fields: ['note', 'is_active'],
      },
    ],
    fieldEnums: {
      status: enumOptions(['open', 'partially_paid', 'closed', 'cancelled']),
      posting_status: enumOptions(['draft', 'posted', 'reversed']),
    },
    crossFieldValidator: (values) => {
      const errors: Record<string, LocalizedText> = {};
      const issuedOn = typeof values.issued_on === 'string' ? values.issued_on : '';
      const dueOn = typeof values.due_on === 'string' ? values.due_on : '';
      if (issuedOn && dueOn && dueOn < issuedOn) {
        errors.due_on = {
          ru: 'Дата оплаты не может быть раньше даты выставления.',
          uz: 'To‘lov sanasi chiqarilgan sanadan oldin bo‘lishi mumkin emas.',
          en: 'Due date cannot be earlier than the issue date.',
        };
      }
      const amountTotal = Number(values.amount_total);
      const amountPaid = Number(values.amount_paid);
      if (Number.isFinite(amountTotal) && Number.isFinite(amountPaid) && amountPaid > amountTotal) {
        errors.amount_paid = {
          ru: 'Оплата не может превышать общую сумму долга.',
          uz: 'To‘lov qarzning umumiy summasidan oshmasligi kerak.',
          en: 'Payment cannot exceed the total debt amount.',
        };
      }
      return errors;
    },
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
    detailPanelKey: 'debt_summary',
  },
  'finance:advances': {
    formOrder: [
      'employee_id',
      'department_id',
      'amount_issued',
      'currency_id',
      'issued_on',
      'due_on',
      'status',
      'note',
    ],
    tableOrder: ['issued_on', 'due_on', 'employee_id', 'amount_issued', 'currency_id', 'status'],
    fieldHelpers: {
      amount_issued: {
        ru: 'Сумма аванса, выданного сотруднику. Остаток и удержания отображаются в панели справа после сохранения.',
        uz: 'Xodimga berilgan avans summasi. Qoldiq va ushlab qolishlar saqlashdan keyin o‘ng paneldan ko‘rinadi.',
        en: 'Advance amount issued to the employee. Balance and deductions appear in the right-side panel after saving.',
      },
      due_on: {
        ru: 'Дата, до которой сотрудник должен погасить аванс или вернуть разницу.',
        uz: 'Xodim avansni qoplashi yoki qoldiqni qaytarishi kerak bo‘lgan sana.',
        en: 'Date by which the employee must repay the advance or return the remainder.',
      },
      status: {
        ru: 'Открыт — пока аванс не закрыт. Закрыт — после полного возврата или удержания из зарплаты.',
        uz: 'Ochiq — avans yopilmaguncha. Yopiq — to‘liq qaytarilgandan yoki maoshdan ushlab qolingandan keyin.',
        en: 'Open — until the advance is settled. Closed — after full return or deduction from payroll.',
      },
    },
    formSections: [
      {
        title: { ru: 'Получатель', uz: 'Oluvchi', en: 'Recipient' },
        fields: ['employee_id', 'department_id'],
      },
      {
        title: { ru: 'Сумма', uz: 'Summa', en: 'Amount' },
        fields: ['amount_issued', 'currency_id'],
      },
      {
        title: { ru: 'Даты и статус', uz: 'Sanalar va holat', en: 'Dates and status' },
        fields: ['issued_on', 'due_on', 'status'],
      },
      {
        title: { ru: 'Дополнительно', uz: 'Qo‘shimcha', en: 'Extras' },
        fields: ['note'],
      },
    ],
    fieldEnums: {
      status: enumOptions(['open', 'reconciled', 'cancelled']),
    },
    crossFieldValidator: (values) => {
      const errors: Record<string, LocalizedText> = {};
      const issuedOn = typeof values.issued_on === 'string' ? values.issued_on : '';
      const dueOn = typeof values.due_on === 'string' ? values.due_on : '';
      if (issuedOn && dueOn && dueOn < issuedOn) {
        errors.due_on = {
          ru: 'Срок возврата не может быть раньше даты выдачи.',
          uz: 'Qaytarish muddati berilgan sanadan oldin bo‘lishi mumkin emas.',
          en: 'Return date cannot be earlier than the issue date.',
        };
      }
      const amount = Number(values.amount_issued);
      if (Number.isFinite(amount) && amount <= 0) {
        errors.amount_issued = {
          ru: 'Сумма аванса должна быть больше нуля.',
          uz: 'Avans summasi noldan katta bo‘lishi kerak.',
          en: 'Advance amount must be greater than zero.',
        };
      }
      return errors;
    },
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
    detailPanelKey: 'advance_balance',
  },
  'finance:debt-payments': {
    formOrder: [
      'client_debt_id',
      'supplier_debt_id',
      'direction',
      'amount',
      'currency_id',
      'paid_on',
      'method',
      'cash_account_id',
      'reference_no',
      'note',
      'is_active',
    ],
    tableOrder: [
      'paid_on',
      'direction',
      'amount',
      'currency_id',
      'method',
      'reference_no',
      'cash_account_id',
    ],
    fieldEnums: {
      direction: enumOptions(['incoming', 'outgoing']),
      method: enumOptions(['cash', 'bank', 'card', 'transfer', 'offset', 'other']),
    },
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'finance:expense-categories': {
    formOrder: ['name', 'code', 'flow_type', 'description', 'is_active'],
    tableOrder: ['name', 'code', 'flow_type', 'department_id', 'is_active'],
    hiddenFields: ['is_global'],
    // parent_id (parent category) is handled by bulk import / seeding —
    // operators don't build the tree by hand.
    formHiddenFields: ['parent_id'],
    fieldEnums: {
      flow_type: enumOptions(['income', 'expense']),
    },
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'finance:cash-accounts': {
    formOrder: ['name', 'code', 'currency_id', 'opening_balance', 'note', 'is_active'],
    tableOrder: ['name', 'code', 'currency_id', 'opening_balance', 'department_id', 'is_active'],
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'finance:cash-transactions': {
    formOrder: [
      'transaction_date',
      'title',
      'transaction_type',
      'cash_account_id',
      'expense_category_id',
      'counterparty_client_id',
      'amount',
      'currency_id',
      'note',
    ],
    tableOrder: [
      'transaction_date',
      'transaction_type',
      'title',
      'cash_account_id',
      'department_id',
      'expense_category_id',
      'amount',
      'currency_id',
    ],
    // reference_no + counterparty_type/id + operation_date + item_key etc.
    // are system-side structured fields we don't ask operators to fill.
    formHiddenFields: [
      'reference_no',
      'counterparty_type',
      'counterparty_id',
      'operation_date',
      'item_type',
      'item_key',
      'amount_in_base',
      'exchange_rate_to_base',
    ],
    fieldHelpers: {
      transaction_type: {
        ru: 'income — поступление (приход), expense — списание (расход). Определяет знак движения по кассе.',
        uz: 'income — kirim, expense — chiqim. Kassa harakatining ishorasini belgilaydi.',
        en: 'income — inflow, expense — outflow. Defines the sign of the cash movement.',
      },
      cash_account_id: {
        ru: 'Касса или банковский счёт, через который проводим операцию. Остаток кассы обновится после сохранения.',
        uz: 'Operatsiya o‘tkaziladigan kassa yoki bank hisobi. Kassa qoldig‘i saqlashdan keyin yangilanadi.',
        en: 'Cash account or bank account used for the operation. The balance updates after saving.',
      },
      expense_category_id: {
        ru: 'Статья БДДС. Нужна для расходов — определяет, в какой раздел отчёта о движении денег попадёт операция.',
        uz: 'PPHH moddasi. Xarajatlar uchun kerak — pul oqimi hisobotining qaysi qismiga tushishini belgilaydi.',
        en: 'Cash-flow category. Required for expenses — determines which section of the cash-flow report the operation lands in.',
      },
      counterparty_client_id: {
        ru: 'Клиент или поставщик по операции. Для внутренних перемещений оставьте пустым.',
        uz: 'Operatsiya bo‘yicha mijoz yoki yetkazib beruvchi. Ichki ko‘chirishlar uchun bo‘sh qoldiring.',
        en: 'Client or supplier for the operation. Leave empty for internal transfers.',
      },
      amount: {
        ru: 'Сумма в валюте кассы. Проверьте, что валюта совпадает с валютой счёта.',
        uz: 'Kassa valyutasidagi summa. Valyuta hisob valyutasiga mos kelishini tekshiring.',
        en: 'Amount in the cash-account currency. Check that the currency matches the account.',
      },
    },
    formSections: [
      {
        title: { ru: 'Операция', uz: 'Operatsiya', en: 'Operation' },
        fields: [
          'transaction_date',
          'title',
          'transaction_type',
          'cash_account_id',
          'expense_category_id',
        ],
      },
      {
        title: {
          ru: 'Контрагент и сумма',
          uz: 'Kontragent va summa',
          en: 'Counterparty and amount',
        },
        fields: ['counterparty_client_id', 'amount', 'currency_id', 'note'],
      },
    ],
    fieldEnums: {
      transaction_type: enumOptions([
        'income',
        'expense',
        'transfer_in',
        'transfer_out',
        'adjustment',
      ]),
    },
    crossFieldValidator: (values) => {
      const errors: Record<string, LocalizedText> = {};
      const type =
        typeof values.transaction_type === 'string'
          ? values.transaction_type.trim().toLowerCase()
          : '';
      const categoryId =
        typeof values.expense_category_id === 'string' ? values.expense_category_id.trim() : '';
      if (type === 'expense' && !categoryId) {
        errors.expense_category_id = {
          ru: 'Для расхода необходимо указать статью БДДС.',
          uz: 'Xarajat uchun PPHH moddasini ko‘rsatish shart.',
          en: 'For an expense you must specify a cash-flow category.',
        };
      }
      const amount = Number(values.amount);
      if (Number.isFinite(amount) && amount <= 0) {
        errors.amount = {
          ru: 'Сумма должна быть больше нуля.',
          uz: 'Summa noldan katta bo‘lishi kerak.',
          en: 'Amount must be greater than zero.',
        };
      }
      return errors;
    },
    hideOrganizationFieldWhenScoped: true,
  },
  'slaughter:arrivals': {
    formOrder: [
      'poultry_type_id',
      'arrived_on',
      'birds_received',
      'arrival_total_weight_kg',
      'arrival_unit_price',
      'arrival_currency_id',
      'note',
    ],
    tableOrder: ['arrived_on', 'birds_received', 'arrival_total_weight_kg', 'arrival_unit_price'],
    fieldHelpers: {
      birds_received: {
        ru: 'Фактическое количество птицы на приёмке. Может отличаться от отгрузки — расхождение фиксируется через акт.',
        uz: 'Qabul qilingan haqiqiy parranda soni. Jo‘natmadan farq qilishi mumkin — farq dalolatnoma orqali qayd etiladi.',
        en: 'Actual number of birds on receipt. May differ from the shipment — the gap is recorded in the act.',
      },
      arrival_unit_price: {
        ru: 'Цена за 1 кг живой массы. Общая стоимость = цена × вес.',
        uz: '1 kg tirik vazn narxi. Umumiy qiymat = narx × vazn.',
        en: 'Price per 1 kg of live weight. Total cost = price × weight.',
      },
    },
    formSections: [
      {
        title: { ru: 'Партия', uz: 'Partiya', en: 'Batch' },
        fields: ['poultry_type_id', 'arrived_on'],
      },
      {
        title: { ru: 'Количество и стоимость', uz: 'Miqdor va qiymat', en: 'Quantity and cost' },
        fields: [
          'birds_received',
          'arrival_total_weight_kg',
          'arrival_unit_price',
          'arrival_currency_id',
        ],
      },
      {
        title: { ru: 'Дополнительно', uz: 'Qo‘shimcha', en: 'Extras' },
        fields: ['note'],
      },
    ],
    crossFieldValidator: (values) => {
      const errors: Record<string, LocalizedText> = {};
      const birds = Number(values.birds_received);
      const weight = Number(values.arrival_total_weight_kg);
      if (Number.isFinite(birds) && birds > 0 && Number.isFinite(weight) && weight > 0) {
        const avg = weight / birds;
        if (avg < 0.5 || avg > 6) {
          const avgStr = avg.toFixed(2);
          errors.arrival_total_weight_kg = {
            ru: `Средний вес тушки ${avgStr} кг выходит за разумные пределы (0.5–6 кг). Проверьте данные.`,
            uz: `O‘rtacha tushka vazni ${avgStr} kg oqilona chegaralardan tashqarida (0.5–6 kg). Ma’lumotlarni tekshiring.`,
            en: `Average carcass weight ${avgStr} kg is outside the reasonable range (0.5–6 kg). Check the data.`,
          };
        }
      }
      return errors;
    },
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'slaughter:processings': {
    formOrder: [
      'arrival_id',
      'processed_on',
      'processed_by',
      'birds_processed',
      'first_sort_count',
      'second_sort_count',
      'bad_count',
      'first_sort_weight_kg',
      'second_sort_weight_kg',
      'bad_weight_kg',
      'net_meat_kg',
      'waste_kg',
      'note',
    ],
    tableOrder: [
      'processed_on',
      'arrival_id',
      'birds_processed',
      'first_sort_count',
      'second_sort_count',
      'bad_count',
      'net_meat_kg',
      'waste_kg',
    ],
    fieldHelpers: {
      arrival_id: {
        ru: 'Партия живой птицы, из которой переработаны тушки. Определяет пул доступного сырья.',
        uz: 'Tushkalar qayta ishlangan tirik parranda partiyasi. Mavjud xomashyo fondini belgilaydi.',
        en: 'Live-bird batch the carcasses were processed from. Defines the available raw-material pool.',
      },
      birds_processed: {
        ru: 'Суммарно переработано голов. Должно совпадать с «1 сорт + 2 сорт + брак».',
        uz: 'Jami qayta ishlangan boshlar soni. «1-navli + 2-navli + brak» yig‘indisiga teng bo‘lishi kerak.',
        en: 'Total birds processed. Must equal "1st grade + 2nd grade + reject".',
      },
      first_sort_count: {
        ru: 'Количество тушек высшего сорта — товарные, без дефектов.',
        uz: 'Oliy nav tushkalar soni — tovar sifatli, nuqsonsiz.',
        en: 'Number of first-grade carcasses — marketable, defect-free.',
      },
      second_sort_count: {
        ru: 'Количество тушек второго сорта — мелкие/с дефектами, но пригодные.',
        uz: 'Ikkinchi nav tushkalar soni — mayda/nuqsonli, lekin yaroqli.',
        en: 'Number of second-grade carcasses — small or with defects but still usable.',
      },
      bad_count: {
        ru: 'Отбраковано — непригодно для реализации (учитывается как потеря).',
        uz: 'Brak — sotishga yaroqsiz (yo‘qotish sifatida hisobga olinadi).',
        en: 'Rejected — unfit for sale (counted as a loss).',
      },
      net_meat_kg: {
        ru: 'Чистое товарное мясо — итоговый выход без костей, голов, лап и потрохов.',
        uz: 'Toza tovar go‘sht — suyak, bosh, oyoq va ichak-qorinsiz yakuniy chiqish.',
        en: 'Net commercial meat — final yield without bones, heads, feet, and offal.',
      },
      waste_kg: {
        ru: 'Отходы — перья, головы, лапы, кровь и прочие непригодные части.',
        uz: 'Chiqindilar — pat, bosh, oyoq, qon va boshqa yaroqsiz qismlar.',
        en: 'Waste — feathers, heads, feet, blood and other unusable parts.',
      },
    },
    formSections: [
      {
        title: { ru: 'Партия и смена', uz: 'Partiya va smena', en: 'Batch and shift' },
        fields: ['arrival_id', 'processed_on', 'processed_by'],
      },
      {
        title: {
          ru: 'Разбивка по сортам (голов)',
          uz: 'Navlar bo‘yicha taqsimot (bosh)',
          en: 'Breakdown by grade (heads)',
        },
        fields: ['birds_processed', 'first_sort_count', 'second_sort_count', 'bad_count'],
      },
      {
        title: {
          ru: 'Разбивка по сортам (вес, кг)',
          uz: 'Navlar bo‘yicha taqsimot (vazn, kg)',
          en: 'Breakdown by grade (weight, kg)',
        },
        fields: ['first_sort_weight_kg', 'second_sort_weight_kg', 'bad_weight_kg'],
      },
      {
        title: {
          ru: 'Выход и отходы, кг',
          uz: 'Chiqish va chiqindilar, kg',
          en: 'Yield and waste, kg',
        },
        fields: ['net_meat_kg', 'waste_kg'],
      },
      {
        title: { ru: 'Дополнительно', uz: 'Qo‘shimcha', en: 'Extras' },
        fields: ['note'],
      },
    ],
    crossFieldValidator: (values) => {
      const errors: Record<string, LocalizedText> = {};
      const total = Number(values.birds_processed);
      const s1 = Number(values.first_sort_count);
      const s2 = Number(values.second_sort_count);
      const bad = Number(values.bad_count);
      if (
        Number.isFinite(total) &&
        total > 0 &&
        Number.isFinite(s1) &&
        Number.isFinite(s2) &&
        Number.isFinite(bad)
      ) {
        const sum = s1 + s2 + bad;
        if (sum !== total) {
          const delta = total - sum;
          errors.birds_processed = {
            ru: `«1 сорт + 2 сорт + брак» = ${sum}, должно быть ${total} (расхождение ${delta}).`,
            uz: `«1-nav + 2-nav + brak» = ${sum}, ${total} bo‘lishi kerak (farq ${delta}).`,
            en: `"1st grade + 2nd grade + reject" = ${sum}, should be ${total} (gap ${delta}).`,
          };
        }
      }
      return errors;
    },
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'slaughter:semi-products': {
    formOrder: [
      'produced_on',
      'processing_id',
      'warehouse_id',
      'part_name',
      'quality',
      'quantity',
      'unit',
      'code',
      'note',
    ],
    tableOrder: ['produced_on', 'part_name', 'quality', 'quantity', 'unit'],
    fieldEnums: {
      quality: enumOptions(['first', 'second', 'mixed', 'byproduct']),
    },
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'slaughter:semi-product-shipments': {
    formOrder: [
      'shipped_on',
      'semi_product_id',
      'warehouse_id',
      'client_id',
      'quantity',
      'unit',
      'unit_price',
      'currency_id',
      'note',
    ],
    tableOrder: ['shipped_on', 'semi_product_id', 'client_id', 'quantity', 'status'],
    hiddenFields: ['invoice_no'],
    formHiddenFields: [
      'received_quantity',
      'status',
      'acknowledged_at',
      'acknowledged_by',
      'created_by',
    ],
    fieldEnums: {
      status: enumOptions(['sent', 'received', 'discrepancy']),
    },
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'slaughter:slaughter-quality-checks': {
    formOrder: ['checked_on', 'semi_product_id', 'status', 'grade', 'inspector_id', 'notes'],
    tableOrder: ['checked_on', 'semi_product_id', 'status', 'grade', 'inspector_id'],
    fieldEnums: {
      status: enumOptions(['pending', 'passed', 'failed']),
      grade: enumOptions(['first', 'second', 'mixed', 'byproduct']),
    },
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'inventory:movements': {
    formOrder: [
      'department_id',
      'warehouse_id',
      'occurred_on',
      'movement_kind',
      'item_type',
      'item_key',
      'quantity',
      'unit',
      'counterparty_warehouse_id',
      'note',
    ],
    tableOrder: [
      'occurred_on',
      'movement_kind',
      'warehouse_id',
      'item_type',
      'item_key',
      'quantity',
      'unit',
      'counterparty_warehouse_id',
      'note',
    ],
    hiddenFields: ['counterparty_department_id', 'reference_table', 'reference_id'],
    fieldEnums: {
      item_type: enumOptions(['egg', 'chick', 'feed', 'feed_raw', 'medicine', 'semi_product']),
      // Operators can only book incoming/outgoing manually. Transfers are
      // created via the inventory-transfer flow, and adjustments come from
      // stock-takes — we don't expose them as a free-form choice.
      movement_kind: enumOptions(['incoming', 'outgoing']),
    },
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'egg:productions': {
    formOrder: [
      'produced_on',
      'warehouse_id',
      'eggs_collected',
      'eggs_broken',
      'eggs_rejected',
      'total_shelled',
      'note',
    ],
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'egg:shipments': {
    formOrder: [
      'shipped_on',
      'production_id',
      'warehouse_id',
      'client_id',
      'destination_department_id',
      'eggs_count',
      'unit',
      'unit_price',
      'currency_id',
      'note',
    ],
    hiddenFields: ['invoice_no'],
    formHiddenFields: [
      'eggs_broken',
      'received_quantity',
      'status',
      'acknowledged_at',
      'acknowledged_by',
    ],
    fieldHelpers: {
      destination_department_id: {
        ru: 'Только для внутренней передачи между отделами. Для продажи клиенту оставьте пустым.',
        uz: 'Faqat bo‘limlar orasida ichki uzatish uchun. Mijozga sotish uchun bo‘sh qoldiring.',
        en: 'Only for internal inter-department transfers. Leave empty when selling to a client.',
      },
    },
    fieldEnums: {
      status: enumOptions(['sent', 'received', 'discrepancy']),
    },
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'egg:egg-quality-checks': {
    formOrder: ['checked_on', 'production_id', 'status', 'grade', 'inspector_id', 'notes'],
    tableOrder: ['checked_on', 'production_id', 'status', 'grade', 'inspector_id'],
    fieldEnums: {
      status: enumOptions(['pending', 'passed', 'failed']),
      grade: enumOptions(['large', 'medium', 'small', 'defective', 'mixed']),
    },
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'incubation:batches': {
    formOrder: [
      'arrived_on',
      'batch_code',
      'warehouse_id',
      'eggs_arrived',
      'expected_hatch_on',
      'note',
      'is_active',
    ],
    fieldHelpers: {
      eggs_arrived: {
        ru: 'Количество яиц при закладке. Оплодотворённость и вывод рассчитываются на этапе «Инкубации».',
        uz: 'Yuklash paytidagi tuxumlar soni. Urug‘lanish va chiqish «Inkubatsiya» bosqichida hisoblanadi.',
        en: 'Number of eggs at setting. Fertility and hatching are computed during the "Incubation" stage.',
      },
      expected_hatch_on: {
        ru: 'Ожидаемая дата вывода — обычно +21 день для куры-несушки. Используется для планирования.',
        uz: 'Kutilayotgan chiqish sanasi — odatda tuxum beruvchi tovuq uchun +21 kun. Rejalashtirish uchun ishlatiladi.',
        en: 'Expected hatch date — typically +21 days for laying hens. Used for planning.',
      },
    },
    formSections: [
      {
        title: { ru: 'Партия', uz: 'Partiya', en: 'Batch' },
        fields: ['arrived_on', 'batch_code', 'warehouse_id'],
      },
      {
        title: { ru: 'Закладка', uz: 'Yuklash', en: 'Setting' },
        fields: ['eggs_arrived', 'expected_hatch_on'],
      },
      {
        title: { ru: 'Дополнительно', uz: 'Qo‘shimcha', en: 'Extras' },
        fields: ['note', 'is_active'],
      },
    ],
    crossFieldValidator: (values) => {
      const errors: Record<string, LocalizedText> = {};
      const arrivedOn = typeof values.arrived_on === 'string' ? values.arrived_on : '';
      const hatchOn = typeof values.expected_hatch_on === 'string' ? values.expected_hatch_on : '';
      if (arrivedOn && hatchOn && hatchOn < arrivedOn) {
        errors.expected_hatch_on = {
          ru: 'Дата вывода не может быть раньше даты закладки.',
          uz: 'Chiqish sanasi yuklash sanasidan oldin bo‘lishi mumkin emas.',
          en: 'Hatch date cannot be earlier than the setting date.',
        };
      }
      return errors;
    },
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'incubation:runs': {
    formOrder: [
      'start_date',
      'end_date',
      'batch_id',
      'warehouse_id',
      'eggs_set',
      'grade_1_count',
      'grade_2_count',
      'bad_eggs_count',
      'chicks_hatched',
      'chicks_destroyed',
      'note',
    ],
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'incubation:chick-shipments': {
    formOrder: [
      'shipped_on',
      'run_id',
      'warehouse_id',
      'client_id',
      'destination_department_id',
      'chicks_count',
      'unit_price',
      'currency_id',
      'note',
    ],
    hiddenFields: ['invoice_no'],
    formHiddenFields: ['received_quantity', 'status', 'acknowledged_at', 'acknowledged_by'],
    fieldHelpers: {
      destination_department_id: {
        ru: 'Только для внутренней передачи между отделами. Для продажи клиенту оставьте пустым.',
        uz: 'Faqat bo‘limlar orasida ichki uzatish uchun. Mijozga sotish uchun bo‘sh qoldiring.',
        en: 'Only for internal inter-department transfers. Leave empty when selling to a client.',
      },
    },
    fieldEnums: {
      status: enumOptions(['sent', 'received', 'discrepancy']),
    },
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'feed:raw-arrivals': {
    formOrder: [
      'arrived_on',
      'ingredient_id',
      'warehouse_id',
      'quantity',
      'unit',
      'unit_price',
      'currency_id',
      'note',
    ],
    tableOrder: ['arrived_on', 'ingredient_id', 'quantity', 'unit_price', 'currency_id'],
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'feed:raw-consumptions': {
    formOrder: [
      'consumed_on',
      'production_batch_id',
      'ingredient_id',
      'warehouse_id',
      'quantity',
      'unit',
      'note',
    ],
    tableOrder: ['consumed_on', 'production_batch_id', 'ingredient_id', 'quantity'],
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'feed:quality-checks': {
    formOrder: ['checked_on', 'production_batch_id', 'status', 'grade', 'inspector_id', 'notes'],
    tableOrder: ['checked_on', 'production_batch_id', 'status', 'grade', 'inspector_id'],
    fieldEnums: {
      status: enumOptions(['pending', 'passed', 'failed']),
      grade: enumOptions(['first', 'second', 'mixed', 'premium', 'rejected']),
    },
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'feed:types': {
    formOrder: ['name', 'code', 'poultry_type_id', 'unit', 'description', 'is_active'],
    tableOrder: ['name', 'code', 'poultry_type_id', 'unit', 'is_active'],
    hiddenFields: ['measurement_unit_id'],
    hideOrganizationFieldWhenScoped: true,
  },
  'feed:ingredients': {
    formOrder: ['name', 'code', 'supplier_category', 'unit', 'description', 'is_active'],
    tableOrder: ['name', 'code', 'supplier_category', 'unit', 'is_active'],
    hiddenFields: ['measurement_unit_id'],
    hideOrganizationFieldWhenScoped: true,
  },
  'feed:formulas': {
    formOrder: ['name', 'code', 'feed_type_id', 'version', 'description', 'is_active'],
    tableOrder: ['name', 'code', 'feed_type_id', 'version', 'is_active'],
    hideOrganizationFieldWhenScoped: true,
  },
  'feed:formula-ingredients': {
    formOrder: ['formula_id', 'ingredient_id', 'quantity_per_batch', 'unit'],
    tableOrder: ['formula_id', 'ingredient_id', 'quantity_per_batch', 'unit'],
    hiddenFields: ['measurement_unit_id'],
    hideOrganizationFieldWhenScoped: true,
  },
  'feed:consumptions': {
    formOrder: [
      'consumed_on',
      'feed_type_id',
      'production_batch_id',
      'poultry_type_id',
      'quantity',
      'unit',
      'note',
    ],
    tableOrder: ['consumed_on', 'feed_type_id', 'quantity', 'unit', 'poultry_type_id'],
    hiddenFields: ['daily_log_id', 'measurement_unit_id'],
    fieldHelpers: {
      feed_type_id: {
        ru: 'Тип корма, который списываем (стартер / гровер / финишер и т.д.).',
        uz: 'Chiqim qilinadigan em turi (starter / grower / finisher va h.k.).',
        en: 'Feed type being consumed (starter / grower / finisher, etc.).',
      },
      production_batch_id: {
        ru: 'Партия-производитель корма. Оставьте пустым, если корм внешний — тогда списание идёт по общему остатку.',
        uz: 'Em ishlab chiqargan partiya. Em tashqi bo‘lsa bo‘sh qoldiring — bu holda umumiy qoldiqdan chiqim qilinadi.',
        en: 'Production batch that produced the feed. Leave empty for external feed — then the write-off draws from the general stock.',
      },
      poultry_type_id: {
        ru: 'Порода/группа птицы, на которую пошёл корм. Нужен для расчёта FCR.',
        uz: 'Em ketgan parranda zoti/guruhi. FCR hisoblash uchun kerak.',
        en: 'Poultry breed/group the feed went to. Needed for FCR calculation.',
      },
      quantity: {
        ru: 'Сколько корма ушло. Снимается с остатка после сохранения.',
        uz: 'Qancha em ketgan. Saqlashdan keyin qoldiqdan yechiladi.',
        en: 'How much feed was used. Deducted from stock after saving.',
      },
    },
    formSections: [
      {
        title: { ru: 'Что списываем', uz: 'Nima chiqim qilinadi', en: 'What is consumed' },
        fields: ['consumed_on', 'feed_type_id', 'production_batch_id', 'poultry_type_id'],
      },
      {
        title: { ru: 'Количество', uz: 'Miqdor', en: 'Quantity' },
        fields: ['quantity', 'unit'],
      },
      {
        title: { ru: 'Дополнительно', uz: 'Qo‘shimcha', en: 'Extras' },
        fields: ['note'],
      },
    ],
    crossFieldValidator: (values) => {
      const errors: Record<string, LocalizedText> = {};
      const qty = Number(values.quantity);
      if (Number.isFinite(qty) && qty <= 0) {
        errors.quantity = {
          ru: 'Количество должно быть больше нуля.',
          uz: 'Miqdor noldan katta bo‘lishi kerak.',
          en: 'Quantity must be greater than zero.',
        };
      }
      return errors;
    },
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'feed:product-shipments': {
    formOrder: [
      'shipped_on',
      'feed_type_id',
      'warehouse_id',
      'production_batch_id',
      'client_id',
      'quantity',
      'unit',
      'unit_price',
      'currency_id',
      'note',
    ],
    hiddenFields: ['invoice_no'],
    formHiddenFields: ['received_quantity', 'status', 'acknowledged_at', 'acknowledged_by'],
    fieldEnums: {
      status: enumOptions(['sent', 'received', 'discrepancy']),
    },
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'feed:production-batches': {
    formOrder: [
      'started_on',
      'finished_on',
      'formula_id',
      'warehouse_id',
      'batch_code',
      'planned_output',
      'actual_output',
      'unit',
      'note',
    ],
    hiddenFields: ['invoice_no'],
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'factory:flocks': {
    formOrder: [
      'arrived_on',
      'flock_code',
      'warehouse_id',
      'poultry_type_id',
      'initial_count',
      'current_count',
      'status',
      'note',
      'is_active',
    ],
    hiddenFields: ['chick_arrival_id'],
    fieldHelpers: {
      initial_count: {
        ru: 'Количество птенцов при постановке партии. Меняется только через корректировку.',
        uz: 'Partiya boshlanganidagi jo‘jalar soni. Faqat tuzatish orqali o‘zgartiriladi.',
        en: 'Number of chicks when the batch was placed. Changed only via an adjustment.',
      },
      current_count: {
        ru: 'Пересчитывается автоматически по падежу и отгрузкам.',
        uz: 'O‘lim va jo‘natmalarga qarab avtomatik qayta hisoblanadi.',
        en: 'Recalculated automatically from mortality and shipments.',
      },
    },
    formSections: [
      {
        title: { ru: 'Партия', uz: 'Partiya', en: 'Batch' },
        fields: ['arrived_on', 'flock_code', 'warehouse_id', 'poultry_type_id'],
      },
      {
        title: { ru: 'Поголовье', uz: 'Bosh soni', en: 'Livestock' },
        fields: ['initial_count', 'current_count', 'status'],
      },
      {
        title: { ru: 'Дополнительно', uz: 'Qo‘shimcha', en: 'Extras' },
        fields: ['note', 'is_active'],
      },
    ],
    crossFieldValidator: (values) => {
      const errors: Record<string, LocalizedText> = {};
      const initial = Number(values.initial_count);
      const current = Number(values.current_count);
      if (
        Number.isFinite(initial) &&
        Number.isFinite(current) &&
        initial > 0 &&
        current > initial
      ) {
        errors.current_count = {
          ru: 'Текущее поголовье не может быть больше исходного. Оставьте пустым — пересчитается автоматически.',
          uz: 'Hozirgi bosh soni boshlang‘ich sondan ko‘p bo‘lishi mumkin emas. Bo‘sh qoldirsangiz — avtomatik qayta hisoblanadi.',
          en: 'Current head count cannot exceed the initial count. Leave empty — it will be recalculated automatically.',
        };
      }
      return errors;
    },
    tableOrder: [
      'arrived_on',
      'flock_code',
      'initial_count',
      'current_count',
      'status',
      'poultry_type_id',
    ],
    fieldEnums: {
      status: enumOptions(['active', 'completed', 'cancelled']),
    },
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
    detailPanelKey: 'flock_kpi',
  },
  'factory:daily-logs': {
    formOrder: [
      'log_date',
      'flock_id',
      'mortality_count',
      'sick_count',
      'healthy_count',
      'feed_type_id',
      'feed_consumed_kg',
      'feed_cost',
      'water_consumed_liters',
      'avg_weight_kg',
      'temperature',
      'note',
    ],
    tableOrder: [
      'log_date',
      'flock_id',
      'mortality_count',
      'sick_count',
      'healthy_count',
      'feed_consumed_kg',
      'avg_weight_kg',
      'temperature',
    ],
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'factory:shipments': {
    formOrder: [
      'shipped_on',
      'flock_id',
      'warehouse_id',
      'client_id',
      'birds_count',
      'total_weight_kg',
      'unit_price',
      'currency_id',
      'note',
    ],
    tableOrder: [
      'shipped_on',
      'flock_id',
      'client_id',
      'birds_count',
      'total_weight_kg',
      'unit_price',
      'currency_id',
      'status',
    ],
    hiddenFields: ['invoice_no'],
    formHiddenFields: ['received_quantity', 'status', 'acknowledged_at', 'acknowledged_by'],
    fieldHelpers: {
      client_id: {
        ru: 'Внешний покупатель отгрузки.',
        uz: 'Jo‘natma tashqi xaridori.',
        en: 'External buyer for the shipment.',
      },
      birds_count: {
        ru: 'Количество голов в отгрузке. Спишется из остатка партии после сохранения.',
        uz: 'Jo‘natmadagi bosh soni. Saqlashdan keyin partiya qoldig‘idan yechiladi.',
        en: 'Head count in the shipment. Deducted from the batch balance after saving.',
      },
      total_weight_kg: {
        ru: 'Общий живой вес. Используется для биллинга и расчёта цены.',
        uz: 'Umumiy tirik vazn. Billing va narxni hisoblash uchun ishlatiladi.',
        en: 'Total live weight. Used for billing and price calculation.',
      },
      unit_price: {
        ru: 'Цена за 1 кг. Итог = цена × вес.',
        uz: '1 kg narxi. Jami = narx × vazn.',
        en: 'Price per 1 kg. Total = price × weight.',
      },
      status: {
        ru: 'Отправлено → Принято (получатель подтверждает приёмку) → Расхождение (если фактическое количество отличается).',
        uz: 'Jo‘natilgan → Qabul qilindi (qabul qiluvchi tasdiqlaydi) → Nomuvofiqlik (haqiqiy miqdor farq qilsa).',
        en: 'Sent → Received (receiver confirms) → Discrepancy (if the actual quantity differs).',
      },
    },
    formSections: [
      {
        title: { ru: 'Отгрузка', uz: 'Jo‘natma', en: 'Shipment' },
        fields: ['shipped_on', 'flock_id', 'warehouse_id', 'client_id'],
      },
      {
        title: { ru: 'Количество и цена', uz: 'Miqdor va narx', en: 'Quantity and price' },
        fields: ['birds_count', 'total_weight_kg', 'unit_price', 'currency_id'],
      },
      {
        title: { ru: 'Дополнительно', uz: 'Qo‘shimcha', en: 'Extras' },
        fields: ['note'],
      },
    ],
    fieldEnums: {
      status: enumOptions(['sent', 'received', 'discrepancy']),
    },
    crossFieldValidator: (values) => {
      const errors: Record<string, LocalizedText> = {};
      const birds = Number(values.birds_count);
      const weight = Number(values.total_weight_kg);
      if (Number.isFinite(birds) && birds > 0 && Number.isFinite(weight) && weight > 0) {
        const avg = weight / birds;
        if (avg < 0.3 || avg > 6) {
          const avgStr = avg.toFixed(2);
          errors.total_weight_kg = {
            ru: `Средний живой вес ${avgStr} кг выходит за разумные пределы (0.3–6 кг). Проверьте данные.`,
            uz: `O‘rtacha tirik vazn ${avgStr} kg oqilona chegaralardan tashqarida (0.3–6 kg). Ma’lumotlarni tekshiring.`,
            en: `Average live weight ${avgStr} kg is outside the reasonable range (0.3–6 kg). Check the data.`,
          };
        }
      }
      return errors;
    },
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'factory:medicine-usages': {
    formOrder: [
      'usage_date',
      'flock_id',
      'medicine_type_id',
      'medicine_batch_id',
      'quantity',
      'unit_cost',
      'total_cost',
      'measurement_unit_id',
      'note',
    ],
    tableOrder: [
      'usage_date',
      'flock_id',
      'medicine_type_id',
      'quantity',
      'unit_cost',
      'total_cost',
    ],
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'factory:vaccination-plans': {
    formOrder: [
      'flock_id',
      'medicine_type_id',
      'day_of_life',
      'planned_date',
      'is_completed',
      'completed_date',
      'note',
    ],
    tableOrder: [
      'flock_id',
      'medicine_type_id',
      'day_of_life',
      'planned_date',
      'is_completed',
      'completed_date',
    ],
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'medicine:types': {
    hiddenFields: ['unit'],
  },
  'medicine:batches': {
    formOrder: [
      'arrived_on',
      'expiry_date',
      'medicine_type_id',
      'warehouse_id',
      'batch_code',
      'barcode',
      'received_quantity',
      'remaining_quantity',
      'unit',
      'unit_cost',
      'currency_id',
      'note',
    ],
    tableOrder: [
      'arrived_on',
      'medicine_type_id',
      'batch_code',
      'barcode',
      'remaining_quantity',
      'unit',
      'expiry_date',
    ],
    hiddenFields: [
      'arrival_id',
      'qr_public_token',
      'qr_token_expires_at',
      'qr_generated_at',
      'qr_image_key',
      'qr_image_content_type',
      'qr_image_size_bytes',
      'attachment_key',
      'attachment_name',
      'attachment_content_type',
      'attachment_size_bytes',
    ],
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
  'medicine:consumptions': {
    formOrder: [
      'consumed_on',
      'batch_id',
      'factory_flock_id',
      'poultry_type_id',
      'client_id',
      'quantity',
      'unit',
      'purpose',
      'notes',
    ],
    tableOrder: ['consumed_on', 'batch_id', 'quantity', 'unit', 'purpose', 'factory_flock_id'],
    hiddenFields: ['measurement_unit_id', 'created_by'],
    fieldHelpers: {
      batch_id: {
        ru: 'Партия препарата. Рекомендуется списывать по FEFO — партии с ближайшим сроком годности первыми.',
        uz: 'Dori partiyasi. FEFO bo‘yicha chiqim qilish tavsiya etiladi — avval yaroqlilik muddati yaqin bo‘lgan partiyalar.',
        en: 'Medicine batch. FEFO is recommended — batches with the nearest expiry date first.',
      },
      factory_flock_id: {
        ru: 'Партия птицы, на которой использовали препарат. Оставьте пустым, если не по конкретной партии.',
        uz: 'Dori qo‘llanilgan parranda partiyasi. Aniq partiyaga bog‘liq bo‘lmasa bo‘sh qoldiring.',
        en: 'Poultry batch the medicine was used on. Leave empty if not tied to a specific batch.',
      },
      client_id: {
        ru: 'Клиент — если препарат отпущен внешнему покупателю. Для внутреннего использования оставьте пустым.',
        uz: 'Mijoz — dori tashqi xaridorga berilganda. Ichki foydalanish uchun bo‘sh qoldiring.',
        en: 'Client — if the medicine was issued to an external buyer. Leave empty for internal use.',
      },
      quantity: {
        ru: 'Количество препарата в единицах партии. Вычитается из остатка после сохранения.',
        uz: 'Partiya birliklarida dori miqdori. Saqlashdan keyin qoldiqdan ayriladi.',
        en: 'Amount of medicine in batch units. Deducted from stock after saving.',
      },
      purpose: {
        ru: 'Коротко: профилактика, лечение, вакцинация и т.п.',
        uz: 'Qisqacha: profilaktika, davolash, emlash va h.k.',
        en: 'Short note: prevention, treatment, vaccination, etc.',
      },
    },
    formSections: [
      {
        title: { ru: 'Кому и откуда', uz: 'Kimga va qayerdan', en: 'From and to' },
        fields: ['consumed_on', 'batch_id', 'factory_flock_id', 'poultry_type_id', 'client_id'],
      },
      {
        title: { ru: 'Сколько', uz: 'Qancha', en: 'How much' },
        fields: ['quantity', 'unit'],
      },
      {
        title: { ru: 'Дополнительно', uz: 'Qo‘shimcha', en: 'Extras' },
        fields: ['purpose', 'notes'],
      },
    ],
    crossFieldValidator: (values) => {
      const errors: Record<string, LocalizedText> = {};
      const qty = Number(values.quantity);
      if (Number.isFinite(qty) && qty <= 0) {
        errors.quantity = {
          ru: 'Количество должно быть больше нуля.',
          uz: 'Miqdor noldan katta bo‘lishi kerak.',
          en: 'Quantity must be greater than zero.',
        };
      }
      return errors;
    },
    hideDepartmentFieldWhenScoped: true,
    hideOrganizationFieldWhenScoped: true,
  },
};

export const inputBaseClassName =
  'flex h-11 w-full rounded-2xl border border-border/75 bg-card px-4 py-3 text-sm text-foreground shadow-[0_16px_38px_-30px_rgba(15,23,42,0.12)] ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50';
export const heroCardClassName =
  'relative overflow-hidden rounded-[30px] border border-border/70 bg-card shadow-[0_28px_88px_-56px_rgba(15,23,42,0.16)]';
export const frostedPanelClassName =
  'rounded-[24px] border border-border/70 bg-card shadow-[0_20px_56px_-40px_rgba(15,23,42,0.14)]';
export const compactPillClassName =
  'rounded-full border border-border/75 bg-card px-3 py-1.5 text-xs font-medium text-muted-foreground shadow-[0_16px_36px_-30px_rgba(15,23,42,0.1)]';

type FieldInputKind =
  | 'text'
  | 'password'
  | 'email'
  | 'tel'
  | 'integer'
  | 'number'
  | 'boolean'
  | 'date'
  | 'time'
  | 'datetime'
  | 'json';

const DATE_FIELD_NAMES = new Set([
  'arrived_on',
  'consumed_on',
  'created_at',
  'deleted_at',
  'end_date',
  'expense_date',
  'expected_hatch_on',
  'expiry_date',
  'finished_on',
  'month_start',
  'processed_on',
  'produced_on',
  'received_on',
  'shipped_on',
  'start_date',
  'started_on',
  'transaction_date',
  'updated_at',
]);
const DATE_FIELD_SUFFIXES = ['_date', '_on', '_start', '_end', '_at'] as const;

export const FORBIDDEN_PAYLOAD_FIELDS = new Set(['id', 'created_at', 'updated_at', 'deleted_at']);
export type ModuleCrudAction =
  | 'create_record'
  | 'update_record'
  | 'delete_record'
  | 'stock_transfer'
  | 'client_notification';
export type ModuleCrudActionAccess = {
  canCreateActiveResource: boolean;
  canEditRecordEntries: boolean;
  canDeleteActiveResource: boolean;
  canSendClientNotifications: boolean;
};

export const canExecuteModuleCrudAction = (
  action: ModuleCrudAction,
  access: ModuleCrudActionAccess,
): boolean => {
  switch (action) {
    case 'create_record':
      return access.canCreateActiveResource;
    case 'update_record':
      return access.canEditRecordEntries;
    case 'delete_record':
      return access.canDeleteActiveResource;
    case 'stock_transfer':
      return access.canCreateActiveResource;
    case 'client_notification':
      return access.canSendClientNotifications;
    default:
      return false;
  }
};

export const isMultiReferenceField = (field: CrudFieldMeta): boolean =>
  Boolean(field.reference?.multiple);

const sanitizePayload = (payload: CrudRecord, idColumn: string): CrudRecord => {
  const cleaned: CrudRecord = {};
  for (const [key, value] of Object.entries(payload)) {
    if (key === idColumn || FORBIDDEN_PAYLOAD_FIELDS.has(key)) {
      continue;
    }
    if (value === undefined) {
      continue;
    }
    cleaned[key] = value;
  }

  return cleaned;
};

export const getFieldInputKind = (field: CrudFieldMeta): FieldInputKind => {
  const fieldName = field.name.toLowerCase();
  const databaseType = (field.database_type || '').toLowerCase();

  if (isPasswordFieldName(fieldName)) {
    return 'password';
  }
  if (fieldName === 'email') {
    return 'email';
  }
  if (fieldName === 'phone') {
    return 'tel';
  }
  if (
    field.type === 'date' ||
    databaseType === 'date' ||
    DATE_FIELD_NAMES.has(fieldName) ||
    DATE_FIELD_SUFFIXES.some((suffix) => fieldName.endsWith(suffix))
  ) {
    return 'date';
  }
  if (field.type === 'time' || databaseType.startsWith('time')) {
    return 'time';
  }
  if (field.type === 'datetime' || databaseType.includes('timestamp')) {
    return 'datetime';
  }
  if (field.type === 'boolean' || databaseType === 'boolean' || databaseType === 'bool') {
    return 'boolean';
  }
  if (
    field.type === 'integer' ||
    databaseType === 'smallint' ||
    databaseType === 'integer' ||
    databaseType === 'bigint'
  ) {
    return 'integer';
  }
  if (
    field.type === 'number' ||
    databaseType === 'numeric' ||
    databaseType === 'decimal' ||
    databaseType === 'real' ||
    databaseType === 'double precision'
  ) {
    return 'number';
  }
  if (
    field.type === 'json' ||
    databaseType === 'json' ||
    databaseType === 'jsonb' ||
    databaseType.startsWith('_')
  ) {
    return 'json';
  }
  return 'text';
};

export const humanizeKey = (value: string): string =>
  value
    .split(/[-_]/g)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');

const getStringFormValue = (value: string | boolean | string[] | undefined): string => {
  if (typeof value === 'string') {
    return value.trim();
  }
  if (Array.isArray(value)) {
    return value
      .map((item) => item.trim())
      .filter((item) => item.length > 0)
      .join(' ')
      .trim();
  }
  return '';
};

const transliterateToLatin = (value: string): string =>
  value
    .split('')
    .map((character) => {
      const lowerCharacter = character.toLowerCase();
      if (!(lowerCharacter in CYRILLIC_TO_LATIN_MAP)) {
        return character;
      }
      const mappedCharacter = CYRILLIC_TO_LATIN_MAP[lowerCharacter] ?? '';
      return character === lowerCharacter ? mappedCharacter : mappedCharacter.toUpperCase();
    })
    .join('');

const normalizeCodeSourceValue = (value: string): string =>
  transliterateToLatin(value)
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[ʻʼ’'`]+/g, '')
    .replace(/&/g, ' and ')
    .trim();

const buildDelimitedCode = (
  values: string[],
  options: { delimiter: '-' | '.'; casing: 'upper' | 'lower' },
): string => {
  const tokens = values
    .map((value) => normalizeCodeSourceValue(value))
    .join(options.delimiter === '.' ? ' ' : ' ')
    .replace(/[^A-Za-z0-9]+/g, ' ')
    .trim()
    .split(/\s+/)
    .filter((token) => token.length > 0);

  if (tokens.length === 0) {
    return EMPTY_TEXT;
  }

  const joined = tokens.join(options.delimiter);
  return options.casing === 'upper' ? joined.toUpperCase() : joined.toLowerCase();
};

export const buildAutoGeneratedCodeValue = (
  fields: CrudFieldMeta[],
  values: FormValues,
  targetFieldName: string,
): string => {
  if (!isCodeFieldName(targetFieldName)) {
    return EMPTY_TEXT;
  }

  const availableFieldNames = new Set(fields.map((field) => field.name));
  const normalizedTargetFieldName = targetFieldName.trim().toLowerCase();
  const resourceActionSourceGroup = AUTO_CODE_SOURCE_GROUPS[0];

  for (const fieldGroup of AUTO_CODE_SOURCE_GROUPS) {
    if (!fieldGroup.every((fieldName) => availableFieldNames.has(fieldName))) {
      continue;
    }

    const parts = fieldGroup
      .map((fieldName) => getStringFormValue(values[fieldName]))
      .filter((value) => value.length > 0);

    if (parts.length !== fieldGroup.length) {
      continue;
    }

    if (fieldGroup === resourceActionSourceGroup) {
      return buildDelimitedCode(parts, { delimiter: '.', casing: 'lower' });
    }

    if (normalizedTargetFieldName === 'client_code') {
      return buildDelimitedCode(parts, { delimiter: '-', casing: 'upper' });
    }

    return buildDelimitedCode(parts, { delimiter: '-', casing: 'upper' });
  }

  const fallbackSourceFields = fields
    .filter(
      (field) =>
        field.name !== targetFieldName &&
        !isCodeFieldName(field.name) &&
        !isPasswordFieldName(field.name) &&
        /(title|name|label)/i.test(field.name),
    )
    .map((field) => getStringFormValue(values[field.name]))
    .filter((value) => value.length > 0);

  if (fallbackSourceFields.length > 0) {
    return buildDelimitedCode([fallbackSourceFields[0]], { delimiter: '-', casing: 'upper' });
  }

  return EMPTY_TEXT;
};

export const applyAutoGeneratedCodeFields = (
  fields: CrudFieldMeta[],
  previousValues: FormValues,
  nextValues: FormValues,
  changedFieldName?: string,
): FormValues => {
  const resolvedValues = cloneFormValues(nextValues);

  for (const field of fields) {
    if (field.readonly || !isCodeFieldName(field.name) || changedFieldName === field.name) {
      continue;
    }

    const currentFieldValue = getStringFormValue(previousValues[field.name]);
    const nextFieldValue = getStringFormValue(resolvedValues[field.name]);
    const currentGeneratedValue = buildAutoGeneratedCodeValue(fields, previousValues, field.name);
    const nextGeneratedValue = buildAutoGeneratedCodeValue(fields, resolvedValues, field.name);

    if (!nextGeneratedValue) {
      continue;
    }

    const shouldReplaceValue =
      nextFieldValue.length === 0 ||
      currentFieldValue.length === 0 ||
      currentFieldValue === currentGeneratedValue;

    if (shouldReplaceValue) {
      resolvedValues[field.name] = nextGeneratedValue;
    }
  }

  return resolvedValues;
};

export const getResourceUiConfig = (
  moduleKey: string,
  resourceKey: string,
): ResourceUiConfig | undefined => resourceUiConfigs[`${moduleKey}:${resourceKey}`];

export const resolveResourceCategoryGroupId = (
  resource: ResourceCategoryCandidate,
): ResourceCategoryGroupId => {
  if (resource.key.endsWith('-analytics')) {
    return 'analytics';
  }
  if (
    resource.moduleKey &&
    CATALOG_MODULE_RESOURCE_KEYS.has(`${resource.moduleKey}:${resource.key}`)
  ) {
    return 'catalogs';
  }
  if (FINANCE_RESOURCE_PERMISSION_PREFIXES.has(resource.permissionPrefix)) {
    return 'finance';
  }
  if (
    PEOPLE_RESOURCE_PERMISSION_PREFIXES.has(resource.permissionPrefix) ||
    PEOPLE_RESOURCE_KEYS.has(resource.key)
  ) {
    return 'people_clients';
  }
  if (WAREHOUSE_RESOURCE_PERMISSION_PREFIXES.has(resource.permissionPrefix)) {
    return 'warehouse';
  }
  return 'operations';
};

const RESOURCE_ICON_KEY_MAP: Record<string, string> = {
  batches: 'Barcode',
  'production-batches': 'Barcode',
  types: 'Tag',
  production: 'Factory',
  shipments: 'Truck',
  'chick-shipments': 'Truck',
  'product-shipments': 'Truck',
  'semi-product-shipments': 'Truck',
  arrivals: 'PackagePlus',
  processings: 'Scissors',
  'semi-products': 'Package',
  'stock-movements': 'ArrowRightLeft',
  warehouses: 'Warehouse',
  clients: 'Users',
  'factory-clients': 'Users',
  'client-debts': 'Receipt',
  'supplier-debts': 'ReceiptText',
  'debt-payments': 'HandCoins',
  employees: 'UserCog',
  positions: 'Briefcase',
  'expense-categories': 'FolderOpen',
  expenses: 'CreditCard',
  'cash-accounts': 'Landmark',
  'cash-transactions': 'ArrowLeftRight',
  currencies: 'CircleDollarSign',
  organizations: 'Building2',
  departments: 'Network',
  'department-modules': 'LayoutGrid',
  'poultry-types': 'Bird',
  'measurement-units': 'Ruler',
  'client-categories': 'Tags',
  roles: 'ShieldCheck',
  permissions: 'KeyRound',
  runs: 'IterationCcw',
  formulas: 'FlaskConical',
  ingredients: 'Leaf',
  'formula-ingredients': 'FlaskRound',
  flocks: 'Bird',
  'daily-logs': 'ClipboardList',
  'medicine-usages': 'Pill',
  'vaccination-plans': 'Syringe',
  'feed-consumptions': 'Wheat',
};

export const resolveResourceIconKey = (resourceKey: string): string =>
  RESOURCE_ICON_KEY_MAP[resourceKey] ?? 'FileText';

type BadgeVariant =
  | 'default'
  | 'secondary'
  | 'outline'
  | 'muted'
  | 'success'
  | 'warning'
  | 'destructive';

const POSTING_STATUS_BADGES: Record<string, { variant: BadgeVariant; label: string }> = {
  draft: { variant: 'muted', label: 'Черновик' },
  posted: { variant: 'success', label: 'Проведён' },
  reversed: { variant: 'destructive', label: 'Сторно' },
};

const SHIPMENT_STATUS_BADGES: Record<string, { variant: BadgeVariant; label: string }> = {
  sent: { variant: 'warning', label: 'Отправлено' },
  received: { variant: 'success', label: 'Принято' },
  discrepancy: { variant: 'destructive', label: 'Расхождение' },
};

const DEBT_PAYMENT_STATUS_BADGES: Record<string, { variant: BadgeVariant; label: string }> = {
  open: { variant: 'warning', label: 'Открыт' },
  partially_paid: { variant: 'default', label: 'Частично оплачен' },
  closed: { variant: 'success', label: 'Закрыт' },
  cancelled: { variant: 'muted', label: 'Отменён' },
};

export function getStatusBadge(
  fieldName: string,
  rawValue: unknown,
): { variant: BadgeVariant; label: string } | null {
  if (rawValue === null || rawValue === undefined) {
    return null;
  }
  const value = String(rawValue).trim().toLowerCase();
  if (!value) {
    return null;
  }
  if (fieldName === 'posting_status') {
    return POSTING_STATUS_BADGES[value] ?? null;
  }
  if (fieldName === 'status') {
    if (value in SHIPMENT_STATUS_BADGES) {
      return SHIPMENT_STATUS_BADGES[value];
    }
    if (value in DEBT_PAYMENT_STATUS_BADGES) {
      return DEBT_PAYMENT_STATUS_BADGES[value];
    }
    return null;
  }
  return null;
}

export const shouldExposeResourceInModule = (
  moduleKey: string,
  resource: { key: string; apiModuleKey?: string },
): boolean => Boolean(moduleKey.trim() || resource.key.trim());

export const sortFieldsByPreferredOrder = (
  fields: CrudFieldMeta[],
  preferredOrder?: string[],
): CrudFieldMeta[] => {
  if (!preferredOrder || preferredOrder.length === 0) {
    return fields;
  }

  const priority = new Map(preferredOrder.map((fieldName, index) => [fieldName, index]));

  return [...fields].sort((left, right) => {
    const leftPriority = priority.get(left.name);
    const rightPriority = priority.get(right.name);
    if (leftPriority === undefined && rightPriority === undefined) {
      return 0;
    }
    if (leftPriority === undefined) {
      return 1;
    }
    if (rightPriority === undefined) {
      return -1;
    }
    return leftPriority - rightPriority;
  });
};

export const getDepartmentLabel = (department: DepartmentRecord): string => {
  if (typeof department.name === 'string' && department.name) {
    return department.name;
  }
  if (typeof department.code === 'string' && department.code) {
    return department.code;
  }
  if (typeof department.id === 'string' && department.id) {
    return department.id;
  }
  return EMPTY_TEXT;
};

export const getReferenceOptionLabel = (
  field: CrudFieldMeta,
  optionValue: string,
  optionLabel: string,
  translate: (key: string, params?: Record<string, string | number>, fallback?: string) => string,
): string => {
  const readableLabel = getReadableReferenceLabel({
    fieldName: field.name,
    fieldLabel: field.label,
    optionValue,
    optionLabel,
  });

  if (field.name === 'module_key') {
    return readableLabel || translate(`modules.${optionValue}.label`, undefined, optionValue);
  }
  if (field.name === 'transaction_type') {
    return translate(
      `cashTransactionTypes.${optionValue}`,
      undefined,
      readableLabel || optionValue,
    );
  }
  if (field.name === 'status') {
    return translate(
      `clientDebtStatuses.${optionValue}`,
      undefined,
      readableLabel || humanizeKey(optionValue),
    );
  }
  if (field.name === 'item_type') {
    return translate(
      `inventory.itemTypes.${optionValue}`,
      undefined,
      readableLabel || humanizeKey(optionValue),
    );
  }
  if (field.name === 'movement_kind') {
    return translate(
      `inventory.movementKinds.${optionValue}`,
      undefined,
      readableLabel || humanizeKey(optionValue),
    );
  }
  if (field.name === 'unit') {
    return translate(`inventory.units.${optionValue}`, undefined, readableLabel || optionValue);
  }
  return readableLabel;
};

export const buildDepartmentScope = (
  selectedDepartmentId: string,
  childrenMap: Map<string, string[]>,
): Set<string> => {
  if (!selectedDepartmentId) {
    return new Set();
  }

  const scope = new Set<string>();
  const stack = [selectedDepartmentId];
  while (stack.length > 0) {
    const currentDepartmentId = stack.pop();
    if (!currentDepartmentId || scope.has(currentDepartmentId)) {
      continue;
    }
    scope.add(currentDepartmentId);
    for (const childId of childrenMap.get(currentDepartmentId) ?? []) {
      stack.push(childId);
    }
  }
  return scope;
};

type DepartmentOptionCandidate = {
  id: string;
};

export const resolveDefaultDepartmentSelection = (
  actorDepartmentId: string | null | undefined,
  departmentOptions: readonly DepartmentOptionCandidate[],
): string => {
  const normalizedActorDepartmentId =
    typeof actorDepartmentId === 'string' ? actorDepartmentId : '';
  if (normalizedActorDepartmentId) {
    const actorDepartmentOption = departmentOptions.find(
      (department) => department.id === normalizedActorDepartmentId,
    );
    if (actorDepartmentOption) {
      return actorDepartmentOption.id;
    }
  }

  return departmentOptions[0]?.id ?? '';
};

export const resolveDefaultFormDepartmentId = (
  selectedDepartmentId: string,
  actorDepartmentId: string | null | undefined,
  selectableDepartmentIds: ReadonlySet<string>,
  selectableDepartmentOptions: readonly DepartmentOptionCandidate[],
  scopedDepartmentIds: ReadonlySet<string>,
): string => {
  if (selectedDepartmentId && selectableDepartmentIds.has(selectedDepartmentId)) {
    return selectedDepartmentId;
  }

  const normalizedActorDepartmentId =
    typeof actorDepartmentId === 'string' ? actorDepartmentId : '';
  const actorDepartmentIsInScope =
    !selectedDepartmentId ||
    scopedDepartmentIds.size === 0 ||
    scopedDepartmentIds.has(normalizedActorDepartmentId);
  if (
    normalizedActorDepartmentId &&
    selectableDepartmentIds.has(normalizedActorDepartmentId) &&
    actorDepartmentIsInScope
  ) {
    return normalizedActorDepartmentId;
  }

  const scopedDepartmentOption =
    selectedDepartmentId && scopedDepartmentIds.size > 0
      ? selectableDepartmentOptions.find((department) => scopedDepartmentIds.has(department.id))
      : null;
  if (scopedDepartmentOption) {
    return scopedDepartmentOption.id;
  }

  return selectableDepartmentOptions[0]?.id ?? '';
};

export const getRecordId = (record: CrudRecord | null | undefined, idColumn: string): string => {
  const candidate = record?.[idColumn];
  if (typeof candidate === 'string' || typeof candidate === 'number') {
    return String(candidate);
  }
  return '';
};

export const getInputType = (field: CrudFieldMeta): string => {
  const fieldInputKind = getFieldInputKind(field);
  switch (fieldInputKind) {
    case 'password':
      return 'password';
    case 'email':
      return 'email';
    case 'tel':
      return 'tel';
    case 'integer':
    case 'number':
      return 'number';
    case 'date':
      return 'date';
    case 'time':
      return 'time';
    case 'datetime':
      return 'datetime-local';
    default:
      return 'text';
  }
};

export const formatDateValue = (value: unknown): string => {
  if (typeof value !== 'string') {
    return EMPTY_TEXT;
  }
  return value.slice(0, 10);
};

const formatDateTimeValue = (value: unknown): string => {
  if (typeof value !== 'string') {
    return EMPTY_TEXT;
  }
  const normalized = value.replace(/Z$/, '');
  return normalized.length >= 16 ? normalized.slice(0, 16) : normalized;
};

export const formatDateTimeDisplayValue = (value: unknown): string => {
  const normalized = formatDateTimeValue(value);
  return normalized ? normalized.replace('T', ' ') : EMPTY_TEXT;
};

const formatTimeValue = (value: unknown): string => {
  if (typeof value !== 'string') {
    return EMPTY_TEXT;
  }
  const normalized = value.trim();
  if (!normalized) {
    return EMPTY_TEXT;
  }
  if (normalized.includes('T')) {
    const timePart = normalized.split('T')[1] ?? normalized;
    return timePart.slice(0, 5);
  }
  return normalized.slice(0, 5);
};

export const getInputProps = (field: CrudFieldMeta) => {
  const fieldInputKind = getFieldInputKind(field);
  switch (fieldInputKind) {
    case 'integer':
      return { inputMode: 'numeric' as const, step: '1' };
    case 'number':
      return { inputMode: 'decimal' as const, step: 'any' };
    case 'email':
      return { inputMode: 'email' as const, autoComplete: 'email' };
    case 'tel':
      return { inputMode: 'tel' as const, autoComplete: 'tel' };
    case 'password':
      return { autoComplete: 'new-password' };
    case 'date':
    case 'time':
    case 'datetime':
      return fieldInputKind === 'time'
        ? { autoComplete: 'off', step: '60' }
        : { autoComplete: 'off' };
    default:
      return {};
  }
};

const normalizeReferenceCandidateValue = (
  value: unknown,
  options: { allowNonUuidFallback?: boolean } = {},
): string => {
  if (typeof value === 'string') {
    return value.trim();
  }
  if (typeof value === 'number' || typeof value === 'bigint') {
    return String(value).trim();
  }
  if (Array.isArray(value)) {
    return '';
  }
  if (value && typeof value === 'object') {
    const recordValue = value as {
      id?: unknown;
      value?: unknown;
      uuid?: unknown;
      code?: unknown;
      slug?: unknown;
    };

    if (typeof recordValue.id === 'string' && recordValue.id.trim()) {
      return recordValue.id.trim();
    }
    if (typeof recordValue.value === 'string' && recordValue.value.trim()) {
      const resolved = recordValue.value.trim();
      if (options.allowNonUuidFallback || isValidUuid(resolved)) {
        return resolved;
      }
      return '';
    }
    if (typeof recordValue.uuid === 'string' && recordValue.uuid.trim()) {
      return recordValue.uuid.trim();
    }
    if (
      options.allowNonUuidFallback &&
      typeof recordValue.code === 'string' &&
      recordValue.code.trim()
    ) {
      return recordValue.code.trim();
    }
    if (
      options.allowNonUuidFallback &&
      typeof recordValue.slug === 'string' &&
      recordValue.slug.trim()
    ) {
      return recordValue.slug.trim();
    }
  }
  return '';
};

const resolveReferenceOptionValue = (
  rawValue: string,
  reference: CrudFieldReference | null,
): string | null => {
  if (!reference || reference.options.length === 0) {
    return null;
  }
  const exactOption = reference.options.find((option) => option.value === rawValue);
  if (exactOption) {
    return exactOption.value;
  }
  const normalizedSearch = rawValue.trim().toLowerCase();
  if (!normalizedSearch) {
    return null;
  }
  const labelOption = reference.options.find(
    (option) => option.label.trim().toLowerCase() === normalizedSearch,
  );
  return labelOption ? labelOption.value : null;
};

export const buildFormValues = (fields: CrudFieldMeta[], record: CrudRecord | null): FormValues => {
  const values: FormValues = {};
  for (const field of fields) {
    const currentValue = record?.[field.name];
    const fieldInputKind = getFieldInputKind(field);

    if (isMultiReferenceField(field)) {
      if (Array.isArray(currentValue)) {
        values[field.name] = currentValue
          .map((item) =>
            normalizeReferenceCandidateValue(item, { allowNonUuidFallback: field.type !== 'uuid' }),
          )
          .filter((item) => item.length > 0);
        continue;
      }
      if (currentValue === null || currentValue === undefined || currentValue === '') {
        values[field.name] = [];
        continue;
      }
      values[field.name] = [
        normalizeReferenceCandidateValue(currentValue, {
          allowNonUuidFallback: field.type !== 'uuid',
        }),
      ];
      continue;
    }

    if (fieldInputKind === 'boolean') {
      values[field.name] = Boolean(currentValue);
      continue;
    }
    if (fieldInputKind === 'password') {
      values[field.name] = EMPTY_TEXT;
      continue;
    }
    if (currentValue === null || currentValue === undefined) {
      values[field.name] = EMPTY_TEXT;
      continue;
    }
    if (fieldInputKind === 'date') {
      values[field.name] = formatDateValue(currentValue);
      continue;
    }
    if (fieldInputKind === 'time') {
      values[field.name] = formatTimeValue(currentValue);
      continue;
    }
    if (fieldInputKind === 'datetime') {
      values[field.name] = formatDateTimeValue(currentValue);
      continue;
    }
    if (fieldInputKind === 'json') {
      values[field.name] =
        typeof currentValue === 'string' ? currentValue : JSON.stringify(currentValue, null, 2);
      continue;
    }
    if (field.reference) {
      values[field.name] = normalizeReferenceCandidateValue(currentValue, {
        allowNonUuidFallback: field.type !== 'uuid',
      });
      continue;
    }
    values[field.name] = String(currentValue);
  }

  return values;
};

export const cloneFormValues = (values: FormValues): FormValues => {
  const nextValues: FormValues = {};
  for (const [fieldName, fieldValue] of Object.entries(values)) {
    nextValues[fieldName] = Array.isArray(fieldValue) ? [...fieldValue] : fieldValue;
  }
  return nextValues;
};

const normalizeFormValueForComparison = (
  value: string | boolean | string[] | undefined,
): string => {
  if (Array.isArray(value)) {
    return JSON.stringify(value);
  }
  if (typeof value === 'boolean') {
    return value ? '1' : '0';
  }
  if (typeof value === 'string') {
    return value;
  }
  return '';
};

export const areFormValuesEqual = (left: FormValues, right: FormValues): boolean => {
  const allFieldNames = new Set([...Object.keys(left), ...Object.keys(right)]);
  for (const fieldName of allFieldNames) {
    if (
      normalizeFormValueForComparison(left[fieldName]) !==
      normalizeFormValueForComparison(right[fieldName])
    ) {
      return false;
    }
  }
  return true;
};

export const getDisplayValue = (
  field: CrudFieldMeta,
  value: unknown,
  yesLabel: string,
  noLabel: string,
  emptyLabel: string,
  translateReferenceLabel?: (
    field: CrudFieldMeta,
    optionValue: string,
    optionLabel: string,
  ) => string,
): string => {
  const fieldInputKind = getFieldInputKind(field);

  if (value === null || value === undefined || value === '') {
    return emptyLabel;
  }
  if (fieldInputKind === 'password') {
    return MASKED_PASSWORD_VALUE;
  }
  if (isMultiReferenceField(field) && Array.isArray(value)) {
    const labels = value
      .map((item) => normalizeReferenceCandidateValue(item))
      .filter((item) => item.length > 0)
      .map((item) => {
        const matchedOption = field.reference?.options.find((option) => option.value === item);
        if (!matchedOption) {
          return item;
        }
        return translateReferenceLabel
          ? translateReferenceLabel(field, matchedOption.value, matchedOption.label)
          : matchedOption.label;
      });
    return labels.length > 0 ? labels.join(', ') : emptyLabel;
  }

  if (field.reference?.options.length) {
    const matchedOption = field.reference.options.find((option) => option.value === String(value));
    if (matchedOption) {
      return translateReferenceLabel
        ? translateReferenceLabel(field, matchedOption.value, matchedOption.label)
        : matchedOption.label;
    }
  }

  if (field.reference) {
    const fallbackValue = String(value);
    return getReadableReferenceLabel({
      fieldName: field.name,
      fieldLabel: field.label,
      optionValue: fallbackValue,
      optionLabel: fallbackValue,
    });
  }

  if (fieldInputKind === 'boolean') {
    return value === true ? yesLabel : noLabel;
  }
  if (fieldInputKind === 'date') {
    return formatDateValue(value);
  }
  if (fieldInputKind === 'time') {
    return formatTimeValue(value);
  }
  if (fieldInputKind === 'datetime') {
    return formatDateTimeDisplayValue(value);
  }
  if (fieldInputKind === 'json') {
    return typeof value === 'string' ? value : JSON.stringify(value);
  }

  return String(value);
};

export const getTableFields = (fields: CrudFieldMeta[], idColumn: string): CrudFieldMeta[] => {
  const preferredFields = fields.filter(
    (field) =>
      field.name !== idColumn &&
      !isPasswordFieldName(field.name) &&
      !(field.type === 'uuid' && !field.reference) &&
      field.type !== 'json' &&
      field.name !== 'created_at' &&
      field.name !== 'updated_at' &&
      field.name !== 'deleted_at',
  );
  if (preferredFields.length > 0) {
    return preferredFields.slice(0, 6);
  }
  return fields
    .filter(
      (field) =>
        !isPasswordFieldName(field.name) &&
        field.type !== 'json' &&
        field.name !== 'created_at' &&
        field.name !== 'updated_at' &&
        field.name !== 'deleted_at',
    )
    .slice(0, 6);
};

export const isAuditSnapshot = (value: unknown): value is AuditSnapshot => {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
};

export const isStructuredAuditValue = (value: unknown): boolean => {
  if (Array.isArray(value)) {
    return value.some((item) => typeof item === 'object' && item !== null);
  }
  return typeof value === 'object' && value !== null;
};

const parseFieldValue = (
  field: CrudFieldMeta,
  rawValue: unknown,
  mode: SubmitMode,
  requiredMessage: string,
  integerMessage: string,
  numberMessage: string,
  invalidJsonMessage: string,
  invalidUuidMessage: string,
): { ok: true; value?: unknown } | { ok: false; message: string } => {
  const fieldInputKind = getFieldInputKind(field);

  if (field.readonly || field.name === 'id') {
    return { ok: true };
  }

  if (isMultiReferenceField(field)) {
    const values = (
      Array.isArray(rawValue) ? rawValue : typeof rawValue === 'string' ? [rawValue] : []
    )
      .map((item) =>
        normalizeReferenceCandidateValue(item, { allowNonUuidFallback: field.type !== 'uuid' }),
      )
      .filter((item) => item.length > 0)
      .map((item) => resolveReferenceOptionValue(item, field.reference) ?? item)
      .filter((item) => item.length > 0);

    if (
      field.type === 'uuid' &&
      values.some((item) => {
        return (
          !isValidUuid(item) && !field.reference?.options.some((option) => option.value === item)
        );
      })
    ) {
      return { ok: false, message: invalidUuidMessage };
    }
    if (values.length === 0 && field.required) {
      return { ok: false, message: requiredMessage };
    }

    return { ok: true, value: Array.from(new Set(values)) };
  }

  if (fieldInputKind === 'boolean') {
    return { ok: true, value: Boolean(rawValue) };
  }

  const value = normalizeReferenceCandidateValue(rawValue, {
    allowNonUuidFallback: field.type !== 'uuid',
  });
  const isPasswordField = field.name.toLowerCase().includes('password');

  if (value === EMPTY_TEXT) {
    if (isPasswordField && mode === 'update') {
      return { ok: true };
    }
    if (field.nullable) {
      return { ok: true, value: null };
    }
    if (field.required) {
      return { ok: false, message: requiredMessage };
    }
    return { ok: true };
  }

  if (fieldInputKind === 'integer') {
    const parsed = Number(value);
    if (!Number.isInteger(parsed)) {
      return { ok: false, message: integerMessage };
    }
    return { ok: true, value: parsed };
  }
  if (fieldInputKind === 'number') {
    const parsed = Number(value);
    if (Number.isNaN(parsed)) {
      return { ok: false, message: numberMessage };
    }
    return { ok: true, value: parsed };
  }
  if (fieldInputKind === 'json') {
    try {
      return { ok: true, value: JSON.parse(value) };
    } catch {
      return { ok: false, message: invalidJsonMessage };
    }
  }
  if (field.type === 'uuid') {
    const resolvedReferenceValue = resolveReferenceOptionValue(value, field.reference);
    if (resolvedReferenceValue !== null) {
      return { ok: true, value: resolvedReferenceValue };
    }
    if (!isValidUuid(value)) {
      return { ok: false, message: invalidUuidMessage };
    }
    return { ok: true, value };
  }
  return { ok: true, value };
};

export const buildPayload = (
  fields: CrudFieldMeta[],
  values: FormValues,
  mode: SubmitMode,
  requiredMessage: string,
  integerMessage: string,
  numberMessage: string,
  invalidJsonMessage: string,
  invalidUuidMessage: string,
  idColumn: string,
): { payload: CrudRecord; errors: FormErrors } => {
  const preparedValues = applyAutoGeneratedCodeFields(fields, values, values);
  const payload: CrudRecord = {};
  const errors: FormErrors = {};

  for (const field of fields) {
    if (field.name === idColumn || field.name === 'id') {
      continue;
    }

    const parsed = parseFieldValue(
      field,
      preparedValues[field.name],
      mode,
      requiredMessage,
      integerMessage,
      numberMessage,
      invalidJsonMessage,
      invalidUuidMessage,
    );

    if (!parsed.ok) {
      errors[field.name] = parsed.message;
      continue;
    }

    if ('value' in parsed) {
      payload[field.name] = parsed.value;
    }
  }

  return { payload: sanitizePayload(payload, idColumn), errors };
};
