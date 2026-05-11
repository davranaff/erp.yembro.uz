# yembro-catalog

Публичный SEO-каталог `yembro.uz` — отдельный Next.js проект.

## Стек

- Next.js 15 (App Router) + React 19
- Tailwind CSS 4 + дизайн-токены ERP
- next-intl для i18n (ru/uz/en)
- Tetra: SSG + ISR с revalidateTag
- JSON-LD (Organization, WebSite, Product, BreadcrumbList)
- Yandex.Metrica + GA4

## Локальный запуск

```bash
cp .env.example .env.local
# отредактируйте API_URL, SITE_URL, REVALIDATE_SECRET
npm install
npm run dev    # http://localhost:3001
```

Бэкенд должен крутиться на `NEXT_PUBLIC_API_URL`. По умолчанию ожидает
`http://localhost:8000/api/catalog/v1` (поправьте в `.env.local`).

## Build / Production

```bash
npm run build
npm start
```

Образ Docker — `Dockerfile`, multi-stage, output: `standalone`. Финальный
образ ~150мб. Слушает `:3001`.

## SEO-чеклист

- [x] hreflang на всех страницах для ru/uz/en
- [x] canonical
- [x] sitemap.xml — динамический, с alternates по 3 языкам
- [x] robots.txt — allow `/`, disallow `/api`, `/_next`
- [x] JSON-LD Organization + WebSite (с SearchAction) на всех страницах
- [x] JSON-LD Product + BreadcrumbList на карточке товара
- [x] generateMetadata с title (≤60), description (≤160), OG-image
- [x] ISR через revalidateTag с теговой инвалидацией из Django
- [x] next/image + remotePatterns для media.yembro.uz
- [x] next/font/google self-host Manrope + JetBrains Mono

## Структура URL

```
/                           → редирект на /ru
/ru                         → главная
/ru/catalog                 → все товары + фильтр по направлению
/ru/catalog/{categoryCode}  → категория
/ru/product/{productCode}   → карточка товара
/ru/brand/{brandCode}       → страница бренда
/ru/about                   → о компании (CMS)
/ru/contacts                → контакты + форма заявки
/ru/erp                     → лендинг "Арендовать ERP"
```

`{...code}` — стабильный технический код из бэкенда (не slug). Slug на
странице берётся из ответа API и используется только для вывода/SEO.

## ISR-ревалидация

Бэкенд при изменении контента POST'ит:

```
POST /api/revalidate
{ "secret": "...", "tags": ["product:starter-broiler", "sitemap"] }
```

`REVALIDATE_SECRET` в `.env.local` должен совпадать с
`CATALOG_REVALIDATE_SECRET` в backend `.env`.

Теги:
- `product:<code>` — карточка товара
- `category:<code>` — страница категории
- `brand:<code>` — страница бренда
- `page:<code>` — статичная CMS-страница
- `sitemap` — пересборка sitemap.xml
