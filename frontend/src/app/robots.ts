import type { MetadataRoute } from 'next';

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || 'https://erp.yembro.uz';

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: '*',
        // Маркетинговый landing открыт для индексации; остальное — закрыто
        // (приложение под авторизацией, нет смысла индексировать).
        allow: ['/'],
        disallow: [
          '/login',
          '/dashboard',
          '/admin',
          '/api',
          '/scan',
          '/print',
          // Все маршруты внутри /(app) после login. Префикс /app не используется,
          // но конкретные маршруты — закрываем перечислением:
          '/sales',
          '/purchases',
          '/transfers',
          '/feed',
          '/feedlot',
          '/incubation',
          '/matochnik',
          '/slaughter',
          '/vet',
          '/stock',
          '/finance',
          '/ledger',
          '/reports',
          '/counterparties',
          '/nomenclature',
          '/people',
          '/roles',
          '/blocks',
          '/accounts',
          '/audit-log',
          '/holding',
          '/settings',
          '/profile',
          '/tasks',
          '/traceability',
        ],
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
