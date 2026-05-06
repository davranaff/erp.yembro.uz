'use client';

import { useEffect, useRef, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';

/**
 * Глобальный обработчик HID-сканера штрих-кодов.
 *
 * USB/Bluetooth сканер в HID-режиме притворяется клавиатурой: вводит
 * символы очень быстро (< 30мс между клавишами) и в конце шлёт Enter.
 * Это отличает его от ручного ввода.
 *
 * Поведение:
 *   - Слушает keydown на document на любой странице.
 *   - Если фокус в input/textarea/contenteditable — НЕ перехватывает,
 *     даёт спокойно печатать.
 *   - Если уже на /scan/* или /scan/login — игнорирует (там свой ввод).
 *   - Накапливает символы в буфер, сбрасывает если интервал > 50мс.
 *   - На Enter с буфером ≥ 6 симв и быстрой накачкой → router.push(/scan/<barcode>).
 *
 * `scannerActive` — короткий флаг (true пока идёт быстрая накачка),
 * для индикатора в UI.
 */

const SCAN_GAP_MS = 50;          // интервал «ещё печатает сканер»
const MIN_BARCODE_LEN = 6;
const ACTIVE_FLAG_TIMEOUT = 600; // как долго гореть индикатор после буквы

function isInputFocused(): boolean {
  const el = document.activeElement;
  if (!el) return false;
  const tag = el.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
  if ((el as HTMLElement).isContentEditable) return true;
  return false;
}

export function useBarcodeScanner(): { scannerActive: boolean } {
  const router = useRouter();
  const pathname = usePathname();
  const [scannerActive, setScannerActive] = useState(false);
  const activeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let buffer = '';
    let lastKeyTime = 0;

    const flashActive = () => {
      setScannerActive(true);
      if (activeTimerRef.current) clearTimeout(activeTimerRef.current);
      activeTimerRef.current = setTimeout(
        () => setScannerActive(false),
        ACTIVE_FLAG_TIMEOUT,
      );
    };

    const handleKey = (e: KeyboardEvent) => {
      // Не вмешиваемся, если оператор печатает в форму.
      if (isInputFocused()) return;
      // На /scan/* свой обработчик в самом инпуте — не дублируем.
      if (pathname && pathname.startsWith('/scan')) return;

      const now = Date.now();
      const gap = now - lastKeyTime;

      if (e.key === 'Enter') {
        const code = buffer.trim();
        buffer = '';
        // Принимаем только если пакет был накачан быстро (HID-сканер).
        // gap здесь — интервал от ПОСЛЕДНЕГО keydown до Enter; обычно < 30мс.
        if (code.length >= MIN_BARCODE_LEN && gap < SCAN_GAP_MS) {
          e.preventDefault();
          router.push(`/scan/${encodeURIComponent(code)}`);
        }
        return;
      }

      // Скидываем буфер, если зазор слишком большой (это не сканер,
      // оператор просто нажал какую-то клавишу).
      if (buffer.length > 0 && gap > SCAN_GAP_MS) {
        buffer = '';
      }

      // Принимаем только печатные одиночные символы.
      if (e.key.length === 1) {
        buffer += e.key;
        lastKeyTime = now;
        flashActive();
      }
    };

    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('keydown', handleKey);
      if (activeTimerRef.current) clearTimeout(activeTimerRef.current);
    };
  }, [router, pathname]);

  return { scannerActive };
}
