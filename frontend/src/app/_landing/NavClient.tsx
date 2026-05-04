'use client';

import { useState } from 'react';
import type { ReactNode } from 'react';

import Icon from '@/components/ui/Icon';

interface Props {
  logo: ReactNode;
}

export default function NavClient({ logo }: Props) {
  const [open, setOpen] = useState(false);

  const close = () => setOpen(false);

  return (
    <>
      <nav className="lp-nav" aria-label="Навигация">
        {logo}
        <div className="lp-nav-links">
          <a href="#features" className="lp-nav-link" onClick={close}>Модули</a>
          <a href="#how"      className="lp-nav-link" onClick={close}>Как работает</a>
          <a href="#why"      className="lp-nav-link" onClick={close}>Преимущества</a>
          <a href="#demo"     className="lp-nav-link" onClick={close}>Демо</a>
          <a href="/login" className="lp-btn-lg btn-primary" style={{ height: 36, fontSize: 14, padding: '0 18px' }}>
            Войти
          </a>
          <button
            className="lp-nav-hamburger"
            aria-label={open ? 'Закрыть меню' : 'Открыть меню'}
            aria-expanded={open}
            onClick={() => setOpen(o => !o)}
          >
            <Icon name={open ? 'close' : 'menu'} size={22} />
          </button>
        </div>
      </nav>

      <div className={`lp-mobile-menu${open ? ' open' : ''}`} aria-hidden={!open}>
        <a href="#features" onClick={close}>Модули</a>
        <a href="#how"      onClick={close}>Как работает</a>
        <a href="#why"      onClick={close}>Преимущества</a>
        <a href="#demo"     onClick={close}>Демо</a>
        <a href="/login" className="lp-mobile-cta">Войти в систему</a>
      </div>
    </>
  );
}
