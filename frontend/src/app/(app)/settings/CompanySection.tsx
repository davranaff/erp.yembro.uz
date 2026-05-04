'use client';

import { useEffect, useState } from 'react';

import Panel from '@/components/ui/Panel';
import { useAuth } from '@/contexts/AuthContext';
import { ApiError } from '@/lib/api';
import { useCurrenciesSorted } from '@/hooks/useCurrencyRates';
import { useHasLevel } from '@/hooks/usePermissions';
import {
  useOrganizationDetails,
  useUpdateOrganization,
} from '@/hooks/useOrganizationDetails';

const DIRECTION_OPTIONS: { value: 'broiler' | 'egg' | 'mixed'; label: string }[] = [
  { value: 'broiler', label: 'Бройлер' },
  { value: 'egg',     label: 'Яичное' },
  { value: 'mixed',   label: 'Смешанное' },
];

const TIMEZONES = [
  'Asia/Tashkent',
  'Asia/Samarkand',
  'Asia/Almaty',
  'Europe/Moscow',
  'UTC',
];

export default function CompanySection() {
  const { org } = useAuth();
  const { data, isLoading, error } = useOrganizationDetails();
  const { data: currencies } = useCurrenciesSorted();
  const update = useUpdateOrganization();
  const hasLevel = useHasLevel();
  const canEdit = hasLevel('admin', 'rw');

  const [name, setName] = useState('');
  const [legalName, setLegalName] = useState('');
  const [inn, setInn] = useState('');
  const [legalAddress, setLegalAddress] = useState('');
  const [direction, setDirection] = useState<'broiler' | 'egg' | 'mixed'>('broiler');
  const [accountingCurrency, setAccountingCurrency] = useState('');
  const [tz, setTz] = useState('Asia/Tashkent');
  const [savedAt, setSavedAt] = useState<Date | null>(null);

  useEffect(() => {
    if (!data) return;
    setName(data.name ?? '');
    setLegalName(data.legal_name ?? '');
    setInn(data.inn ?? '');
    setLegalAddress(data.legal_address ?? '');
    setDirection(data.direction);
    setAccountingCurrency(data.accounting_currency);
    setTz(data.timezone ?? 'Asia/Tashkent');
  }, [data]);

  if (isLoading) {
    return (
      <Panel title="Компания">
        <div style={{ padding: 16, color: 'var(--fg-3)' }}>Загрузка…</div>
      </Panel>
    );
  }

  if (error) {
    return (
      <Panel title="Компания">
        <div style={{ padding: 16, color: 'var(--danger)' }}>
          Ошибка загрузки: {error.message}
        </div>
      </Panel>
    );
  }

  if (!data) return null;

  const dirty =
    data.name !== name ||
    data.legal_name !== legalName ||
    data.inn !== inn ||
    data.legal_address !== legalAddress ||
    data.direction !== direction ||
    data.accounting_currency !== accountingCurrency ||
    data.timezone !== tz;

  const reset = () => {
    setName(data.name);
    setLegalName(data.legal_name);
    setInn(data.inn);
    setLegalAddress(data.legal_address);
    setDirection(data.direction);
    setAccountingCurrency(data.accounting_currency);
    setTz(data.timezone);
  };

  const save = async () => {
    setSavedAt(null);
    try {
      await update.mutateAsync({
        name,
        legal_name: legalName,
        inn,
        legal_address: legalAddress,
        direction,
        accounting_currency: accountingCurrency,
        timezone: tz,
      });
      setSavedAt(new Date());
    } catch {
      /* ошибка отобразится через update.error */
    }
  };

  const fieldErrors =
    update.error instanceof ApiError && update.error.status === 400
      ? ((update.error.data as Record<string, string[]>) ?? {})
      : {};

  const disabled = !canEdit || update.isPending;

  return (
    <Panel title={`Компания · ${org?.code ?? ''}`}>
      {!canEdit && (
        <div
          style={{
            marginBottom: 12,
            padding: 8,
            fontSize: 12,
            color: 'var(--fg-3)',
            background: 'var(--bg-soft)',
            borderRadius: 4,
          }}
        >
          Просмотр. Для редактирования нужен уровень «rw» или выше на модуль «Администрирование».
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>Название (короткое)</label>
          <input
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={disabled}
          />
          {fieldErrors.name && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>
              {fieldErrors.name.join(' · ')}
            </div>
          )}
        </div>

        <div className="field">
          <label>ИНН</label>
          <input
            className="input mono"
            value={inn}
            onChange={(e) => setInn(e.target.value)}
            disabled={disabled}
          />
          {fieldErrors.inn && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>
              {fieldErrors.inn.join(' · ')}
            </div>
          )}
        </div>

        <div className="field">
          <label>Юр. название</label>
          <input
            className="input"
            value={legalName}
            onChange={(e) => setLegalName(e.target.value)}
            disabled={disabled}
          />
        </div>

        <div className="field">
          <label>Направление</label>
          <select
            className="input"
            value={direction}
            onChange={(e) => setDirection(e.target.value as typeof direction)}
            disabled={disabled}
          >
            {DIRECTION_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label>Валюта учёта</label>
          <select
            className="input"
            value={accountingCurrency}
            onChange={(e) => setAccountingCurrency(e.target.value)}
            disabled={disabled}
          >
            {currencies?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.code} · {c.name_ru}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label>Часовой пояс</label>
          <select
            className="input"
            value={tz}
            onChange={(e) => setTz(e.target.value)}
            disabled={disabled}
          >
            {TIMEZONES.map((z) => (
              <option key={z} value={z}>
                {z}
              </option>
            ))}
          </select>
        </div>

        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>Юридический адрес</label>
          <input
            className="input"
            value={legalAddress}
            onChange={(e) => setLegalAddress(e.target.value)}
            disabled={disabled}
          />
        </div>
      </div>

      {update.error instanceof ApiError && update.error.status !== 400 && (
        <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 12 }}>
          Ошибка {update.error.status}
        </div>
      )}

      <div
        style={{
          display: 'flex',
          gap: 8,
          alignItems: 'center',
          justifyContent: 'flex-end',
          marginTop: 12,
          paddingTop: 12,
          borderTop: '1px solid var(--border)',
        }}
      >
        {savedAt && !dirty && (
          <span style={{ fontSize: 12, color: 'var(--success)' }}>
            Сохранено {savedAt.toLocaleTimeString('ru')}
          </span>
        )}
        <button className="btn btn-ghost" onClick={reset} disabled={!dirty || disabled}>
          Отмена
        </button>
        <button
          className="btn btn-primary"
          onClick={save}
          disabled={!dirty || disabled}
        >
          {update.isPending ? 'Сохранение…' : 'Сохранить'}
        </button>
      </div>
    </Panel>
  );
}
