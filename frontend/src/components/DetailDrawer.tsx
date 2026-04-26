'use client';

import Icon from '@/components/ui/Icon';

interface Tab {
  key: string;
  label: string;
  count?: number;
}

interface DetailDrawerProps {
  title: string;
  subtitle?: string;
  onClose: () => void;
  tabs?: Tab[];
  activeTab?: string;
  onTab?: (key: string) => void;
  actions?: React.ReactNode;
  children: React.ReactNode;
}

export default function DetailDrawer({ title, subtitle, onClose, tabs, activeTab, onTab, actions, children }: DetailDrawerProps) {
  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <div className="drawer" onClick={e => e.stopPropagation()}>
        <div className="drawer-hdr">
          <div style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 10 }}>
            <button className="close-btn" onClick={onClose} title="Закрыть (Esc)">
              <Icon name="close" size={16} />
            </button>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--fg-1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {title}
              </div>
              {subtitle && (
                <div style={{ fontSize: 12, color: 'var(--fg-3)', marginTop: 2 }}>{subtitle}</div>
              )}
            </div>
          </div>
          {actions && <div style={{ display: 'flex', gap: 8 }}>{actions}</div>}
        </div>

        {tabs && (
          <div className="drawer-tabs">
            {tabs.map(t => (
              <button
                key={t.key}
                className={`drawer-tab${activeTab === t.key ? ' active' : ''}`}
                onClick={() => onTab?.(t.key)}
              >
                {t.label}
                {t.count != null && (
                  <span className="badge-count" style={{ marginLeft: 6 }}>{t.count}</span>
                )}
              </button>
            ))}
          </div>
        )}

        <div className="drawer-body">{children}</div>
      </div>
    </div>
  );
}

/* Key-value block for detail views */
interface KVItem {
  k: string;
  v: React.ReactNode;
  mono?: boolean;
}

export function KV({ items, cols = 2 }: { items: KVItem[]; cols?: number }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: `repeat(${cols},1fr)`, gap: '10px 20px', marginBottom: 16 }}>
      {items.map((it, i) => (
        <div key={i}>
          <div style={{ fontSize: 11, color: 'var(--fg-3)', letterSpacing: '.04em', textTransform: 'uppercase', fontWeight: 600, marginBottom: 2 }}>
            {it.k}
          </div>
          <div style={{ fontSize: 13, color: 'var(--fg-1)', fontWeight: 500, fontFamily: it.mono ? 'var(--font-mono)' : 'var(--font-sans)' }}>
            {it.v}
          </div>
        </div>
      ))}
    </div>
  );
}

/* Activity timeline */
interface ActivityEvent {
  date: string;
  time: string;
  text: string;
  meta?: string;
  tone?: 'success' | 'warn' | 'danger' | 'info';
}

export function Activity({ events }: { events: ActivityEvent[] }) {
  const dotColor = (tone?: string) => {
    switch (tone) {
      case 'danger': return 'var(--danger)';
      case 'warn':   return 'var(--warning)';
      case 'success':return 'var(--success)';
      default:       return 'var(--brand-orange)';
    }
  };
  return (
    <div style={{ position: 'relative', paddingLeft: 18 }}>
      <div style={{ position: 'absolute', left: 4, top: 6, bottom: 6, width: 2, background: 'var(--border-strong)' }} />
      {events.map((e, i) => (
        <div key={i} style={{ position: 'relative', paddingBottom: 14 }}>
          <div style={{ position: 'absolute', left: -18, top: 6, width: 10, height: 10, borderRadius: '50%', background: dotColor(e.tone) }} />
          <div style={{ fontSize: 12, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>{e.date} · {e.time}</div>
          <div style={{ fontSize: 13, color: 'var(--fg-1)', marginTop: 2 }}>{e.text}</div>
          {e.meta && <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 2 }}>{e.meta}</div>}
        </div>
      ))}
    </div>
  );
}
