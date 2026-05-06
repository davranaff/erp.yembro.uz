import type { ChangeEvent } from 'react';

/**
 * onChange-хендлер для «ключевых» полей (sku, code, lot_number и т.п.) —
 * автоматически приводит ввод к UPPERCASE.
 *
 * Используется вместе с CSS-классом `input upper` (визуальный transform):
 *
 *   <input
 *     className="input mono upper"
 *     value={code}
 *     onChange={uppercaseChange(setCode)}
 *   />
 *
 * Backend дополнительно нормализует через UpperCaseField mixin (на случай
 * прямого API-вызова), но фронт делает это сам — чтобы юзер видел заглавные
 * буквы сразу при наборе.
 */
export function uppercaseChange(
  setter: (value: string) => void,
): (event: ChangeEvent<HTMLInputElement>) => void {
  return (event) => setter(event.target.value.toUpperCase());
}
