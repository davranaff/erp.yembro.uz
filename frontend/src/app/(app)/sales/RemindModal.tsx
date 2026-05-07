'use client';

import { useEffect, useState } from 'react';

import Modal from '@/components/ui/Modal';
import {
  useSendDebtReminder,
  usePreviewDebtReminder,
} from '@/hooks/useTgBot';
import type { SaleOrder } from '@/types/auth';

interface Props {
  order: SaleOrder;
  onClose: () => void;
}

/**
 * Превью + правка текста напоминания перед отправкой в Telegram.
 *
 * Раньше клик «Напомнить в TG» сразу шёл send → клиент получал стандартный
 * шаблон без возможности что-то добавить или сократить. Сейчас:
 *   1. На открытии модалки → GET /api/tg/preview-debt-reminder/ возвращает
 *      рендеренный текст + информацию подключён ли клиент к TG
 *   2. Оператор видит превью в textarea, может править
 *   3. На «Отправить» → POST send-debt-reminder с body.text (или без, если
 *      не правил — backend сам отрендерит дефолт)
 */
export default function RemindModal({ order, onClose }: Props) {
  const { data, isLoading, error } = usePreviewDebtReminder(order.id);
  const send = useSendDebtReminder();
  const [text, setText] = useState('');
  const [edited, setEdited] = useState(false);

  // Подгружаем дефолт когда preview пришёл — но только если оператор не
  // успел ничего поменять. Иначе перезатёрли бы его правки.
  useEffect(() => {
    if (data?.text && !edited) {
      setText(data.text);
    }
  }, [data?.text, edited]);

  const handleSend = () => {
    if (!data?.has_tg_link) {
      alert('У клиента не подключён Telegram. Привяжите через карточку контрагента.');
      return;
    }
    const trimmed = text.trim();
    if (!trimmed) {
      alert('Текст пустой.');
      return;
    }
    // Если оператор не правил — отправляем без override (бэкенд возьмёт дефолт)
    const body = edited
      ? { sale_order_id: order.id, text: trimmed }
      : { sale_order_id: order.id };
    send.mutate(body, {
      onSuccess: () => {
        alert('Напоминание отправлено в Telegram');
        onClose();
      },
      onError: (e) => alert('Ошибка: ' + e.message),
    });
  };

  return (
    <Modal
      title={`Напоминание · ${order.doc_number}`}
      onClose={onClose}
      footer={
        <>
          <button
            className="btn btn-ghost"
            onClick={() => {
              if (data?.text) setText(data.text);
              setEdited(false);
            }}
            disabled={!edited || isLoading}
          >
            Сбросить к шаблону
          </button>
          <div style={{ flex: 1 }} />
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            onClick={handleSend}
            disabled={send.isPending || isLoading || !data?.has_tg_link}
          >
            {send.isPending ? 'Отправка…' : 'Отправить в Telegram'}
          </button>
        </>
      }
    >
      <div style={{
        padding: 10, marginBottom: 12,
        background: 'var(--bg-soft)', borderRadius: 6,
        fontSize: 13,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span>Клиент:</span>
          <b>{data?.customer_name ?? order.customer_name ?? '—'}</b>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span>Telegram:</span>
          {isLoading ? (
            <span style={{ color: 'var(--fg-3)' }}>проверяю…</span>
          ) : data?.has_tg_link ? (
            <span style={{ color: 'var(--success)' }}>
              ✓ подключён{data.tg_username ? ` · @${data.tg_username}` : ''}
            </span>
          ) : (
            <span style={{ color: 'var(--danger)' }}>
              ✗ не подключён — отправить нельзя
            </span>
          )}
        </div>
      </div>

      {error && (
        <div style={{
          padding: 8, marginBottom: 12, background: '#fef2f2',
          color: 'var(--danger)', borderRadius: 6, fontSize: 12,
        }}>
          Не удалось загрузить превью: {error.message}
        </div>
      )}

      <div className="field">
        <label>
          Текст сообщения{' '}
          {edited && (
            <span style={{ fontSize: 11, color: 'var(--brand-orange)' }}>
              · отредактировано
            </span>
          )}
        </label>
        <textarea
          className="input"
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setEdited(true);
          }}
          rows={14}
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
            lineHeight: 1.5,
            whiteSpace: 'pre-wrap',
          }}
          disabled={isLoading || !data?.has_tg_link}
        />
        <span className="hint">
          HTML-разметка Telegram (&lt;b&gt;, &lt;i&gt;, &lt;code&gt;) поддерживается.
          Эмодзи можно вставлять как обычный текст.
        </span>
      </div>
    </Modal>
  );
}
