import { History, Paperclip, Pencil, QrCode, Send, Trash2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import type { CrudRecord } from '@/shared/api/backend-crud';
import { cn } from '@/shared/lib/cn';

import { EMPTY_TEXT, getRecordId } from '../module-crud-page.helpers';

import type { MouseEvent as ReactMouseEvent, ReactNode } from 'react';

export interface RecordActionButtonsProps {
  record: CrudRecord;
  idColumn: string;
  deleteConfirmRecordId: string;
  pendingAction: boolean;
  notificationPendingAction: boolean;
  deleteConfirmLabel: string;
  deleteConfirmClassName: string;
  labels: {
    qr: string;
    attachFile: string;
    notify: string;
    edit: string;
    history: string;
    delete: string;
  };
  isMedicineBatchesResource: boolean;
  canManageMedicineBatchOps: boolean;
  canSendClientNotifications: boolean;
  canEditActiveResource: boolean;
  canReadAuditActiveResource: boolean;
  canDeleteActiveResource: boolean;
  isMedicineBatchActionBusy: (recordId: string) => boolean;
  onOpenMedicineBatchQrCenter: (record: CrudRecord) => void | Promise<void>;
  onOpenMedicineBatchAttachmentPicker: (record: CrudRecord) => void;
  onOpenClientNotification: (record: CrudRecord) => void;
  onEditRecord: (record: CrudRecord) => void;
  onOpenAudit: (record: CrudRecord) => void;
  onDeleteRecord: (event: ReactMouseEvent<HTMLButtonElement>, record: CrudRecord) => void;
}

export function renderRecordActionButtons({
  record,
  idColumn,
  deleteConfirmRecordId,
  pendingAction,
  notificationPendingAction,
  deleteConfirmLabel,
  deleteConfirmClassName,
  labels,
  isMedicineBatchesResource,
  canManageMedicineBatchOps,
  canSendClientNotifications,
  canEditActiveResource,
  canReadAuditActiveResource,
  canDeleteActiveResource,
  isMedicineBatchActionBusy,
  onOpenMedicineBatchQrCenter,
  onOpenMedicineBatchAttachmentPicker,
  onOpenClientNotification,
  onEditRecord,
  onOpenAudit,
  onDeleteRecord,
}: RecordActionButtonsProps): ReactNode[] {
  const recordId = getRecordId(record, idColumn);
  const actionKeyPrefix = recordId || 'record';
  const isDeleteConfirming = recordId !== EMPTY_TEXT && deleteConfirmRecordId === recordId;
  const isMedicineBatchBusy =
    isMedicineBatchesResource && recordId !== EMPTY_TEXT
      ? isMedicineBatchActionBusy(recordId)
      : false;
  const buttons: ReactNode[] = [];

  if (isMedicineBatchesResource) {
    buttons.push(
      <Button
        key={`${actionKeyPrefix}-qr`}
        type="button"
        size="sm"
        variant="outline"
        className="border-border/75 bg-card"
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          void onOpenMedicineBatchQrCenter(record);
        }}
        disabled={pendingAction || isMedicineBatchBusy}
      >
        <QrCode className="h-3.5 w-3.5" />
        {labels.qr}
      </Button>,
    );

    if (canManageMedicineBatchOps) {
      buttons.push(
        <Button
          key={`${actionKeyPrefix}-file`}
          type="button"
          size="sm"
          variant="outline"
          className="border-border/75 bg-card"
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            onOpenMedicineBatchAttachmentPicker(record);
          }}
          disabled={pendingAction || isMedicineBatchBusy}
        >
          <Paperclip className="h-3.5 w-3.5" />
          {labels.attachFile}
        </Button>,
      );
    }
  }

  if (canSendClientNotifications) {
    buttons.push(
      <Button
        key={`${actionKeyPrefix}-notify`}
        type="button"
        size="sm"
        variant="outline"
        className="border-border/75 bg-card"
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          onOpenClientNotification(record);
        }}
        disabled={notificationPendingAction}
        data-tour="client-row-notify-action"
      >
        <Send className="h-3.5 w-3.5" />
        {labels.notify}
      </Button>,
    );
  }

  if (canEditActiveResource) {
    buttons.push(
      <Button
        key={`${actionKeyPrefix}-edit`}
        type="button"
        size="sm"
        variant="outline"
        className="border-border/75 bg-card"
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          onEditRecord(record);
        }}
        disabled={pendingAction}
      >
        <Pencil className="h-3.5 w-3.5" />
        {labels.edit}
      </Button>,
    );
  }

  if (canReadAuditActiveResource) {
    buttons.push(
      <Button
        key={`${actionKeyPrefix}-history`}
        type="button"
        size="sm"
        variant="outline"
        className="border-border/75 bg-card"
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          onOpenAudit(record);
        }}
        disabled={pendingAction}
        data-tour="module-open-audit-drawer"
      >
        <History className="h-3.5 w-3.5" />
        {labels.history}
      </Button>,
    );
  }

  if (canDeleteActiveResource) {
    buttons.push(
      <Button
        key={`${actionKeyPrefix}-delete`}
        type="button"
        size="sm"
        variant={isDeleteConfirming ? 'destructive' : 'outline'}
        className={cn(
          isDeleteConfirming
            ? deleteConfirmClassName
            : 'border-destructive/25 bg-destructive/5 text-destructive hover:bg-destructive/10 hover:text-destructive',
        )}
        onClick={(event) => onDeleteRecord(event, record)}
        disabled={pendingAction}
      >
        <Trash2 className="h-3.5 w-3.5" />
        {isDeleteConfirming ? deleteConfirmLabel : labels.delete}
      </Button>,
    );
  }

  return buttons;
}
