'use client';

import { useEffect, useState } from 'react';

import Icon from '@/components/ui/Icon';
import { attachAutoFlush, flush, listQueued } from '@/lib/offlineQueue';


/**
 * Плашка-индикатор offline-состояния и очереди мутаций.
 *
 * Показывается в правом нижнем углу когда:
 *   — нет сети (`navigator.onLine === false`), ИЛИ
 *   — в очереди есть неотправленные мутации.
 *
 * Клик по плашке — ручной retry. Когда сеть появляется — автоматически
 * прогоняет очередь и плашка прячется.
 */
export default function OfflineIndicator() {
  const [online, setOnline] = useState(true);
  const [queued, setQueued] = useState(0);
  const [busy, setBusy] = useState(false);

  // Refresh queued count
  const refresh = async () => {
    try {
      const items = await listQueued();
      setQueued(items.length);
    } catch {
      setQueued(0);
    }
  };

  useEffect(() => {
    if (typeof navigator !== 'undefined') setOnline(navigator.onLine);
    refresh();

    const onOnline = () => setOnline(true);
    const onOffline = () => setOnline(false);
    window.addEventListener('online', onOnline);
    window.addEventListener('offline', onOffline);

    // Авто-прогон очереди когда сеть появилась
    const detach = attachAutoFlush(() => refresh());

    // Периодический refresh + retry (раз в 30с)
    const tick = setInterval(refresh, 30_000);

    return () => {
      window.removeEventListener('online', onOnline);
      window.removeEventListener('offline', onOffline);
      detach();
      clearInterval(tick);
    };
  }, []);

  const handleRetry = async () => {
    setBusy(true);
    try {
      await flush();
      await refresh();
    } finally {
      setBusy(false);
    }
  };

  // Не показываем если онлайн и очередь пуста
  if (online && queued === 0) return null;

  const tone = !online ? 'offline' : queued > 0 ? 'queued' : 'ok';
  const bg = tone === 'offline'
    ? 'var(--danger)'
    : tone === 'queued' ? 'var(--brand-orange)' : 'var(--success)';

  return (
    <button
      className="offline-indicator"
      onClick={handleRetry}
      disabled={busy || !online}
      title={!online ? 'Нет сети' : `${queued} записей ждут отправки`}
      style={{
        position: 'fixed',
        bottom: 16,
        right: 16,
        zIndex: 9999,
        padding: '10px 14px',
        borderRadius: 24,
        background: bg,
        color: '#fff',
        border: 'none',
        cursor: online ? 'pointer' : 'default',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        fontSize: 13,
        fontWeight: 600,
        boxShadow: '0 4px 12px rgba(0,0,0,.15)',
      }}
    >
      <Icon name={!online ? 'close' : 'inbox'} size={14} />
      <span>
        {!online && 'Нет сети'}
        {online && queued > 0 && (busy ? 'Отправка…' : `${queued} в очереди`)}
      </span>
    </button>
  );
}
