'use client';

import { useMemo, useState } from 'react';

import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Panel from '@/components/ui/Panel';
import Seg from '@/components/ui/Seg';
import {
  useNotifications,
  type NotificationItem,
} from '@/hooks/useNotifications';

type ChannelTab = '' | 'sms' | 'tg';

const STATUS_TONE: Record<string, 'neutral' | 'success' | 'warn' | 'danger' | 'info'> = {
  queued: 'neutral',
  sent: 'info',
  delivered: 'success',
  failed: 'danger',
};

const SOURCE_LABEL: Record<string, string> = {
  otp: 'OTP',
  notify: 'Уведомление',
  manual: 'Ручная отправка',
  debt_reminder: 'Напоминание о долге',
  tg_invite: 'Приглашение в TG',
  system: 'Системное',
  other: 'Прочее',
};

function fmtDate(s: string): string {
  try {
    const d = new Date(s);
    return d.toLocaleString('ru-RU', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return s;
  }
}

export default function NotificationsPage() {
  const [channel, setChannel] = useState<ChannelTab>('');
  const [status, setStatus] = useState<string>('');
  const [source, setSource] = useState<string>('');
  const [phone, setPhone] = useState<string>('');
  const [page, setPage] = useState(0);
  const pageSize = 50;

  const filter = useMemo(() => ({
    channel: channel || undefined,
    status: status || undefined,
    source: source || undefined,
    phone: phone || undefined,
    limit: pageSize,
    offset: page * pageSize,
  }), [channel, status, source, phone, page]);

  const { data, isLoading, error } = useNotifications(filter);
  const items = data?.results ?? [];
  const total = data?.count ?? 0;

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Оповещения</h1>
          <div className="sub">
            История исходящих сообщений: SMS (Eskiz) и Telegram.
            {total > 0 && ` Всего: ${total}.`}
          </div>
        </div>
      </div>

      <div style={{ marginBottom: 12 }}>
        <Seg
          options={[
            { value: '', label: 'Все' },
            { value: 'sms', label: 'SMS' },
            { value: 'tg', label: 'Telegram' },
          ]}
          value={channel}
          onChange={(v) => { setChannel(v as ChannelTab); setPage(0); }}
        />
      </div>

      <div className="filter-bar">
        <div className="filter-cell">
          <label>Статус</label>
          <select
            className="input"
            value={status}
            onChange={(e) => { setStatus(e.target.value); setPage(0); }}
          >
            <option value="">Все</option>
            <option value="queued">В очереди</option>
            <option value="sent">Отправлено</option>
            <option value="delivered">Доставлено</option>
            <option value="failed">Ошибка</option>
          </select>
        </div>
        <div className="filter-cell">
          <label>Тип</label>
          <select
            className="input"
            value={source}
            onChange={(e) => { setSource(e.target.value); setPage(0); }}
          >
            <option value="">Все</option>
            <option value="otp">OTP</option>
            <option value="notify">Уведомление</option>
            <option value="manual">Ручная</option>
            <option value="debt_reminder">Напоминание о долге</option>
            <option value="tg_invite">Приглашение в TG</option>
            <option value="system">Системное</option>
          </select>
        </div>
        {channel !== 'tg' && (
          <div className="filter-cell" style={{ minWidth: 200 }}>
            <label>Телефон</label>
            <input
              className="input"
              type="text"
              value={phone}
              onChange={(e) => { setPhone(e.target.value); setPage(0); }}
              placeholder="998901234567"
            />
          </div>
        )}
      </div>

      {error && (
        <div style={{
          marginTop: 12, padding: 10,
          background: '#fef2f2', color: 'var(--danger)',
          borderRadius: 6, fontSize: 13,
        }}>
          Не удалось загрузить: {error.message}
        </div>
      )}

      <Panel flush>
        <DataTable<NotificationItem>
          isLoading={isLoading}
          rows={items}
          rowKey={(n) => `${n.channel}-${n.id}`}
          emptyMessage="Оповещений нет."
          columns={[
            { key: 'date', label: 'Дата', mono: true,
              cellStyle: { fontSize: 12 },
              render: (n) => fmtDate(n.created_at) },
            { key: 'channel', label: 'Канал',
              render: (n) => (
                <Badge tone={n.channel === 'sms' ? 'info' : 'success'}>
                  {n.channel === 'sms' ? '💬 SMS' : '📩 Telegram'}
                </Badge>
              ) },
            { key: 'to', label: 'Получатель', mono: true,
              cellStyle: { fontSize: 12 },
              render: (n) => (
                n.channel === 'sms'
                  ? n.phone || '—'
                  : (n.counterparty_name
                      ? `${n.counterparty_name} · chat:${n.chat_id}`
                      : `chat:${n.chat_id}`)
              ) },
            { key: 'source', label: 'Тип', muted: true,
              cellStyle: { fontSize: 12 },
              render: (n) => SOURCE_LABEL[n.source] ?? n.source },
            { key: 'text', label: 'Сообщение',
              cellStyle: { fontSize: 12, maxWidth: 380, whiteSpace: 'normal' },
              render: (n) => (
                <span style={{
                  display: 'inline-block',
                  maxWidth: 380, overflow: 'hidden',
                  textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }} title={n.text}>
                  {n.text}
                </span>
              ) },
            { key: 'status', label: 'Статус',
              render: (n) => (
                <Badge tone={STATUS_TONE[n.status] ?? 'neutral'}>
                  {n.status}
                </Badge>
              ) },
            { key: 'error', label: 'Ошибка',
              cellStyle: { fontSize: 11, color: 'var(--danger)', maxWidth: 240 },
              render: (n) => n.error_msg
                ? <span title={n.error_msg}>
                    {n.error_msg.length > 60 ? n.error_msg.slice(0, 60) + '…' : n.error_msg}
                  </span>
                : '—' },
          ]}
        />

        {total > pageSize && (
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: 10, fontSize: 12, color: 'var(--fg-3)',
          }}>
            <div>
              Страница {page + 1} из {Math.ceil(total / pageSize)} ·
              записей {page * pageSize + 1}–{Math.min((page + 1) * pageSize, total)} из {total}
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              <button
                className="btn btn-ghost btn-sm"
                disabled={page === 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
              >
                ← Назад
              </button>
              <button
                className="btn btn-ghost btn-sm"
                disabled={(page + 1) * pageSize >= total}
                onClick={() => setPage((p) => p + 1)}
              >
                Вперёд →
              </button>
            </div>
          </div>
        )}
      </Panel>
    </>
  );
}
