'use client';

import { useMemo, useState } from 'react';

import OrganizationsTab from '@/app/(app)/profile/OrganizationsTab';
import ProfileTab from '@/app/(app)/profile/ProfileTab';
import SecurityTab from '@/app/(app)/profile/SecurityTab';
import Icon from '@/components/ui/Icon';
import { useAuth } from '@/contexts/AuthContext';
import { useHasLevel } from '@/hooks/usePermissions';
import type { ModuleLevel } from '@/types/auth';

import AccountsSection from './AccountsSection';
import AuditSection from './AuditSection';
import CompanySection from './CompanySection';
import ExpenseArticlesSection from './ExpenseArticlesSection';
import IntegrationsSection from './IntegrationsSection';
import ModulesSection from './ModulesSection';
import RolesSection from './RolesSection';

interface Section {
  key: string;
  title: string;
  desc: string;
  group: 'personal' | 'company' | 'system';
  /** Если задано — секция видна только при наличии этих прав. */
  module?: string;
  min?: ModuleLevel;
}

const SECTIONS: Section[] = [
  { key: 'profile',  title: 'Профиль',      desc: 'Личные данные',               group: 'personal' },
  { key: 'security', title: 'Безопасность', desc: 'Смена пароля',                group: 'personal' },
  { key: 'orgs',     title: 'Организации',  desc: 'Переключение активной',       group: 'personal' },

  { key: 'co',       title: 'Компания',        desc: 'Реквизиты и настройки',       group: 'company',
    module: 'admin',  min: 'r' },
  { key: 'mod',      title: 'Модули',          desc: 'Включение / отключение',      group: 'company',
    module: 'admin',  min: 'r' },
  { key: 'acc',      title: 'План счетов',     desc: 'Счета и субсчета',            group: 'company',
    module: 'ledger', min: 'r' },
  { key: 'expense',  title: 'Статьи расходов', desc: 'Газ, электричество, ЗП…',     group: 'company',
    module: 'ledger', min: 'r' },
  { key: 'role',     title: 'Роли и права',    desc: 'Матрица доступов',            group: 'company',
    module: 'admin',  min: 'r' },

  { key: 'aud',      title: 'Аудит',        desc: 'Журнал действий',             group: 'system',
    module: 'admin',  min: 'r' },
  { key: 'int',      title: 'Интеграции',   desc: 'CBU, 1С, Банк-клиент, ЭДО',   group: 'system',
    module: 'admin',  min: 'r' },
];

const GROUP_LABEL: Record<Section['group'], string> = {
  personal: 'Личные',
  company:  'Компания',
  system:   'Система',
};

export default function SettingsPage() {
  const { org } = useAuth();
  const hasLevel = useHasLevel();
  const [active, setActive] = useState<string>('profile');

  // Фильтрация по правам активной организации. Личные секции
  // (profile/security/orgs) — без модуля, видны всем авторизованным.
  const visibleSections = useMemo(
    () => SECTIONS.filter((s) => !s.module || hasLevel(s.module, s.min ?? 'r')),
    [hasLevel],
  );

  // Если активная секция оказалась скрытой (после смены организации) —
  // переключаемся на первую доступную.
  const section =
    visibleSections.find((s) => s.key === active) ?? visibleSections[0];

  const groups = Object.entries(
    visibleSections.reduce<Record<string, Section[]>>((acc, s) => {
      (acc[s.group] ??= []).push(s);
      return acc;
    }, {}),
  ) as [Section['group'], Section[]][];

  const renderSection = () => {
    if (!section) return null;
    switch (section.key) {
      case 'profile':  return <ProfileTab />;
      case 'security': return <SecurityTab />;
      case 'orgs':     return <OrganizationsTab />;
      case 'co':       return <CompanySection />;
      case 'mod':      return <ModulesSection />;
      case 'acc':      return <AccountsSection />;
      case 'expense':  return <ExpenseArticlesSection />;
      case 'role':     return <RolesSection />;
      case 'aud':      return <AuditSection />;
      case 'int':      return <IntegrationsSection />;
      default:         return null;
    }
  };

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Настройки</h1>
          <div className="sub">
            {org ? `Компания «${org.name}» · настройка системы` : 'Настройка системы'}
          </div>
        </div>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '260px 1fr',
          gap: 16,
          alignItems: 'start',
        }}
        className="settings-grid"
      >
        <div
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
            borderRadius: 6,
            padding: 6,
            position: 'sticky',
            top: 16,
          }}
        >
          {groups.map(([groupKey, items]) => (
            <div key={groupKey} style={{ marginBottom: 6 }}>
              <div
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  color: 'var(--fg-3)',
                  textTransform: 'uppercase',
                  letterSpacing: '.06em',
                  padding: '8px 10px 4px',
                }}
              >
                {GROUP_LABEL[groupKey]}
              </div>
              {items.map((s) => (
                <button
                  key={s.key}
                  className={'nav-item' + (s.key === active ? ' active' : '')}
                  style={{
                    width: '100%',
                    justifyContent: 'flex-start',
                    borderRadius: 4,
                    textAlign: 'left',
                  }}
                  onClick={() => setActive(s.key)}
                >
                  <Icon name="chevron-right" size={14} />
                  <span>{s.title}</span>
                </button>
              ))}
            </div>
          ))}
        </div>

        <div style={{ minWidth: 0 }}>{renderSection()}</div>
      </div>
    </>
  );
}
