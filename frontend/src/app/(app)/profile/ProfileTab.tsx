'use client';

import { useEffect, useMemo, useState } from 'react';

import Panel from '@/components/ui/Panel';
import { useAuth } from '@/contexts/AuthContext';
import { ApiError } from '@/lib/api';
import { useUpdateProfile } from '@/hooks/useUpdateProfile';
import type { ModuleLevel } from '@/types/auth';

const LEVEL_LABEL: Record<ModuleLevel, string> = {
  none: 'Нет доступа',
  r: 'Просмотр',
  rw: 'Ввод документов',
  admin: 'Администратор',
};
const LEVEL_TONE: Record<ModuleLevel, string> = {
  none: 'var(--fg-3)',
  r: 'var(--info)',
  rw: 'var(--success)',
  admin: 'var(--brand-orange)',
};
const MODULE_LABEL: Record<string, string> = {
  core: 'Ядро', matochnik: 'Маточник', incubation: 'Инкубация',
  feedlot: 'Откорм', slaughter: 'Убойня', feed: 'Корма', vet: 'Вет. аптека',
  stock: 'Склад', ledger: 'Учёт', reports: 'Отчёты',
  purchases: 'Закупки', sales: 'Продажи', admin: 'Администрирование',
};

export default function ProfileTab() {
  const { user, org } = useAuth();
  const update = useUpdateProfile();

  // Права в активной организации
  const activePermissions = useMemo(() => {
    if (!user || !org) return [];
    const m = user.memberships?.find((x) => x.organization.code === org.code);
    if (!m) return [];
    return Object.entries(m.module_permissions)
      .filter(([, level]) => level !== 'none')
      .sort((a, b) => a[0].localeCompare(b[0]));
  }, [user, org]);

  const [fullName, setFullName] = useState('');
  const [phone, setPhone] = useState('');
  const [savedAt, setSavedAt] = useState<Date | null>(null);

  useEffect(() => {
    if (user) {
      setFullName(user.full_name);
      setPhone(user.phone ?? '');
    }
  }, [user]);

  if (!user) return null;

  const dirty = user.full_name !== fullName || (user.phone ?? '') !== phone;

  const handleSave = async () => {
    setSavedAt(null);
    try {
      await update.mutateAsync({ full_name: fullName, phone });
      setSavedAt(new Date());
    } catch {
      // ошибка уже доступна в update.error
    }
  };

  const handleReset = () => {
    setFullName(user.full_name);
    setPhone(user.phone ?? '');
  };

  const fieldErrors = (update.error instanceof ApiError && update.error.status === 400)
    ? (update.error.data as Record<string, string[]>) ?? {}
    : {};

  return (
    <>
    <Panel title="Профиль">
      <div className="form-grid-2">
        <div className="field">
          <label>ФИО</label>
          <input
            className="input"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
          />
          {fieldErrors.full_name && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>
              {fieldErrors.full_name.join(' · ')}
            </div>
          )}
        </div>

        <div className="field">
          <label>Телефон</label>
          <input
            className="input"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+998 …"
          />
          {fieldErrors.phone && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>
              {fieldErrors.phone.join(' · ')}
            </div>
          )}
        </div>

        <div className="field">
          <label>Email (read-only)</label>
          <input className="input" value={user.email} disabled />
        </div>

        <div className="field">
          <label>Последний вход</label>
          <input
            className="input mono"
            value={user.last_login ? new Date(user.last_login).toLocaleString('ru') : '—'}
            disabled
          />
        </div>
      </div>

      {update.error && update.error instanceof ApiError && update.error.status !== 400 && (
        <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 12 }}>
          Ошибка: {update.error.status}
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
        <button className="btn btn-ghost" onClick={handleReset} disabled={!dirty || update.isPending}>
          Отмена
        </button>
        <button
          className="btn btn-primary"
          onClick={handleSave}
          disabled={!dirty || update.isPending}
        >
          {update.isPending ? 'Сохранение…' : 'Сохранить'}
        </button>
      </div>
    </Panel>

    {/* Мои права в активной организации */}
    {org && (
      <Panel title={`Мои права в «${org.name}»`} style={{ marginTop: 16 }}>
        {activePermissions.length === 0 ? (
          <div style={{ padding: 12, fontSize: 13, color: 'var(--fg-3)' }}>
            В этой организации у вас нет прав ни на один модуль. Обратитесь
            к администратору компании.
          </div>
        ) : (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
              gap: 8,
              padding: 4,
            }}
          >
            {activePermissions.map(([code, level]) => (
              <div
                key={code}
                style={{
                  padding: '8px 10px',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  background: 'var(--bg-card)',
                  borderLeft: `3px solid ${LEVEL_TONE[level]}`,
                }}
              >
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--fg-1)' }}>
                  {MODULE_LABEL[code] ?? code}
                </div>
                <div
                  style={{
                    fontSize: 11,
                    color: LEVEL_TONE[level],
                    marginTop: 2,
                    fontWeight: 500,
                  }}
                >
                  {LEVEL_LABEL[level]}
                </div>
              </div>
            ))}
          </div>
        )}
        <div style={{ padding: 8, fontSize: 11, color: 'var(--fg-3)' }}>
          Уровни: <b>R</b> — просмотр · <b>RW</b> — ввод документов · <b>Admin</b> — полный
          контроль модуля. Изменить права может администратор через раздел «Роли и права».
        </div>
      </Panel>
    )}
    </>
  );
}
