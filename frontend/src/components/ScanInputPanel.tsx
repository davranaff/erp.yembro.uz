'use client';

import { useEffect, useRef, useState } from 'react';

/**
 * Универсальная панель ввода штрих-кода для drawer'ов лотов/партий.
 *
 * Auto-focused input + Enter / кнопка «Открыть» открывают /scan/<barcode>
 * в новом окне. Используется в:
 *   - /vet — drawer лота препарата
 *   - /feed — drawer партии мешков
 *
 * USB-сканер вводит код + нажимает Enter автоматически. Если оператор
 * отсканировал не в фокус — есть глобальный обработчик на уровне Shell
 * (см. useBarcodeScanner), который перехватит ввод и редиректнет.
 */
export default function ScanInputPanel() {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [value, setValue] = useState('');

  useEffect(() => {
    const t = setTimeout(() => inputRef.current?.focus(), 50);
    return () => clearTimeout(t);
  }, []);

  const open = () => {
    const v = value.trim();
    if (!v) return;
    window.open(`/scan/${encodeURIComponent(v)}`, '_blank');
    setValue('');
    inputRef.current?.focus();
  };

  return (
    <div style={{
      padding: 12, marginBottom: 14,
      background: 'var(--info-soft, var(--bg-soft))',
      borderRadius: 6, border: '1px solid var(--border)',
    }}>
      <div style={{
        fontSize: 11, fontWeight: 700, color: 'var(--fg-3)',
        textTransform: 'uppercase', letterSpacing: '.04em',
        marginBottom: 8,
      }}>
        Сканер / ручной ввод штрих-кода
      </div>
      <div style={{ display: 'flex', gap: 6 }}>
        <input
          ref={inputRef}
          className="input"
          placeholder="Отсканируйте или введите код…"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              open();
            }
          }}
          style={{ flex: 1, fontFamily: 'var(--font-mono, monospace)' }}
        />
        <button
          type="button"
          className="btn btn-primary btn-sm"
          onClick={open}
          disabled={!value.trim()}
        >
          Открыть
        </button>
      </div>
      <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 6 }}>
        Подключите USB-сканер — он введёт код и нажмёт Enter автоматически.
      </div>
    </div>
  );
}
