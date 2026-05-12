'use client';

import { useState } from 'react';

import Icon from '@/components/ui/Icon';
import Modal from '@/components/ui/Modal';
import {
  useNotifyDebt,
  type NotifyChannelResult,
} from '@/hooks/useCounterparties';

interface Props {
  counterpartyId: string;
  counterpartyName: string;
  hasPhone: boolean;
  onClose: () => void;
}

/**
 * Модалка «Уведомить о долге». Юзер выбирает каналы (SMS / TG),
 * жмёт «Отправить», видит по каждому каналу зелёную/красную плашку
 * с detail-сообщением от бэкенда.
 */
export default function NotifyDebtModal({
  counterpartyId, counterpartyName, hasPhone, onClose,
}: Props) {
  const [sms, setSms] = useState(hasPhone);
  const [tg, setTg] = useState(true);
  const [results, setResults] = useState<NotifyChannelResult[] | null>(null);

  const notify = useNotifyDebt();

  const channels: Array<'sms' | 'tg'> = [];
  if (sms) channels.push('sms');
  if (tg) channels.push('tg');
  const canSubmit = channels.length > 0 && !notify.isPending;

  const onSubmit = async () => {
    try {
      const res = await notify.mutateAsync({ id: counterpartyId, channels });
      setResults(res.results);
    } catch {
      /* mutation сама хранит ошибку */
    }
  };

  return (
    <Modal
      title="Уведомить о долге"
      onClose={onClose}
      footer={
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, width: '100%' }}>
          <button className="btn btn-ghost" onClick={onClose}>
            {results ? 'Закрыть' : 'Отмена'}
          </button>
          {!results && (
            <button
              className="btn btn-primary"
              disabled={!canSubmit}
              onClick={onSubmit}
            >
              {notify.isPending ? 'Отправляю…' : 'Отправить'}
            </button>
          )}
        </div>
      }
    >
      <div className="hint" style={{ marginBottom: 12 }}>
        Контрагент: <b>{counterpartyName}</b>
      </div>

      {!results && (
        <>
          <div style={{ marginBottom: 12 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <input
                type="checkbox"
                checked={sms}
                disabled={!hasPhone}
                onChange={(e) => setSms(e.target.checked)}
              />
              <span>SMS{!hasPhone && ' (телефон не указан)'}</span>
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input
                type="checkbox"
                checked={tg}
                onChange={(e) => setTg(e.target.checked)}
              />
              <span>Telegram (если клиент привязан к боту)</span>
            </label>
          </div>
          <div className="hint">
            Текст SMS — на узбекской латинице, короткий, чтобы укладывался
            в 1–2 SMS. В Telegram уходит детальное сообщение с эмодзи.
            Текущий долг берётся из aging-отчёта.
          </div>
        </>
      )}

      {results && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {results.map((r) => (
            <div
              key={r.channel}
              style={{
                padding: '8px 10px', borderRadius: 6,
                background: r.ok ? '#ecfdf5' : '#fef2f2',
                border: '1px solid ' + (r.ok ? '#10b981' : 'var(--danger)'),
                color: r.ok ? '#065f46' : 'var(--danger)',
                fontSize: 13,
                display: 'flex', alignItems: 'flex-start', gap: 8,
              }}
            >
              <Icon name={r.ok ? 'check' : 'close'} size={14} />
              <div>
                <div style={{ fontWeight: 600 }}>
                  {r.channel === 'sms' ? 'SMS' : 'Telegram'}
                  {' — '}
                  {r.ok ? 'отправлено' : 'не отправлено'}
                </div>
                <div>{r.detail}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </Modal>
  );
}
