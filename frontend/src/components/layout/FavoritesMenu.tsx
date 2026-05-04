'use client';

import { useEffect, useRef, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';

import Icon from '@/components/ui/Icon';
import { useNavigationStatus } from '@/contexts/NavigationContext';
import {
  useAddFavorite,
  useFavorites,
  useIsFavorite,
  useRemoveFavorite,
} from '@/hooks/useFavorites';
import { ApiError } from '@/lib/api';

import { labelForHref } from './nav';

/**
 * Меню «Избранные страницы» в топбаре.
 *
 * Хранилище — бэкенд `/api/users/me/favorites/` (per-user). Список синхронен
 * между устройствами; на сайдбаре те же закладки рендерятся в секции
 * «Закреплённые» сверху.
 */
export default function FavoritesMenu() {
  const router = useRouter();
  const pathname = usePathname();
  const { startNavigation, isNavigating } = useNavigationStatus();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  const { data: favorites = [], isLoading } = useFavorites();
  const addFav = useAddFavorite();
  const removeFav = useRemoveFavorite();
  const { isFavorite, favorite } = useIsFavorite(pathname);

  // Закрытие по клику снаружи / Escape
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const addCurrent = () => {
    const label = labelForHref(pathname);
    if (!label) return; // страница не из навигации
    if (isFavorite) return;
    addFav.mutate(
      { href: pathname, label },
      {
        onError: (err: ApiError) => {
          alert(err.message || 'Не удалось закрепить страницу.');
        },
      },
    );
  };

  const removeById = (id: string) => {
    removeFav.mutate(id, {
      onError: (err: ApiError) => {
        alert(err.message || 'Не удалось снять с избранного.');
      },
    });
  };

  const navigate = (href: string) => {
    setOpen(false);
    if (isNavigating) return;
    if (pathname === href) return;
    startNavigation(href);
    router.push(href);
  };

  // Можно ли закрепить текущую страницу
  const canPinCurrent = !isFavorite && labelForHref(pathname) !== null;

  return (
    <div ref={wrapRef} style={{ position: 'relative' }}>
      <button
        className={'fav-tab' + (open ? ' active' : '')}
        onClick={() => setOpen((v) => !v)}
        type="button"
      >
        <Icon name="star" size={14} />
        Избранные страницы
        {favorites.length > 0 && (
          <span className="fav-tab-count">{favorites.length}</span>
        )}
      </button>

      {open && (
        <div className="fav-menu" role="menu">
          <div className="fav-menu-hdr">
            <span>Избранные страницы</span>
            {canPinCurrent && (
              <button
                className="btn btn-ghost btn-sm"
                onClick={addCurrent}
                type="button"
                title="Добавить текущую страницу"
                disabled={addFav.isPending}
              >
                <Icon name="plus" size={12} />{' '}
                {addFav.isPending ? '…' : 'Закрепить эту'}
              </button>
            )}
            {isFavorite && favorite && (
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => removeById(favorite.id)}
                type="button"
                title="Снять с избранного"
                style={{ color: 'var(--fg-3)' }}
                disabled={removeFav.isPending}
              >
                <Icon name="close" size={12} /> Снять
              </button>
            )}
          </div>

          {isLoading ? (
            <div className="fav-menu-empty">Загрузка…</div>
          ) : favorites.length === 0 ? (
            <div className="fav-menu-empty">
              Ничего не закреплено.
              <br />
              Откройте нужную страницу и нажмите «Закрепить эту» — она появится
              здесь и в сайдбаре сверху.
            </div>
          ) : (
            <div className="fav-menu-list">
              {favorites.map((f) => {
                const isActive = pathname === f.href;
                return (
                  <div
                    key={f.id}
                    className={'fav-menu-item' + (isActive ? ' active' : '')}
                  >
                    <button
                      className="fav-menu-link"
                      onClick={() => navigate(f.href)}
                      type="button"
                    >
                      <Icon name="star" size={12} />
                      <span className="fav-menu-label">{f.label}</span>
                      <span className="fav-menu-href mono">{f.href}</span>
                    </button>
                    <button
                      className="fav-menu-remove"
                      onClick={() => removeById(f.id)}
                      type="button"
                      title="Снять с избранного"
                      disabled={removeFav.isPending}
                    >
                      <Icon name="close" size={12} />
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
