import { useCallback, useEffect, useState } from 'react';

import {
  getClientNotificationContext,
  sendBulkClientNotifications,
  sendClientNotification,
  type ClientNotificationBulkResult,
  type ClientNotificationContext,
  type ClientNotificationSendResult,
  type CrudRecord,
} from '@/shared/api/backend-crud';
import { baseQueryKeys, toQueryKey } from '@/shared/api/query-keys';
import { useApiMutation, useApiQuery } from '@/shared/api/react-query';

import { getRecordId } from '../module-crud-page.helpers';

import {
  CLIENT_NOTIFICATION_FALLBACK_TEMPLATES,
  type ClientNotificationTemplateKey,
} from './constants';

type TranslateFn = (
  key: string,
  params?: Record<string, string | number>,
  fallback?: string,
) => string;

export interface UseClientNotificationsOptions {
  t: TranslateFn;
  moduleKey: string;
  idColumn: string;
  isClientResource: boolean;
  canSendClientNotifications: boolean;
  canExecuteClientNotification: () => boolean;
  departmentId: string;
  visibleClientIds: string[];
  getRecordSummaryLabel: (record: CrudRecord) => string;
  setOperationMessage: (message: string) => void;
}

export function useClientNotifications(options: UseClientNotificationsOptions) {
  const {
    t,
    moduleKey,
    idColumn,
    isClientResource,
    canSendClientNotifications,
    canExecuteClientNotification,
    departmentId,
    visibleClientIds,
    getRecordSummaryLabel,
    setOperationMessage,
  } = options;

  const [isSheetOpen, setIsSheetOpen] = useState(false);
  const [isBulkMode, setIsBulkMode] = useState(false);
  const [targetId, setTargetId] = useState('');
  const [targetLabel, setTargetLabel] = useState('');
  const [templateKey, setTemplateKey] = useState<ClientNotificationTemplateKey>('debt_reminder');
  const [message, setMessage] = useState('');
  const [messageTouched, setMessageTouched] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [bulkResult, setBulkResult] = useState<ClientNotificationBulkResult | null>(null);

  const contextQuery = useApiQuery<ClientNotificationContext>({
    queryKey: [
      ...baseQueryKeys.crud.resource('core', 'client-notification-context'),
      targetId || 'none',
      departmentId || 'all',
    ],
    queryFn: () =>
      getClientNotificationContext(targetId, {
        departmentId: departmentId || undefined,
      }),
    enabled: canSendClientNotifications && isSheetOpen && !isBulkMode && targetId.length > 0,
  });

  const templates = isBulkMode
    ? CLIENT_NOTIFICATION_FALLBACK_TEMPLATES
    : (contextQuery.data?.templates ?? CLIENT_NOTIFICATION_FALLBACK_TEMPLATES);

  const activeTemplate =
    templates.length === 0
      ? null
      : (templates.find((template) => template.key === templateKey) ?? templates[0]);

  const sendMutation = useApiMutation<
    ClientNotificationSendResult,
    Error,
    { templateKey: ClientNotificationTemplateKey; message: string }
  >({
    mutationKey: toQueryKey('core', 'client-notify', moduleKey || 'unknown'),
    mutationFn: (payload) => {
      if (!canExecuteClientNotification()) {
        throw new Error('Недостаточно прав для отправки уведомлений.');
      }
      if (!targetId) {
        throw new Error('Client is not selected');
      }
      return sendClientNotification(targetId, {
        templateKey: payload.templateKey,
        message: payload.message,
        channel: 'telegram',
        departmentId: departmentId || undefined,
      });
    },
    onSuccess: (result) => {
      if (result.sent) {
        setFeedback(
          t('crud.clientNotificationSent', undefined, 'Уведомление отправлено в Telegram.'),
        );
        return;
      }
      setFeedback(
        result.error ||
          t('crud.clientNotificationSendFailed', undefined, 'Не удалось отправить уведомление.'),
      );
    },
  });

  const sendBulkMutation = useApiMutation<
    ClientNotificationBulkResult,
    Error,
    { templateKey: ClientNotificationTemplateKey; message: string; clientIds: string[] }
  >({
    mutationKey: toQueryKey('core', 'client-notify-bulk', moduleKey || 'unknown'),
    mutationFn: (payload) => {
      if (!canExecuteClientNotification()) {
        throw new Error('Недостаточно прав для отправки уведомлений.');
      }
      return sendBulkClientNotifications({
        clientIds: payload.clientIds,
        templateKey: payload.templateKey,
        message: payload.message,
        channel: 'telegram',
        departmentId: departmentId || undefined,
      });
    },
    onSuccess: (result) => {
      setBulkResult(result);
      setFeedback(
        t(
          'crud.clientNotificationBulkSent',
          { sent: result.sent, failed: result.failed },
          `Отправлено: ${result.sent}, ошибок: ${result.failed}.`,
        ),
      );
    },
  });

  const pendingAction = sendMutation.isPending || sendBulkMutation.isPending;
  const error = sendMutation.error ?? sendBulkMutation.error ?? null;
  const isSendDisabled =
    pendingAction ||
    message.trim().length === 0 ||
    (isBulkMode
      ? visibleClientIds.length === 0
      : !targetId || contextQuery.isLoading || Boolean(contextQuery.error));

  const sendMutationReset = sendMutation.reset;
  const sendBulkMutationReset = sendBulkMutation.reset;
  const resetState = useCallback(() => {
    setTargetId('');
    setTargetLabel('');
    setTemplateKey('debt_reminder');
    setMessage('');
    setMessageTouched(false);
    setFeedback('');
    setBulkResult(null);
    sendMutationReset();
    sendBulkMutationReset();
  }, [sendBulkMutationReset, sendMutationReset]);

  const resetSheetState = useCallback(() => {
    setIsSheetOpen(false);
    setIsBulkMode(false);
    setTargetId('');
    setTargetLabel('');
    setTemplateKey('debt_reminder');
    setMessage('');
    setMessageTouched(false);
    setFeedback('');
    setBulkResult(null);
  }, []);

  const handleOpen = useCallback(
    (record: CrudRecord) => {
      if (!canExecuteClientNotification()) {
        return;
      }
      const recordId = getRecordId(record, idColumn);
      if (!recordId) {
        return;
      }
      setIsBulkMode(false);
      setTargetId(recordId);
      setTargetLabel(getRecordSummaryLabel(record));
      setTemplateKey('debt_reminder');
      setMessage('');
      setMessageTouched(false);
      setFeedback('');
      setBulkResult(null);
      setIsSheetOpen(true);
    },
    [canExecuteClientNotification, getRecordSummaryLabel, idColumn],
  );

  const handleOpenBulk = useCallback(() => {
    if (!canExecuteClientNotification()) {
      return;
    }
    if (visibleClientIds.length === 0) {
      setOperationMessage(
        t('crud.clientNotificationNoClients', undefined, 'Нет клиентов для массовой рассылки.'),
      );
      return;
    }
    setIsBulkMode(true);
    setTargetId('');
    setTargetLabel('');
    setTemplateKey('debt_reminder');
    setMessage('');
    setMessageTouched(false);
    setFeedback('');
    setBulkResult(null);
    setIsSheetOpen(true);
  }, [canExecuteClientNotification, setOperationMessage, t, visibleClientIds.length]);

  const handleSend = useCallback(() => {
    if (!canExecuteClientNotification()) {
      return;
    }
    if (pendingAction) {
      return;
    }
    if (isBulkMode) {
      void sendBulkMutation.mutateAsync({
        templateKey,
        message: message.trim(),
        clientIds: visibleClientIds,
      });
      return;
    }
    if (!targetId) {
      setFeedback(t('crud.clientNotificationNoTarget', undefined, 'Клиент не выбран.'));
      return;
    }
    void sendMutation.mutateAsync({
      templateKey,
      message: message.trim(),
    });
  }, [
    canExecuteClientNotification,
    isBulkMode,
    message,
    pendingAction,
    sendBulkMutation,
    sendMutation,
    targetId,
    templateKey,
    t,
    visibleClientIds,
  ]);

  useEffect(() => {
    if (!isSheetOpen || messageTouched) {
      return;
    }
    const templateMessage = activeTemplate ? activeTemplate.message : '';
    if (!templateMessage) {
      return;
    }
    setMessage(templateMessage);
  }, [activeTemplate, isSheetOpen, messageTouched]);

  useEffect(() => {
    if (isSheetOpen || !isClientResource) {
      return;
    }
    resetState();
  }, [isClientResource, isSheetOpen, resetState]);

  return {
    isSheetOpen,
    setIsSheetOpen,
    isBulkMode,
    targetLabel,
    message,
    setMessage,
    setMessageTouched,
    templateKey,
    setTemplateKey,
    templates,
    feedback,
    bulkResult,
    contextQuery,
    pendingAction,
    error,
    isSendDisabled,
    resetState,
    resetSheetState,
    handleOpen,
    handleOpenBulk,
    handleSend,
  };
}
