'use client';

import { useMemo, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';

import OrgSelector from '@/components/auth/OrgSelector';
import Icon from '@/components/ui/Icon';
import { useAuth } from '@/contexts/AuthContext';
import { useLayout } from '@/contexts/LayoutContext';
import { useNavigationStatus } from '@/contexts/NavigationContext';
import { useFavorites } from '@/hooks/useFavorites';

import { flatItems, NAV, NAV_FOOTER, isGroup, type NavEntry, type NavGroup, type NavItem } from './nav';

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { org, hasLevel, user } = useAuth();
  const { isNavigating, targetPath, startNavigation } = useNavigationStatus();
  const { closeSidebar } = useLayout();
  const [orgPickerOpen, setOrgPickerOpen] = useState(false);

  // Закреплённые страницы (per-user, синк с бэкендом).
  // Список загружается лениво; пока не пришёл — секция не рендерится.
  const { data: favorites = [] } = useFavorites();

  // Активный href = самый длинный из всех навигационных, который матчит pathname.
  // Без этого «/feed» подсвечивался бы вместе с «/feed/shrinkage-profiles».
  const activeHref = useMemo(() => {
    const all = [...flatItems().map((i) => i.href), ...favorites.map((f) => f.href)];
    let best = '';
    for (const href of all) {
      if (!href) continue;
      const matches = pathname === href
        || (href !== '/' && pathname.startsWith(href + '/'));
      if (matches && href.length > best.length) best = href;
    }
    return best;
  }, [pathname, favorites]);

  const go = (href: string) => {
    if (isNavigating) return;             // защита от двойного клика
    if (pathname === href) return;        // та же страница
    startNavigation(href);                // RouteProgress тоже стартует, это ok (idempotent)
    router.push(href);
  };

  const allowed = (item: NavItem) => {
    if (!item.module) return true;
    return hasLevel(item.module, item.min ?? 'r');
  };

  // Карта nav-items по href — для проверки прав на закреплённую страницу
  // (если её модуль закрыт — пункт скрываем, но запись в БД оставляем).
  const navByHref = new Map(flatItems().map((i) => [i.href, i]));
  const visibleFavorites = favorites.filter((f) => {
    const navItem = navByHref.get(f.href);
    // Если страницы нет в навигации (старая закладка / кастомный путь) —
    // показываем без RBAC-проверки. Если есть — проверяем доступ.
    return navItem ? allowed(navItem) : true;
  });

  // Если страница уже в «Закреплённых» — в основной навигации её не показываем
  // (избегаем дубликата). Set строится из visibleFavorites чтобы скрытые
  // RBAC'ом закладки всё равно не убирали пункт из основной навигации.
  const pinnedHrefs = new Set(visibleFavorites.map((f) => f.href));

  // Сворачиваем подряд идущие группы без видимых пунктов.
  const visibleEntries: NavEntry[] = [];
  let pendingGroup: NavGroup | null = null;
  for (const entry of NAV) {
    if (isGroup(entry)) {
      pendingGroup = entry;
    } else if (allowed(entry) && !pinnedHrefs.has(entry.href)) {
      if (pendingGroup) {
        visibleEntries.push(pendingGroup);
        pendingGroup = null;
      }
      visibleEntries.push(entry);
    }
  }

  const canSwitchOrg = (user?.memberships?.length ?? 0) > 1;
  const orgInitials = org?.code.slice(0, 2).toUpperCase() ?? '··';
  const orgName = org?.name ?? '—';

  return (
    <>
      <aside className="sidebar">
        <div className="sidebar-logo">
          <svg height="26" viewBox="0 0 120 28" fill="none">
            <circle cx="14" cy="14" r="12" fill="#E8751A" />
            <text x="9" y="19" fill="white" fontSize="13" fontWeight="700" fontFamily="sans-serif">Y</text>
            <text x="32" y="20" fill="#2A1F0E" fontSize="15" fontWeight="700" fontFamily="sans-serif">YemBro</text>
          </svg>
          {/* ✕ — виден только на мобиле, закрывает drawer-сайдбар */}
          <button
            className="sidebar-close"
            onClick={closeSidebar}
            aria-label="Закрыть меню"
            type="button"
          >
            <Icon name="close" size={18} />
          </button>
        </div>

        <button
          className="sidebar-company"
          onClick={() => canSwitchOrg && setOrgPickerOpen(true)}
          style={{
            cursor: canSwitchOrg ? 'pointer' : 'default',
            background: 'none',
            border: 'none',
            width: '100%',
            textAlign: 'left',
          }}
          title={canSwitchOrg ? 'Сменить компанию' : undefined}
        >
          <div className="avatar">{orgInitials}</div>
          <div className="name">{orgName}</div>
          {canSwitchOrg && <Icon name="chevron-down" size={14} style={{ color: 'var(--fg-3)' }} />}
        </button>

        {visibleFavorites.length > 0 && (
          <nav className={`sidebar-nav sidebar-nav-pins${isNavigating ? ' is-navigating' : ''}`}>
            <div className="nav-group">Закреплённые</div>
            {visibleFavorites.map((fav) => {
              const navItem = navByHref.get(fav.href);
              const icon = navItem?.icon ?? 'star';
              const active = fav.href === activeHref;
              const isTarget = isNavigating && targetPath === fav.href;
              return (
                <div
                  key={fav.id}
                  className={
                    'nav-item' +
                    (active ? ' active' : '') +
                    (isTarget ? ' loading' : '') +
                    (isNavigating && !isTarget ? ' disabled' : '')
                  }
                  onClick={() => go(fav.href)}
                  aria-busy={isTarget || undefined}
                  aria-disabled={isNavigating && !isTarget ? true : undefined}
                  title={fav.href}
                >
                  <Icon name={icon} size={16} />
                  <span>{fav.label}</span>
                  {isTarget ? (
                    <span className="nav-spinner" aria-hidden style={{ marginLeft: 'auto' }} />
                  ) : (
                    <Icon
                      name="star"
                      size={12}
                      style={{ marginLeft: 'auto', color: 'var(--brand-orange)' }}
                    />
                  )}
                </div>
              );
            })}
          </nav>
        )}

        <nav className={`sidebar-nav${isNavigating ? ' is-navigating' : ''}`}>
          {visibleEntries.map((entry, i) => {
            if (isGroup(entry)) {
              return <div key={`g-${i}`} className="nav-group">{entry.group}</div>;
            }
            // Активным считаем только пункт с самым длинным матчащим href —
            // иначе родительский «/feed» подсвечивался бы вместе с дочерним
            // «/feed/shrinkage-profiles». Логика вычислена в activeHref выше.
            const active = entry.href === activeHref;
            const isTarget = isNavigating && targetPath === entry.href;
            return (
              <div
                key={entry.key}
                className={
                  'nav-item' +
                  (active ? ' active' : '') +
                  (isTarget ? ' loading' : '') +
                  (isNavigating && !isTarget ? ' disabled' : '')
                }
                onClick={() => go(entry.href)}
                aria-busy={isTarget || undefined}
                aria-disabled={isNavigating && !isTarget ? true : undefined}
              >
                <Icon name={entry.icon} size={16} />
                <span>{entry.label}</span>
                {isTarget ? (
                  <span className="nav-spinner" aria-hidden style={{ marginLeft: 'auto' }} />
                ) : (
                  entry.count != null && (
                    <span className="badge-count">{entry.count}</span>
                  )
                )}
              </div>
            );
          })}
        </nav>

        <div className={`sidebar-footer${isNavigating ? ' is-navigating' : ''}`}>
          {NAV_FOOTER.map((it) => {
            const isTarget = isNavigating && targetPath === it.href;
            const active = pathname === it.href;
            return (
              <div
                key={it.href}
                className={
                  'nav-item' +
                  (active ? ' active' : '') +
                  (isTarget ? ' loading' : '') +
                  (isNavigating && !isTarget ? ' disabled' : '')
                }
                onClick={() => go(it.href)}
                aria-busy={isTarget || undefined}
                aria-disabled={isNavigating && !isTarget ? true : undefined}
              >
                <Icon name={it.icon} size={16} />
                <span>{it.label}</span>
                {isTarget && <span className="nav-spinner" aria-hidden style={{ marginLeft: 'auto' }} />}
              </div>
            );
          })}
        </div>
      </aside>

      <OrgSelector open={orgPickerOpen} onClose={() => setOrgPickerOpen(false)} />
    </>
  );
}
