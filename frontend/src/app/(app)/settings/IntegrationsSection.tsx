'use client';

import Panel from '@/components/ui/Panel';
import { useLatestRates, useSyncCbuRates } from '@/hooks/useCurrencyRates';
import { useHasLevel } from '@/hooks/usePermissions';

export default function IntegrationsSection() {
  const { data, isLoading, error, refetch } = useLatestRates();
  const sync = useSyncCbuRates();

  const hasLevel = useHasLevel();
  // Запуск синхронизации с CBU = админ-операция (admin level на admin модуль).
  const canSync = hasLevel('admin', 'admin');

  const lastFetched = data && data.length > 0
    ? new Date(data[0].fetched_at).toLocaleString('ru')
    : null;

  return (
    <Panel title="Интеграции">
      {/* ─── CBU ───────────────────────────────────────── */}
      <div
        style={{
          border: '1px solid var(--border)',
          borderRadius: 6,
          padding: 14,
          marginBottom: 12,
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            gap: 16,
            marginBottom: 12,
          }}
        >
          <div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>ЦБ Узбекистана (cbu.uz)</div>
            <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>
              Ежедневный импорт курсов валют. Обновляется автоматически в 10:00 (Asia/Tashkent).
            </div>
            {lastFetched && (
              <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 6 }}>
                Последнее обновление: <span className="mono">{lastFetched}</span>
              </div>
            )}
          </div>
          <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
            <button
              className="btn btn-ghost"
              onClick={() => refetch()}
              disabled={isLoading}
            >
              Обновить
            </button>
            {canSync && (
              <button
                className="btn btn-primary"
                onClick={() => sync.mutate()}
                disabled={sync.isPending}
              >
                {sync.isPending ? 'Синхронизация…' : 'Синхронизировать'}
              </button>
            )}
          </div>
        </div>

        {sync.isSuccess && sync.data && (
          <div
            style={{
              fontSize: 12,
              color: 'var(--success)',
              background: 'var(--success-soft)',
              padding: 8,
              borderRadius: 4,
              marginBottom: 10,
            }}
          >
            Готово · получено {sync.data.fetched}, создано {sync.data.created}, обновлено{' '}
            {sync.data.updated}, пропущено {sync.data.skipped}.
          </div>
        )}
        {sync.error && (
          <div
            style={{
              fontSize: 12,
              color: 'var(--danger)',
              background: 'var(--danger-soft)',
              padding: 8,
              borderRadius: 4,
              marginBottom: 10,
            }}
          >
            Ошибка синхронизации: {sync.error.message}
          </div>
        )}

        {isLoading && (
          <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>Загрузка курсов…</div>
        )}
        {error && (
          <div style={{ fontSize: 12, color: 'var(--danger)' }}>
            Не удалось загрузить курсы: {error.message}
          </div>
        )}
        {!isLoading && !error && data && data.length > 0 && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
              gap: 8,
              marginTop: 8,
            }}
          >
            {data.slice(0, 8).map((r) => (
              <div
                key={r.id}
                style={{
                  border: '1px solid var(--border)',
                  borderRadius: 4,
                  padding: 10,
                  background: 'var(--bg-card)',
                }}
              >
                <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
                  {r.currency_code ?? r.currency} · {r.date}
                </div>
                <div
                  className="mono"
                  style={{ fontSize: 15, fontWeight: 600, marginTop: 2 }}
                >
                  {r.rate}
                </div>
                <div style={{ fontSize: 10, color: 'var(--fg-3)', marginTop: 2 }}>
                  за {r.nominal} · {r.source}
                </div>
              </div>
            ))}
          </div>
        )}
        {!isLoading && !error && data && data.length === 0 && (
          <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>
            Пока нет загруженных курсов. Нажмите «Синхронизировать».
          </div>
        )}
      </div>

      {/* ─── Другие интеграции (заглушки) ──────────────── */}
      {[
        { title: '1С:Предприятие', desc: 'Выгрузка проводок в формате XML/CSV.' },
        { title: 'Банк-клиент', desc: 'Загрузка выписок, автосверка платежей.' },
        { title: 'ЭДО', desc: 'Обмен первичными документами с контрагентами.' },
      ].map((i) => (
        <div
          key={i.title}
          style={{
            border: '1px solid var(--border)',
            borderRadius: 6,
            padding: 14,
            marginBottom: 8,
            opacity: 0.7,
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <div>
              <div style={{ fontSize: 14, fontWeight: 600 }}>{i.title}</div>
              <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>{i.desc}</div>
            </div>
            <span
              style={{
                fontSize: 10,
                color: 'var(--fg-3)',
                border: '1px solid var(--border)',
                padding: '1px 6px',
                borderRadius: 4,
              }}
            >
              скоро
            </span>
          </div>
        </div>
      ))}
    </Panel>
  );
}
