'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';

import OrgSelector from '@/components/auth/OrgSelector';
import Icon from '@/components/ui/Icon';
import { useAuth } from '@/contexts/AuthContext';
import { useNavigationStatus } from '@/contexts/NavigationContext';

function getInitials(fullName: string | undefined): string {
  if (!fullName) return '··';
  const parts = fullName.trim().split(/\s+/).slice(0, 2);
  return parts.map((p) => p[0]?.toUpperCase() ?? '').join('') || '··';
}

/**
 * Topbar user-menu: имя/инициалы + dropdown с действиями (Профиль / Сменить организацию / Выход).
 */
export default function UserMenu() {
  const { user, org, logout } = useAuth();
  const { isNavigating, startNavigation } = useNavigationStatus();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [orgPickerOpen, setOrgPickerOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  const go = (href: string) => {
    if (isNavigating) return;
    setOpen(false);
    startNavigation(href);
    router.push(href);
  };

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [open]);

  const initials = getInitials(user?.full_name);
  const name = user?.full_name ?? '—';
  const memberships = user?.memberships ?? [];

  return (
    <>
      <div ref={ref} style={{ position: 'relative' }}>
        <div
          className="topbar-user"
          onClick={() => setOpen((v) => !v)}
          style={{ cursor: 'pointer', userSelect: 'none' }}
        >
          <div className="avatar">{initials}</div>
          <span>{name}</span>
          <Icon name="chevron-down" size={12} style={{ color: 'var(--fg-3)' }} />
        </div>

        {open && (
          <div
            className="topbar-user-menu"
            style={{
              position: 'absolute',
              right: 0,
              top: 'calc(100% + 6px)',
              width: 240,
              background: 'var(--bg-card)',
              border: '1px solid var(--border)',
              borderRadius: 6,
              boxShadow: 'var(--shadow-md)',
              zIndex: 50,
              padding: 6,
            }}
          >
            <div
              style={{
                padding: '8px 10px',
                borderBottom: '1px solid var(--border)',
                marginBottom: 6,
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 600 }}>{name}</div>
              <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>{user?.email}</div>
              {org && (
                <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
                  Активная: <span style={{ color: 'var(--brand-orange)' }}>{org.name}</span>
                </div>
              )}
            </div>

            <button
              className="nav-item"
              style={{ width: '100%', justifyContent: 'flex-start' }}
              onClick={() => go('/profile')}
              disabled={isNavigating}
            >
              <Icon name="users" size={14} />
              <span>Профиль</span>
            </button>

            {memberships.length > 1 && (
              <button
                className="nav-item"
                style={{ width: '100%', justifyContent: 'flex-start' }}
                onClick={() => {
                  setOpen(false);
                  setOrgPickerOpen(true);
                }}
              >
                <Icon name="building" size={14} />
                <span>Сменить организацию</span>
              </button>
            )}

            <button
              className="nav-item"
              style={{ width: '100%', justifyContent: 'flex-start' }}
              onClick={() => go('/settings')}
              disabled={isNavigating}
            >
              <Icon name="settings" size={14} />
              <span>Настройки</span>
            </button>

            <div style={{ borderTop: '1px solid var(--border)', margin: '6px 0' }} />

            <button
              className="nav-item"
              style={{ width: '100%', justifyContent: 'flex-start', color: 'var(--danger)' }}
              onClick={logout}
            >
              <Icon name="close" size={14} />
              <span>Выйти</span>
            </button>
          </div>
        )}
      </div>

      <OrgSelector open={orgPickerOpen} onClose={() => setOrgPickerOpen(false)} />
    </>
  );
}
