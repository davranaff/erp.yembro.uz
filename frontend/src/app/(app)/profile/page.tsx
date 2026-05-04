'use client';

import { useMemo, useState } from 'react';

import KpiCard from '@/components/ui/KpiCard';
import { useAuth } from '@/contexts/AuthContext';

import OrganizationsTab from './OrganizationsTab';
import ProfileTab from './ProfileTab';
import SecurityTab from './SecurityTab';

type Tab = 'profile' | 'security' | 'orgs';

const TABS: { key: Tab; label: string }[] = [
  { key: 'profile', label: 'Профиль' },
  { key: 'security', label: 'Безопасность' },
  { key: 'orgs', label: 'Организации' },
];

function initials(name: string): string {
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? '')
    .join('');
}

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('ru-RU', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

export default function ProfilePage() {
  const [tab, setTab] = useState<Tab>('profile');
  const { user, org } = useAuth();

  // KPI: количество организаций, общий уровень доступа в активной orgе, последний вход
  const kpi = useMemo(() => {
    if (!user) return null;
    const orgsCount = user.memberships?.length ?? 0;
    const activeMembership = user.memberships?.find(
      (m) => m.organization.code === org?.code,
    );
    const perms = activeMembership?.module_permissions ?? {};
    const modulesWithAccess = Object.values(perms).filter((l) => l !== 'none').length;
    const adminCount = Object.values(perms).filter((l) => l === 'admin').length;
    return {
      orgsCount,
      modulesWithAccess,
      adminCount,
      lastLogin: user.last_login,
    };
  }, [user, org]);

  if (!user) return null;

  return (
    <>
      {/* Hero-шапка с аватаром */}
      <div className="profile-hero">
        <div className="profile-hero-avatar">{initials(user.full_name)}</div>
        <div className="profile-hero-meta">
          <h1 className="profile-hero-name">{user.full_name}</h1>
          <div className="profile-hero-email">{user.email}</div>
          <div className="profile-hero-tags">
            {user.is_superuser && (
              <span className="profile-hero-tag profile-hero-tag-warn">
                Суперпользователь
              </span>
            )}
            {user.is_staff && !user.is_superuser && (
              <span className="profile-hero-tag profile-hero-tag-info">
                Сотрудник системы
              </span>
            )}
            {!user.is_active && (
              <span className="profile-hero-tag profile-hero-tag-danger">
                Деактивирован
              </span>
            )}
            {user.phone && (
              <span className="profile-hero-tag profile-hero-tag-muted">
                {user.phone}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* KPI */}
      {kpi && (
        <div className="kpi-row" style={{ marginBottom: 16 }}>
          <KpiCard
            tone="orange"
            iconName="building"
            label="Организаций"
            sub="доступно"
            value={String(kpi.orgsCount)}
          />
          <KpiCard
            tone="blue"
            iconName="grid"
            label="Модулей с доступом"
            sub={org?.name ? `в «${org.name}»` : 'в активной'}
            value={String(kpi.modulesWithAccess)}
          />
          <KpiCard
            tone="green"
            iconName="check"
            label="Админ-уровень"
            sub="модулей где admin"
            value={String(kpi.adminCount)}
          />
          <KpiCard
            tone="blue"
            iconName="book"
            label="Последний вход"
            sub={kpi.lastLogin ? 'в систему' : 'нет данных'}
            value={formatDate(kpi.lastLogin)}
          />
        </div>
      )}

      {/* Табы */}
      <div className="profile-tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={'profile-tab' + (tab === t.key ? ' active' : '')}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'profile' && <ProfileTab />}
      {tab === 'security' && <SecurityTab />}
      {tab === 'orgs' && <OrganizationsTab />}
    </>
  );
}
