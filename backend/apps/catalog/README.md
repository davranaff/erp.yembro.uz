# apps/catalog — публичный каталог yembro.uz

Публичный SEO-ориентированный каталог: бренд, товары, статичные страницы.
Полностью изолирован от ERP-операционки. Контент ведётся вручную через
Django admin в трёх языках (ru/uz/en).

## Установка зависимостей

После добавления приложения нужно установить три новых пакета:

```bash
pip install -r requirements.txt   # django-modeltranslation, django-mptt, django-imagekit
```

## Создание миграций

`django-modeltranslation` автоматически добавляет языковые поля
(`name_ru`, `name_uz`, `name_en` и т.д.). После регистрации app:

```bash
python manage.py makemigrations catalog
python manage.py migrate
```

`makemigrations` сгенерирует одну initial-миграцию со всеми i18n-полями
сразу — потому что `translation.py` загружается в момент `app.ready()`.

## Заполнение демо-данными (для разработки фронта)

```bash
python manage.py seed_catalog
```

Создаст: бренд Yembro, 6 категорий, 8 товаров со спецификациями, 6 страниц.
Идемпотентно — повторный запуск обновит существующие записи по `code`.

## Конфиг (env)

```
CATALOG_FRONTEND_URL=https://yembro.uz
CATALOG_REVALIDATE_SECRET=<любой длинный секрет>
CATALOG_NOTIFY_CHAT_IDS=123,456    # необязательно; fallback на DEMO_NOTIFY_CHAT_IDS
```

## Public API

Префикс: `/api/catalog/v1/`. Все эндпоинты — `AllowAny`.
Lang-резолюшен: `?lang=ru|uz|en` → `Accept-Language` → `ru`.

| Метод | URL | Назначение |
|---|---|---|
| GET | `brands/` | список активных брендов |
| GET | `brands/<code>/` | бренд + featured products |
| GET | `categories/` | плоское дерево (level/lft/rght/tree_id) |
| GET | `categories/<code>/` | категория + breadcrumbs + потомки |
| GET | `products/` | пагинированный список + фильтры |
| GET | `products/<code>/` | карточка с spec + images + related |
| GET | `pages/<code>/` | статичная страница |
| POST | `contact/` | заявка (throttle 5/час по IP) |
| GET | `sitemap/` | плоский JSON всех URL для генерации sitemap.xml |

`<code>` — стабильный технический ключ. Локализованный `slug` отдаётся в
ответе, фронт сам строит `/{lang}/product/{slug}` URL.

## ISR-ревалидация

При post_save/post_delete на Brand/Category/Product/CatalogPage
`signals.py` дёргает celery-task `revalidate_next_task`, которая
POST'ит `https://yembro.uz/api/revalidate` с тегами:
- `product:<code>`, `category:<code>`, `brand:<code>`, `page:<code>`
- всегда добавляется `sitemap`

Next.js принимает запрос, проверяет `CATALOG_REVALIDATE_SECRET` и
вызывает `revalidateTag(...)` для каждого.
