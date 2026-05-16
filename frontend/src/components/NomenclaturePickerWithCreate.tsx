'use client';

import { useState } from 'react';

import NomenclatureModal from '@/app/(app)/nomenclature/NomenclatureModal';
import SmartSelect from '@/components/ui/SmartSelect';
import type { NomenclatureItem } from '@/types/auth';

interface Props {
  value: string;
  onChange: (v: string) => void;
  items: NomenclatureItem[];
  disabled?: boolean;
  placeholder?: string;
  emptyText?: string;
  searchPlaceholder?: string;
  /** Hide "+ create" button (e.g. when user has no rw on /nomenclature). */
  hideCreate?: boolean;
}

/**
 * Picker для NomenclatureItem с inline-кнопкой «+» — открывает
 * NomenclatureModal поверх и при сохранении автоматически подставляет
 * новый item в форму. Чтобы юзер не ходил в раздел /nomenclature за
 * каждым новым SKU.
 *
 * Esc внутри вложенной модалки закрывает обе (известное ограничение
 * useModalLifecycle — listeners-стек не реализован). Кнопка-крестик и
 * клик по фону работают как ожидается.
 */
export default function NomenclaturePickerWithCreate({
  value,
  onChange,
  items,
  disabled,
  placeholder,
  emptyText = 'Не найдено',
  searchPlaceholder = 'Поиск по SKU или названию…',
  hideCreate = false,
}: Props) {
  const [createOpen, setCreateOpen] = useState(false);

  return (
    <>
      <div style={{ display: 'flex', gap: 4, alignItems: 'stretch' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <SmartSelect
            value={value}
            onChange={onChange}
            options={items.map((i) => ({
              value: i.id,
              label: i.name,
              sublabel: i.sku,
            }))}
            disabled={disabled}
            placeholder={placeholder}
            searchPlaceholder={searchPlaceholder}
            emptyText={emptyText}
          />
        </div>
        {!hideCreate && (
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => setCreateOpen(true)}
            title="Создать новый товар"
            style={{ whiteSpace: 'nowrap' }}
          >
            + товар
          </button>
        )}
      </div>

      {createOpen && (
        <NomenclatureModal
          onClose={() => setCreateOpen(false)}
          onSaved={(item) => {
            onChange(item.id);
            setCreateOpen(false);
          }}
        />
      )}
    </>
  );
}
