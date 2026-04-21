import { apiClient } from './api-client';

export type CrudRecord = Record<string, unknown>;

export type WorkspaceResourceConfig = {
  id: string;
  module_key: string;
  key: string;
  label: string;
  name?: string;
  path: string;
  description?: string | null;
  permission_prefix: string;
  api_module_key?: string | null;
  sort_order?: number;
  is_head_visible?: boolean;
  is_active?: boolean;
};

export type WorkspaceModuleConfig = {
  id: string;
  key: string;
  label: string;
  name?: string;
  description?: string | null;
  icon?: string | null;
  sort_order?: number;
  is_department_assignable?: boolean;
  analytics_section_key?: string | null;
  implicit_read_permissions?: string[];
  analytics_read_permissions?: string[];
  is_active?: boolean;
  resources: WorkspaceResourceConfig[];
};

export type CrudListResponse = {
  items: CrudRecord[];
  total?: number;
};

export type CrudListOptions = {
  limit?: number;
  offset?: number;
  orderBy?: string;
  search?: string;
  departmentId?: string;
  departmentIds?: string[];
};

export type CrudReferenceOption = {
  value: string;
  label: string;
};

export type CrudFieldReference = {
  table: string;
  column: string;
  label_column: string;
  options: CrudReferenceOption[];
  multiple?: boolean;
};

export type CrudFieldType =
  | 'string'
  | 'uuid'
  | 'integer'
  | 'number'
  | 'boolean'
  | 'date'
  | 'time'
  | 'datetime'
  | 'json';

export type CrudFieldMeta = {
  name: string;
  label: string;
  type: CrudFieldType;
  database_type: string;
  nullable: boolean;
  required: boolean;
  readonly: boolean;
  has_default: boolean;
  is_primary_key: boolean;
  is_foreign_key: boolean;
  reference: CrudFieldReference | null;
};

export type CrudResourceMeta = {
  resource: string;
  table: string;
  id_column: string;
  fields: CrudFieldMeta[];
};

export type CrudReferenceOptionsResponse = {
  field: string;
  options: CrudReferenceOption[];
  multiple: boolean;
};

export type CrudAuditAction = 'create' | 'update' | 'delete';

export type CrudAuditEntry = {
  id: string;
  organization_id?: string | null;
  actor_id?: string | null;
  entity_table: string;
  entity_id: string;
  action: CrudAuditAction;
  actor_username?: string | null;
  actor_roles?: string[] | null;
  changed_fields?: string[] | null;
  before_data?: Record<string, unknown> | null;
  after_data?: Record<string, unknown> | null;
  context_data?: Record<string, unknown> | null;
  changed_at: string;
};

export type CrudAuditResponse = {
  items: CrudAuditEntry[];
  total: number;
  limit?: number;
  offset?: number;
  has_more?: boolean;
};

export type ClientNotificationTemplate = {
  key: string;
  title: string;
  description?: string;
  message: string;
};

export type ClientNotificationContext = {
  client: {
    id: string;
    name: string;
    phone?: string | null;
    email?: string | null;
    telegram_chat_id?: string | null;
  };
  debt_summary: {
    open_count: number;
    total_amount: string;
    paid_amount: string;
    outstanding_amount: string;
    currency: string;
  };
  recent_debts: CrudRecord[];
  recent_purchases: CrudRecord[];
  templates: ClientNotificationTemplate[];
};

export type ClientNotificationSendPayload = {
  templateKey: string;
  message?: string;
  channel?: 'telegram';
  departmentId?: string;
};

export type ClientNotificationSendResult = {
  client_id: string;
  template_key: string;
  channel: string;
  sent: boolean;
  provider_message_id?: string | null;
  error?: string | null;
  message?: string;
};

export type ClientNotificationBulkPayload = {
  clientIds: string[];
  templateKey: string;
  message?: string;
  channel?: 'telegram';
  departmentId?: string;
};

export type ClientNotificationBulkResult = {
  total: number;
  sent: number;
  failed: number;
  items: ClientNotificationSendResult[];
};

const buildPath = (
  resourcePath: string,
  searchParams: Record<string, string | number | undefined | string[]>,
): string => {
  const params = new URLSearchParams();

  Object.entries(searchParams).forEach(([key, value]) => {
    if (Array.isArray(value)) {
      value
        .map((item) => item.trim())
        .filter((item) => item.length > 0)
        .forEach((item) => params.append(key, item));
      return;
    }

    if (value === undefined || value === '') {
      return;
    }

    params.set(key, String(value));
  });

  const queryString = params.toString();
  return queryString ? `${resourcePath}?${queryString}` : resourcePath;
};

export const listCrudRecords = (
  moduleKey: string,
  resourcePath: string,
  options: CrudListOptions = {},
) => {
  const departmentParam: string | string[] | undefined =
    options.departmentIds && options.departmentIds.length > 0
      ? options.departmentIds
      : options.departmentId?.trim() || undefined;
  const path = buildPath(resourcePath, {
    limit: options.limit ?? 1000,
    offset: options.offset,
    order_by: options.orderBy,
    search: options.search?.trim() || undefined,
    department_id: departmentParam,
  });
  return apiClient.get<CrudListResponse>(`/${moduleKey}/${path}`);
};

export const listVisibleDepartments = () => {
  return apiClient.get<CrudListResponse>('/core/visible-departments');
};

export const listWorkspaceModules = () => {
  return apiClient.get<CrudListResponse>('/core/workspace-modules');
};

export const getCrudResourceMeta = (
  moduleKey: string,
  resourcePath: string,
  options: { departmentId?: string; departmentIds?: string[] } = {},
) => {
  const ids =
    options.departmentIds && options.departmentIds.length > 0
      ? options.departmentIds
      : options.departmentId
        ? [options.departmentId]
        : [];
  const departmentParam: string | string[] | undefined =
    ids.length > 1 ? ids : ids.length === 1 ? ids[0] : undefined;
  const path = buildPath(`${resourcePath}/meta`, {
    department_id: departmentParam,
  });
  return apiClient.get<CrudResourceMeta>(`/${moduleKey}/${path}`);
};

export const getCrudReferenceOptions = (
  moduleKey: string,
  resourcePath: string,
  fieldName: string,
  options: {
    search?: string;
    values?: string[];
    limit?: number;
    extraParams?: Record<string, string | number | undefined | string[]>;
  } = {},
) => {
  const path = buildPath(`${resourcePath}/meta/reference-options`, {
    field: fieldName,
    search: options.search?.trim() || undefined,
    values: options.values ?? [],
    limit: options.limit ?? 25,
    ...(options.extraParams ?? {}),
  });
  return apiClient.get<CrudReferenceOptionsResponse>(`/${moduleKey}/${path}`);
};

export const getCrudRecord = (moduleKey: string, resourcePath: string, recordId: string) => {
  return apiClient.get<CrudRecord>(`/${moduleKey}/${resourcePath}/${recordId}`);
};

export const createCrudRecord = (moduleKey: string, resourcePath: string, payload: CrudRecord) => {
  return apiClient.post<CrudRecord, CrudRecord>(`/${moduleKey}/${resourcePath}`, payload);
};

export const updateCrudRecord = (
  moduleKey: string,
  resourcePath: string,
  recordId: string,
  payload: CrudRecord,
) => {
  return apiClient.put<CrudRecord, CrudRecord>(
    `/${moduleKey}/${resourcePath}/${recordId}`,
    payload,
  );
};

export const deleteCrudRecord = (moduleKey: string, resourcePath: string, recordId: string) => {
  return apiClient.delete<{ deleted?: boolean }>(`/${moduleKey}/${resourcePath}/${recordId}`);
};

export interface AcknowledgeShipmentPayload {
  received_quantity: number | string;
  note?: string;
}

export const acknowledgeShipment = (
  moduleKey: string,
  resourcePath: string,
  recordId: string,
  payload: AcknowledgeShipmentPayload,
) => {
  return apiClient.post<CrudRecord, AcknowledgeShipmentPayload>(
    `/${moduleKey}/${resourcePath}/${recordId}/acknowledge`,
    payload,
  );
};

export interface AdvanceBalance {
  advance_id: string;
  amount_issued: string;
  amount_reconciled: string;
  amount_returned: string;
  amount_outstanding: string;
  currency: string | null;
  status: string | null;
}

export const getAdvanceBalance = (advanceId: string) => {
  return apiClient.get<AdvanceBalance>(`/finance/advances/${advanceId}/balance`);
};

export const getCrudRecordAuditHistory = (
  moduleKey: string,
  resourcePath: string,
  recordId: string,
  options: { limit?: number; offset?: number } = {},
) => {
  const path = buildPath(`${resourcePath}/${recordId}/audit`, {
    limit: options.limit ?? 100,
    offset: options.offset ?? 0,
  });
  return apiClient.get<CrudAuditResponse>(`/${moduleKey}/${path}`);
};

export const getClientNotificationContext = (
  clientId: string,
  options: { departmentId?: string } = {},
) => {
  const path = buildPath(`/core/clients/${clientId}/notification-context`, {
    department_id: options.departmentId?.trim() || undefined,
  });
  return apiClient.get<ClientNotificationContext>(path);
};

export const sendClientNotification = (
  clientId: string,
  payload: ClientNotificationSendPayload,
) => {
  return apiClient.post<ClientNotificationSendResult, Record<string, unknown>>(
    `/core/clients/${clientId}/notify`,
    {
      template_key: payload.templateKey,
      message: payload.message ?? undefined,
      channel: payload.channel ?? 'telegram',
      department_id: payload.departmentId ?? undefined,
    },
  );
};

export const sendBulkClientNotifications = (payload: ClientNotificationBulkPayload) => {
  return apiClient.post<ClientNotificationBulkResult, Record<string, unknown>>(
    '/core/clients/notify/bulk',
    {
      client_ids: payload.clientIds,
      template_key: payload.templateKey,
      message: payload.message ?? undefined,
      channel: payload.channel ?? 'telegram',
      department_id: payload.departmentId ?? undefined,
    },
  );
};

export type SystemAuditListOptions = {
  search?: string;
  entityTable?: string;
  entityId?: string;
  action?: CrudAuditAction | '';
  actorId?: string;
  changedFrom?: string;
  changedTo?: string;
  limit?: number;
  offset?: number;
};

export const listSystemAuditLogs = (options: SystemAuditListOptions = {}) => {
  const path = buildPath('/system/audit', {
    search: options.search?.trim() || undefined,
    entity_table: options.entityTable?.trim() || undefined,
    entity_id: options.entityId?.trim() || undefined,
    action: options.action?.trim() || undefined,
    actor_id: options.actorId?.trim() || undefined,
    changed_from: options.changedFrom?.trim() || undefined,
    changed_to: options.changedTo?.trim() || undefined,
    limit: options.limit ?? 20,
    offset: options.offset ?? 0,
  });
  return apiClient.get<CrudAuditResponse>(path);
};
