'use client';

import { forwardRef, useEffect, useState } from 'react';

/**
 * Универсальный инпут для денежных сумм с разделителями по тысячам
 * («1 000 000» вместо «1000000»). Внутри хранится «сырое» числовое
 * значение в виде строки (без пробелов), на экране — отформатированное.
 *
 * Контракт почти как у обычного <input>:
 *   value: string — «сырое» значение (без пробелов). Пустая строка = ничего.
 *   onChange(raw): string — приходит «сырое» (например '1500000').
 *
 * Поддерживает целые и дробные UZS-суммы. Запятая → точка, лишние нечисловые
 * символы выкидываются. Лидирующий минус разрешён (например для корректировок).
 */
function rawToDisplay(raw: string): string {
  if (!raw) return '';
  // Нормализуем: запятая → точка, выкидываем неразрешённые символы.
  const cleaned = raw.replace(',', '.').replace(/[^\d.-]/g, '');
  if (cleaned === '' || cleaned === '-' || cleaned === '.') return cleaned;
  const isNeg = cleaned.startsWith('-');
  const positive = isNeg ? cleaned.slice(1) : cleaned;
  const [intPart, decPart] = positive.split('.');
  const formattedInt = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  const formatted = decPart !== undefined
    ? `${formattedInt}.${decPart}`
    : formattedInt;
  return isNeg ? `-${formatted}` : formatted;
}

function displayToRaw(display: string): string {
  if (!display) return '';
  return display.replace(/\s+/g, '').replace(',', '.');
}

export interface AmountInputProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'value' | 'onChange' | 'type'> {
  /** «Сырое» значение без пробелов: '1000000' или '' */
  value: string;
  /** Принимает сырое значение (без пробелов). */
  onChange: (raw: string) => void;
}

const AmountInput = forwardRef<HTMLInputElement, AmountInputProps>(
  function AmountInput({ value, onChange, ...rest }, ref) {
    const [display, setDisplay] = useState<string>(() => rawToDisplay(value));

    // Синхронизация когда parent сбрасывает value снаружи.
    useEffect(() => {
      const raw = displayToRaw(display);
      if (raw !== value) {
        setDisplay(rawToDisplay(value));
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [value]);

    return (
      <input
        ref={ref}
        type="text"
        inputMode="decimal"
        autoComplete="off"
        value={display}
        onChange={(e) => {
          const raw = displayToRaw(e.target.value);
          setDisplay(rawToDisplay(raw));
          onChange(raw);
        }}
        {...rest}
      />
    );
  },
);

export default AmountInput;
