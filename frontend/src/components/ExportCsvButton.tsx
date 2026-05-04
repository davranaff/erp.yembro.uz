'use client';

import { useState } from 'react';

import Icon from '@/components/ui/Icon';
import { getAccessToken, readOrgCookie } from '@/lib/tokens';


interface Props {
  /** Путь API без host'а: `/api/accounting/reports/trial-balance/?date_from=...` */
  url: string;
  /** Имя сохраняемого файла (с расширением). */
  filename: string;
  /** Текст кнопки. */
  label?: string;
  disabled?: boolean;
}


const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';


/**
 * Кнопка скачивания CSV. Делает fetch с Authorization+X-Organization-Code,
 * получает blob и инициирует загрузку через `<a download>`.
 */
export default function ExportCsvButton({
  url, filename, label = 'CSV', disabled = false,
}: Props) {
  const [busy, setBusy] = useState(false);

  const handle = async () => {
    setBusy(true);
    try {
      // Добавляем format=csv если ещё нет
      const sep = url.includes('?') ? '&' : '?';
      const fullUrl = url.includes('format=csv') ? url : `${url}${sep}format=csv`;

      const headers = new Headers();
      const access = getAccessToken();
      if (access) headers.set('Authorization', `Bearer ${access}`);
      const org = readOrgCookie();
      if (org) headers.set('X-Organization-Code', org.code);
      headers.set('Accept', 'text/csv');

      const res = await fetch(`${API_URL}${fullUrl}`, { headers });
      if (!res.ok) {
        alert(`Не удалось скачать (${res.status})`);
        return;
      }
      const blob = await res.blob();
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(link.href);
    } finally {
      setBusy(false);
    }
  };

  return (
    <button
      className="btn btn-ghost btn-sm"
      onClick={handle}
      disabled={busy || disabled}
      type="button"
    >
      <Icon name="bag" size={12} /> {busy ? 'Скачивание…' : label}
    </button>
  );
}
