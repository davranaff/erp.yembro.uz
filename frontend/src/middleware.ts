import { NextRequest, NextResponse } from 'next/server';

import { ORG_COOKIE } from './lib/tokens';

const PUBLIC_PATHS = new Set(['/login']);

/**
 * Серверный guard на cookie `erp.org`. JWT-токены живут в localStorage и
 * на сервере не доступны — поэтому здесь только грубая отсечка: если нет
 * выбранной организации (нет cookie), редиректим на /login.
 *
 * Полная клиентская валидация (access-token + refresh) происходит в AuthGuard.
 */
export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  if (PUBLIC_PATHS.has(pathname) || pathname.startsWith('/api')) {
    return NextResponse.next();
  }

  const orgCookie = req.cookies.get(ORG_COOKIE);
  if (!orgCookie) {
    const url = req.nextUrl.clone();
    url.pathname = '/login';
    url.searchParams.set('next', pathname);
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon|public).*)'],
};
