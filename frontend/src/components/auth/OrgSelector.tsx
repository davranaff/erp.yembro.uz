'use client';

import Icon from '@/components/ui/Icon';
import Modal from '@/components/ui/Modal';
import { useAuth } from '@/contexts/AuthContext';
import { Membership } from '@/types/auth';

interface Props {
  open: boolean;
  onClose: () => void;
  /** Куда вести пользователя после выбора организации (default: остаёмся на текущей странице). */
  onSelected?: (membership: Membership) => void;
}

/**
 * Модал выбора активной организации из memberships текущего юзера.
 */
export default function OrgSelector({ open, onClose, onSelected }: Props) {
  const { user, org, setOrg } = useAuth();

  if (!open) return null;

  const memberships = user?.memberships ?? [];

  const handlePick = (m: Membership) => {
    setOrg({ code: m.organization.code, name: m.organization.name });
    onSelected?.(m);
    onClose();
  };

  return (
    <Modal title="Выбор компании" onClose={onClose}>
      {memberships.length === 0 && (
        <div style={{ padding: 16, color: 'var(--fg-3)' }}>
          У вас нет активных организаций.
        </div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {memberships.map((m) => {
          const active = m.organization.code === org?.code;
          return (
            <div
              key={m.id}
              className="company-item"
              onClick={() => handlePick(m)}
              style={{
                outline: active ? '2px solid var(--brand-orange)' : 'none',
              }}
            >
              <div
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: 6,
                  background: 'var(--brand-orange)',
                  color: 'white',
                  display: 'grid',
                  placeItems: 'center',
                  fontSize: 13,
                  fontWeight: 700,
                  flexShrink: 0,
                }}
              >
                {m.organization.code.slice(0, 2).toUpperCase()}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, fontWeight: 600 }}>{m.organization.name}</div>
                <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>
                  {m.position_title || m.organization.direction}
                </div>
              </div>
              {active && (
                <span className="badge-count" style={{ background: 'var(--brand-orange)', color: 'white' }}>
                  активна
                </span>
              )}
              <Icon name="chevron-right" size={16} style={{ color: 'var(--fg-muted)' }} />
            </div>
          );
        })}
      </div>
    </Modal>
  );
}
