'use client';

import { useState } from 'react';

import TgConnectModal from '@/components/ui/TgConnectModal';
import { useDisconnectTgLink, useTgMyLink } from '@/hooks/useTgBot';

const TG_BLUE = '#229ED9';

function TelegramIcon({ size = 40 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="24" cy="24" r="24" fill={TG_BLUE} />
      <path
        d="M10.5 23.5L34.7 13.8C35.8 13.4 36.8 14.4 36.4 15.5L31.2 36.2C30.8 37.5 29.1 37.7 28.4 36.6L22.5 27.8L17.8 32.1C17.1 32.7 16 32.3 16 31.3V26.5L10.5 23.5Z"
        fill="white"
        opacity="0.4"
      />
      <path
        d="M16 26.5L22.5 27.8L28.4 36.6C29.1 37.7 30.8 37.5 31.2 36.2L36.4 15.5C36.8 14.4 35.8 13.4 34.7 13.8L10.5 23.5L16 26.5Z"
        fill="white"
      />
      <path
        d="M16 26.5L22.5 27.8L20 32L16 26.5Z"
        fill="#B0BEC5"
      />
    </svg>
  );
}

const COMMANDS = [
  { cmd: '/report', desc: 'Финансовый отчёт за месяц' },
  { cmd: '/stock', desc: 'Остатки кассы и банка' },
  { cmd: '/cashflow', desc: 'Кэш-флоу за 30 дней' },
  { cmd: '/production', desc: 'Поголовье и партии' },
];

export default function TelegramSection() {
  const { data: link, isLoading } = useTgMyLink();
  const disconnect = useDisconnectTgLink();
  const [showModal, setShowModal] = useState(false);

  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: 10,
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        background: `linear-gradient(135deg, ${TG_BLUE}18 0%, ${TG_BLUE}08 100%)`,
        borderBottom: '1px solid var(--border)',
        padding: '24px 24px 20px',
        display: 'flex',
        alignItems: 'center',
        gap: 16,
      }}>
        <TelegramIcon size={48} />
        <div>
          <h2 style={{ margin: 0, fontSize: 18 }}>Telegram-уведомления</h2>
          <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--fg-3)' }}>
            Закупы, оплаты и аналитика — прямо в мессенджере
          </p>
        </div>
      </div>

      <div style={{ padding: 24 }}>
        {/* Connection status */}
        {isLoading ? (
          <div style={{ color: 'var(--fg-3)', fontSize: 13 }}>Загрузка…</div>
        ) : link ? (
          <div style={{
            background: '#10b98115',
            border: '1px solid #10b98130',
            borderRadius: 8,
            padding: '14px 18px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
            marginBottom: 24,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{
                width: 36, height: 36, borderRadius: '50%',
                background: '#10b98120',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 18,
              }}>
                ✅
              </div>
              <div>
                <div style={{ fontWeight: 600, fontSize: 14 }}>Telegram подключён</div>
                <div style={{ fontSize: 12, color: 'var(--fg-3)', marginTop: 2 }}>
                  {link.tg_username ? `@${link.tg_username} · ` : ''}
                  Подключён {new Date(link.created_at).toLocaleDateString('ru-RU')}
                </div>
              </div>
            </div>
            <button
              className="btn btn-ghost btn-sm"
              style={{ color: 'var(--danger)', whiteSpace: 'nowrap' }}
              onClick={() => disconnect.mutate()}
              disabled={disconnect.isPending}
            >
              {disconnect.isPending ? 'Отключение…' : 'Отключить'}
            </button>
          </div>
        ) : (
          <div style={{
            borderRadius: 8,
            border: '1px dashed var(--border)',
            padding: '20px 18px',
            marginBottom: 24,
            display: 'flex',
            alignItems: 'center',
            gap: 16,
          }}>
            <div style={{
              width: 48, height: 48, borderRadius: '50%',
              background: 'var(--bg-soft)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0,
            }}>
              <TelegramIcon size={28} />
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>
                Привяжите свой Telegram-аккаунт
              </div>
              <div style={{ fontSize: 13, color: 'var(--fg-3)', lineHeight: 1.5 }}>
                Получайте мгновенные уведомления и запрашивайте аналитику командами прямо в боте.
              </div>
            </div>
            <button
              className="btn btn-primary"
              style={{ whiteSpace: 'nowrap', flexShrink: 0 }}
              onClick={() => setShowModal(true)}
            >
              Подключить
            </button>
          </div>
        )}

        {/* Commands grid */}
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 10 }}>
            Доступные команды
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            {COMMANDS.map(({ cmd, desc }) => (
              <div key={cmd} style={{
                background: 'var(--bg-soft)',
                borderRadius: 6,
                padding: '10px 12px',
                display: 'flex',
                flexDirection: 'column',
                gap: 3,
              }}>
                <code style={{ fontSize: 12, color: TG_BLUE, fontWeight: 600 }}>{cmd}</code>
                <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>{desc}</span>
              </div>
            ))}
          </div>
        </div>

        {/* How-to steps */}
        <div style={{
          background: 'var(--bg-soft)',
          borderRadius: 8,
          padding: '14px 16px',
          fontSize: 13,
        }}>
          <div style={{ fontWeight: 600, marginBottom: 10 }}>Как привязать аккаунт</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {[
              'Нажмите «Подключить»',
              'Откройте бот по сгенерированной ссылке',
              'Нажмите Start — аккаунт привяжется автоматически',
            ].map((step, i) => (
              <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                <div style={{
                  width: 20, height: 20, borderRadius: '50%',
                  background: TG_BLUE + '20',
                  color: TG_BLUE,
                  fontSize: 11, fontWeight: 700,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0, marginTop: 1,
                }}>
                  {i + 1}
                </div>
                <span style={{ color: 'var(--fg-2)', lineHeight: 1.5 }}>{step}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {showModal && (
        <TgConnectModal mode="user" onClose={() => setShowModal(false)} />
      )}
    </div>
  );
}
