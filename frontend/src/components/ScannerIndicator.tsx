'use client';

/**
 * Маленькая индикация в углу — что глобальный сканер активен.
 *
 * `active=false` — приглушённый кружок (сканер слушает, но сейчас тихо).
 * `active=true`  — пульс зелёным (только что прошла буква от сканера).
 *
 * Подключается в Shell над контентом.
 */
export default function ScannerIndicator({ active }: { active: boolean }) {
  return (
    <div
      title={
        active
          ? 'Сканер: ввод…'
          : 'Сканер активен — отсканируйте штрих-код в любой момент'
      }
      style={{
        position: 'fixed',
        bottom: 12,
        right: 12,
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        padding: '6px 10px',
        background: active ? 'var(--success-soft, #DCFCE7)' : 'var(--bg-soft)',
        border: `1px solid ${active ? 'var(--success)' : 'var(--border)'}`,
        borderRadius: 999,
        fontSize: 11,
        color: active ? 'var(--success)' : 'var(--fg-3)',
        transition: 'background .2s, border-color .2s, color .2s',
        pointerEvents: 'none',
        userSelect: 'none',
      }}
    >
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: active ? 'var(--success)' : 'var(--fg-3)',
          opacity: active ? 1 : 0.5,
          boxShadow: active ? '0 0 8px var(--success)' : 'none',
          transition: 'background .2s, opacity .2s, box-shadow .2s',
        }}
      />
      <span style={{ fontWeight: 500, letterSpacing: '.02em' }}>
        Сканер
      </span>
    </div>
  );
}
