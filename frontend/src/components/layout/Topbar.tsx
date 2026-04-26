'use client';

import { useEffect, useState } from 'react';

import Icon from '@/components/ui/Icon';
import { useLayout } from '@/contexts/LayoutContext';

import CommandPalette from './CommandPalette';
import FavoritesMenu from './FavoritesMenu';
import HelpMenu from './HelpMenu';
import UserMenu from './UserMenu';

interface Crumb {
  label: string;
  href?: string;
}

interface TopbarProps {
  crumbs: Crumb[];
}

export default function Topbar({ crumbs }: TopbarProps) {
  const [paletteOpen, setPaletteOpen] = useState(false);
  const { toggleSidebar } = useLayout();

  // ⌘K / Ctrl+K → открыть палитру
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const isK = e.key === 'k' || e.key === 'K';
      if (isK && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setPaletteOpen(true);
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);

  return (
    <header className="topbar">
      {/* Burger — виден только на мобиле (CSS hide на ≥768) */}
      <button
        className="topbar-burger"
        onClick={toggleSidebar}
        aria-label="Открыть меню"
        type="button"
      >
        <Icon name="menu" size={20} />
      </button>

      <div className="crumbs">
        {crumbs.map((c, i) => (
          <span key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {i > 0 && <span className="sep">/</span>}
            <span className={i === crumbs.length - 1 ? 'cur' : ''}>{c.label}</span>
          </span>
        ))}
      </div>

      <FavoritesMenu />

      <div className="spacer" />

      <button
        className="topbar-btn"
        title="Поиск (⌘K)"
        onClick={() => setPaletteOpen(true)}
        type="button"
      >
        <Icon name="search" size={16} />
        <span className="topbar-btn-hint">⌘K</span>
      </button>
      <HelpMenu onOpenPalette={() => setPaletteOpen(true)} />

      <UserMenu />

      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
      />
    </header>
  );
}
