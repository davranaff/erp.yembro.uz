'use client';

import { useMemo } from 'react';

import { makeCrud } from '@/lib/crudFactory';

export interface UserFavoritePage {
  id: string;
  href: string;
  label: string;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

interface FavoriteInput {
  href: string;
  label: string;
  sort_order?: number;
}

/**
 * CRUD-хуки для избранного (per-user).
 *
 * Endpoint `/api/users/me/favorites/` не требует X-Organization-Code:
 * закладки следуют за пользователем при переключении организаций.
 */
export const favoritesCrud = makeCrud<UserFavoritePage, FavoriteInput, FavoriteInput>({
  key: ['favorites'],
  path: '/api/users/me/favorites/',
  ordering: 'sort_order',
  skipOrg: true,
});

export function useFavorites() {
  return favoritesCrud.useList({});
}

export function useAddFavorite() {
  return favoritesCrud.useCreate();
}

export function useRemoveFavorite() {
  return favoritesCrud.useDelete();
}

/** Удобный хелпер для UI: закреплена ли текущая страница. */
export function useIsFavorite(href: string | null | undefined): {
  isFavorite: boolean;
  favorite: UserFavoritePage | null;
} {
  const { data } = useFavorites();
  return useMemo(() => {
    if (!href || !data) return { isFavorite: false, favorite: null };
    const fav = data.find((f) => f.href === href) ?? null;
    return { isFavorite: Boolean(fav), favorite: fav };
  }, [href, data]);
}
