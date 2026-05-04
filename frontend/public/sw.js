/**
 * Простой Service Worker без зависимостей.
 *
 * Стратегия:
 *  - HTML-страницы (`navigate`): network-first, fallback на /offline.html
 *  - Статика (_next/static, иконки, manifest): cache-first
 *  - API-запросы (/api/...): не кэшируем — пусть apiFetch + offlineQueue
 *    решают что делать (мутации идут в IDB-очередь, GET'ы просто падают
 *    с сетевой ошибкой → React Query покажет старые данные из своего кэша)
 *
 * Для production — рекомендуется next-pwa или Workbox. Этот SW —
 * минимальный фундамент, чтобы оператор не видел «нет интернета» от
 * браузера, а получил нормальную offline-страницу с инструкцией.
 */

const CACHE_VERSION = 'yembro-v1';
const STATIC_ASSETS = [
  '/offline.html',
  '/manifest.webmanifest',
];

// Install: предзагружаем offline-страницу
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => cache.addAll(STATIC_ASSETS)),
  );
  self.skipWaiting();
});

// Activate: чистим старые версии кэша
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k !== CACHE_VERSION)
          .map((k) => caches.delete(k)),
      ),
    ),
  );
  self.clients.claim();
});

// Fetch
self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Кросс-доменные запросы (например на API backend на другом порту) — не трогаем
  if (url.origin !== self.location.origin) return;

  // API → пропускаем без кэша. apiFetch + offlineQueue сами разберутся.
  if (url.pathname.startsWith('/api/')) return;

  // HTML-страницы — network-first с fallback
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req).catch(() =>
        caches.match('/offline.html', { ignoreSearch: true })
          .then((r) => r || new Response('Offline', { status: 503 })),
      ),
    );
    return;
  }

  // Статика и всё остальное — cache-first с обновлением фона
  if (req.method === 'GET') {
    event.respondWith(
      caches.match(req).then((cached) => {
        const networkPromise = fetch(req).then((res) => {
          // Кэшируем только успешные ответы
          if (res.ok && res.type === 'basic') {
            const clone = res.clone();
            caches.open(CACHE_VERSION).then((c) => c.put(req, clone));
          }
          return res;
        }).catch(() => null);
        return cached || networkPromise || fetch(req);
      }),
    );
  }
});
