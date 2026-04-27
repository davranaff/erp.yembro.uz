'use client';

import { useState } from 'react';

import Modal from '@/components/ui/Modal';
import type { TgLinkToken } from '@/hooks/useTgBot';
import {
  useCreateTgLinkToken,
  useDisconnectCounterpartyTg,
  useDisconnectTgLink,
  useTgCounterpartyLink,
  useTgMyLink,
} from '@/hooks/useTgBot';

const TG_BLUE = '#229ED9';

function TgIcon({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none">
      <circle cx="24" cy="24" r="24" fill={TG_BLUE} />
      <path d="M16 26.5L22.5 27.8L28.4 36.6C29.1 37.7 30.8 37.5 31.2 36.2L36.4 15.5C36.8 14.4 35.8 13.4 34.7 13.8L10.5 23.5L16 26.5Z" fill="white" />
      <path d="M16 26.5L22.5 27.8L20 32L16 26.5Z" fill="#B0BEC5" />
    </svg>
  );
}

interface UserProps { mode: 'user'; onClose: () => void; }
interface CounterpartyProps { mode: 'counterparty'; counterpartyId: string; counterpartyName?: string; onClose: () => void; }
type Props = UserProps | CounterpartyProps;

export default function TgConnectModal(props: Props) {
  const { mode, onClose } = props;
  const counterpartyId = mode === 'counterparty' ? props.counterpartyId : undefined;

  const { data: myLink, isLoading: loadingMe } = useTgMyLink();
  const { data: cpLink, isLoading: loadingCp } = useTgCounterpartyLink(counterpartyId);

  const link = mode === 'user' ? myLink : cpLink;
  const isLoading = mode === 'user' ? loadingMe : loadingCp;

  const createToken = useCreateTgLinkToken(counterpartyId);
  const disconnectUser = useDisconnectTgLink();
  const disconnectCp = useDisconnectCounterpartyTg(counterpartyId ?? '');

  const [token, setToken] = useState<TgLinkToken | null>(null);
  const [copied, setCopied] = useState(false);

  const handleGenerate = async () => setToken(await createToken.mutateAsync());

  const handleDisconnect = async () => {
    if (mode === 'user') await disconnectUser.mutateAsync();
    else await disconnectCp.mutateAsync();
    onClose();
  };

  const handleCopy = () => {
    if (!token) return;
    navigator.clipboard.writeText(token.token);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isCounterparty = mode === 'counterparty';
  const cpName = isCounterparty ? (props as CounterpartyProps).counterpartyName : undefined;
  const title = isCounterparty ? `Telegram · ${cpName ?? 'Контрагент'}` : 'Подключить Telegram';

  return (
    <Modal title={title} onClose={onClose} footer={
      <button className="btn btn-ghost" onClick={onClose}>Закрыть</button>
    }>
      {isLoading ? (
        <div style={{ padding: '32px 0', textAlign: 'center', color: 'var(--fg-3)' }}>Загрузка…</div>
      ) : link ? (
        /* ── Already connected ── */
        <div>
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            padding: '20px 0 24px', gap: 12, textAlign: 'center',
          }}>
            <div style={{ position: 'relative', display: 'inline-flex' }}>
              <TgIcon size={56} />
              <span style={{
                position: 'absolute', bottom: -2, right: -2,
                fontSize: 18, lineHeight: 1,
              }}>✅</span>
            </div>
            <div>
              <div style={{ fontWeight: 600, fontSize: 15 }}>Telegram подключён</div>
              {link.tg_username && (
                <div style={{ fontSize: 13, color: TG_BLUE, marginTop: 2 }}>@{link.tg_username}</div>
              )}
              <div style={{ fontSize: 12, color: 'var(--fg-3)', marginTop: 4 }}>
                Подключён {new Date(link.created_at).toLocaleDateString('ru-RU')}
              </div>
            </div>
          </div>
          <div style={{ borderTop: '1px solid var(--border)', paddingTop: 16 }}>
            <button
              className="btn btn-ghost"
              style={{ color: 'var(--danger)', width: '100%' }}
              onClick={handleDisconnect}
              disabled={disconnectUser.isPending || disconnectCp.isPending}
            >
              {disconnectUser.isPending || disconnectCp.isPending ? 'Отключение…' : 'Отключить Telegram'}
            </button>
          </div>
        </div>
      ) : token ? (
        /* ── Token generated ── */
        <div>
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            padding: '16px 0 20px', gap: 10, textAlign: 'center',
          }}>
            <TgIcon size={48} />
            <div style={{ fontSize: 14, fontWeight: 600 }}>
              {isCounterparty ? 'Ссылка для клиента готова' : 'Ссылка для привязки готова'}
            </div>
            <div style={{ fontSize: 13, color: 'var(--fg-3)', maxWidth: 320, lineHeight: 1.5 }}>
              {isCounterparty
                ? 'Отправьте эту ссылку клиенту. Он откроет бота и нажмёт Start.'
                : 'Откройте бота и нажмите Start — аккаунт привяжется автоматически.'}
            </div>
          </div>

          <a
            href={token.bot_url}
            target="_blank"
            rel="noreferrer"
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
              background: TG_BLUE, color: '#fff', borderRadius: 8,
              padding: '11px 16px', fontWeight: 600, fontSize: 14,
              textDecoration: 'none', marginBottom: 12,
            }}
          >
            <TgIcon size={20} />
            Открыть Telegram бот
          </a>

          <div style={{
            background: 'var(--bg-soft)', borderRadius: 6, padding: '10px 12px',
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <code style={{ flex: 1, fontSize: 11, wordBreak: 'break-all', color: 'var(--fg-2)' }}>
              {token.token}
            </code>
            <button className="btn btn-ghost btn-sm" onClick={handleCopy} style={{ flexShrink: 0 }}>
              {copied ? '✓' : 'Копировать'}
            </button>
          </div>
          <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 6, textAlign: 'center' }}>
            Токен действителен 30 минут
          </div>
        </div>
      ) : (
        /* ── Initial state ── */
        <div>
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            padding: '20px 0 24px', gap: 12, textAlign: 'center',
          }}>
            <TgIcon size={56} />
            <div>
              <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 6 }}>
                {isCounterparty ? `Привязать Telegram клиента` : 'Привязать ваш Telegram'}
              </div>
              <div style={{ fontSize: 13, color: 'var(--fg-3)', maxWidth: 320, lineHeight: 1.6 }}>
                {isCounterparty
                  ? `Клиент ${cpName ? `«${cpName}»` : ''} будет автоматически получать напоминания о задолженностях на узбекском языке.`
                  : 'Получайте уведомления о закупах, оплатах и запрашивайте аналитику командами /report, /stock и другими.'}
              </div>
            </div>
          </div>

          <button
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
              background: TG_BLUE, color: '#fff', border: 'none', borderRadius: 8,
              padding: '12px 16px', fontWeight: 600, fontSize: 14,
              width: '100%', cursor: createToken.isPending ? 'not-allowed' : 'pointer',
              opacity: createToken.isPending ? 0.7 : 1,
            }}
            onClick={handleGenerate}
            disabled={createToken.isPending}
          >
            <TgIcon size={20} />
            {createToken.isPending ? 'Генерация ссылки…' : 'Сгенерировать ссылку'}
          </button>
        </div>
      )}
    </Modal>
  );
}
