# Деплой публичного каталога yembro.uz

Каталог-сайт `yembro.uz` — отдельный Next.js-сервис в монорепо
(`catalog/`). Бэкендом служит то же Django-приложение, что и для ERP
(`backend/apps/catalog/`), доступное по `api.erp.yembro.uz/api/catalog/`.

Этот документ описывает: что уже зашито в репозиторий, что нужно
настроить руками, как пушить релизы и как делать первичный запуск на
бойцовском сервере.

---

## 1. Архитектура контейнеров

```
                   ┌─────────────────────────┐
   yembro.uz ─────▶│  prod-catalog (Next.js) │ — публичный сайт
www.yembro.uz ─────▶  redirect → yembro.uz   │
                   └────────────┬────────────┘
                                │  /api/catalog/v1/*
                                ▼
   erp.yembro.uz ────▶┌─────────────────────────┐
api.erp.yembro.uz ───▶│  prod-api (Django)      │ — backend (общий)
                      └────────────┬────────────┘
                                   │
                          ┌────────┴────────┐
                          ▼                 ▼
                       postgres          redis
                                            ▲
                                            │
                                     prod-worker (celery)
```

Caddy на edge-хосте слушает все эти домены — конфиг лежит в
[deploy/caddy/Caddyfile](../deploy/caddy/Caddyfile).

---

## 2. Что уже подготовлено в репо

- **Backend** `backend/apps/catalog/` — модели, public API
  (`/api/catalog/v1/`), Django admin, Celery-задачи, миграция
  `0001_initial`, seed-команда `manage.py seed_catalog`.
- **Frontend** `catalog/` — Next.js 15 с i18n (ru/uz/en), SSG/ISR,
  splash-screen, scroll-progress, JSON-LD, sitemap.xml, robots.txt.
- **Docker** — сервис `catalog` в `compose.base.yml` и алиасы
  `prod-catalog` / `staging-catalog` в `compose.prod.yml` / `.staging.yml`.
- **Caddy** — блоки для `yembro.uz` (apex), `www.yembro.uz` (301-redirect)
  и `staging.yembro.uz` (с `X-Robots-Tag: noindex`).
- **Env** — переменные в `.envs/.env.prod`, `.env.staging`, `.env.edge`.
  Секреты `CATALOG_REVALIDATE_SECRET` уже сгенерированы (`openssl rand
  -hex 32`).

---

## 3. Что нужно настроить руками **до** первого деплоя

### 3.1 DNS

В DNS-зоне `yembro.uz` создать **A-записи** на IP бойцовского сервера:

| Тип | Имя             | Куда           |
|-----|-----------------|----------------|
| A   | `@` (apex)      | `<SERVER_IP>`  |
| A   | `www`           | `<SERVER_IP>`  |
| A   | `staging`       | `<SERVER_IP>`  |

**Важно:** apex (`@`) должен быть именно A-записью. CNAME на apex многие
DNS-провайдеры запрещают.

Поддомены `erp.yembro.uz`, `api.erp.yembro.uz`, `staging.erp.yembro.uz`,
`registry.erp.yembro.uz` — уже должны быть настроены (там работает ERP).

### 3.2 Telegram-уведомления (опционально)

В `.envs/.env.prod` строка `CATALOG_NOTIFY_CHAT_IDS=` пустая. Если хочешь
получать пуши о заявках с формы каталога в отдельный Telegram-чат —
впиши chat_id (через запятую). Если оставить пустым — заявки уйдут на
`DEMO_NOTIFY_CHAT_IDS`.

### 3.3 Аналитика (опционально)

`CATALOG_YM_ID=` (Yandex.Metrica counter) и `CATALOG_GA_ID=` (Google
Analytics 4 measurement ID) — пустые. Когда заведёшь счётчики — впиши
значения, **не нужно ребилдить** контейнер: значения подставляются в
HTML на этапе SSR из переменных окружения.

> Внимание: для смены `NEXT_PUBLIC_*` переменных нужен restart
> контейнера `catalog`. Они инлайнятся в client-bundle на этапе старта.

### 3.4 Регистрация в поисковиках

После того как сайт открыт по https:

1. **Google Search Console** — добавить property `yembro.uz`
   (Domain-property, проверка через DNS TXT).
2. **Yandex.Webmaster** — добавить сайт `yembro.uz`, проверка через
   DNS TXT.
3. В обоих сервисах — sumbit sitemap: `https://yembro.uz/sitemap.xml`.

---

## 4. Сборка и пуш образов в registry

В корне репо:

```bash
# 1. Собрать catalog-образ под прод-тег
docker build -t registry.erp.yembro.uz/yembro/catalog:production ./catalog

# 2. Залогиниться в registry (учётка лежит в .envs/.registry.credentials)
docker login registry.erp.yembro.uz

# 3. Запушить
docker push registry.erp.yembro.uz/yembro/catalog:production
```

Backend и frontend ERP пересобирать не нужно — их образы уже в registry,
а изменения в `apps/catalog/` подтянутся при следующем релизе backend
(или сразу — если делаешь `docker compose pull && up` сейчас).

---

## 5. Запуск на бойцовском сервере (первый раз)

```bash
# 0. Убедиться что .envs/.env.prod и .env.edge на сервере актуальны
#    (синкаем git pull или scp)

# 1. Подтянуть новые образы
cd /opt/yembro
docker compose --env-file .envs/.env.prod \
  -f compose.base.yml -f compose.prod.yml pull api catalog

# 2. Применить миграции backend (для apps.catalog)
docker compose --env-file .envs/.env.prod \
  -f compose.base.yml -f compose.prod.yml run --rm api \
  python manage.py migrate

# 3. Заполнить каталог seed-данными (только при первом запуске)
docker compose --env-file .envs/.env.prod \
  -f compose.base.yml -f compose.prod.yml run --rm api \
  python manage.py seed_catalog

# 4. Поднять backend и catalog
docker compose --env-file .envs/.env.prod \
  -f compose.base.yml -f compose.prod.yml up -d api worker scheduler catalog

# 5. Перечитать конфиг Caddy на edge (новые домены yembro.uz)
docker compose --env-file .envs/.env.edge -f compose.edge.yml \
  exec proxy caddy reload --config /etc/caddy/Caddyfile
```

Caddy сам выпустит TLS-сертификаты для `yembro.uz`, `www.yembro.uz`,
`staging.yembro.uz` через Let's Encrypt при первом запросе.

---

## 6. Регулярные релизы

```bash
# на dev-машине
git pull
docker build -t registry.erp.yembro.uz/yembro/catalog:production ./catalog
docker push registry.erp.yembro.uz/yembro/catalog:production

# на бойцовском сервере
cd /opt/yembro
git pull
docker compose --env-file .envs/.env.prod \
  -f compose.base.yml -f compose.prod.yml pull catalog
docker compose --env-file .envs/.env.prod \
  -f compose.base.yml -f compose.prod.yml up -d --no-deps catalog
```

Если правились **модели backend** или **Caddyfile** — нужно ещё:

```bash
# миграции
docker compose ... run --rm api python manage.py migrate
docker compose ... up -d --no-deps api worker scheduler

# Caddy reload
docker compose --env-file .envs/.env.edge -f compose.edge.yml \
  exec proxy caddy reload --config /etc/caddy/Caddyfile
```

---

## 7. Контент-операции (через Django admin)

`https://api.erp.yembro.uz/admin/catalog/`

- **Brands** — три бренда (yembro / yembro-pro / yembro-bio)
- **Categories** — MPTT-дерево, можно перетаскивать
- **Products** — карточки + spec + изображения inline
- **Pages** — about / contacts / erp / faq / quality / delivery / partners
- **Contact requests** — заявки с формы

Все текстовые поля имеют табы `RU | UZ | EN`. Slug в каждом языке свой
(можно сделать `boshlangich-broyler-yemi` для uz и `broiler-starter-feed`
для en — будут разные URL'ы в каждом языке).

После сохранения изменений Django сигналы автоматически дёрнут
`POST https://yembro.uz/api/revalidate` и Next.js перевыпустит HTML
изменённой страницы. **Не нужно ничего ребилдить вручную.**

---

## 8. Проверка после деплоя

```bash
# Все эндпоинты должны быть 200
curl -I https://yembro.uz/                              # 307 → /ru
curl -I https://yembro.uz/ru                            # 200
curl -I https://yembro.uz/ru/catalog                    # 200
curl -I https://yembro.uz/ru/product/starter-broiler-23 # 200
curl -I https://yembro.uz/sitemap.xml                   # 200
curl -I https://yembro.uz/robots.txt                    # 200

# www должен редиректить на apex
curl -I https://www.yembro.uz/                          # 301 → https://yembro.uz/

# API каталога должен работать
curl https://api.erp.yembro.uz/api/catalog/v1/products/?lang=uz | head

# Sitemap содержит все товары + категории + бренды × 3 языка
curl -s https://yembro.uz/sitemap.xml | grep -c '<loc>'  # должно быть >100
```

В Google Search Console через 1-3 дня после первого пуша sitemap'а
появятся проиндексированные URL'ы. Yandex.Webmaster — то же самое
(индексация быстрее в RU/UZ-сегменте).

---

## 9. Откат (rollback)

```bash
# Если новая сборка catalog сломала прод
docker tag registry.erp.yembro.uz/yembro/catalog:production-N-1 \
          registry.erp.yembro.uz/yembro/catalog:production
docker push registry.erp.yembro.uz/yembro/catalog:production
docker compose ... up -d --no-deps catalog
```

> Совет: на каждый успешный релиз пуши также именованный тег
> `production-YYYYMMDD-HHMM`, чтобы было куда откатываться.

---

## 10. Где живут конфиги

| Что | Путь |
|---|---|
| Прод env | [.envs/.env.prod](../.envs/.env.prod) |
| Staging env | [.envs/.env.staging](../.envs/.env.staging) |
| Edge env | [.envs/.env.edge](../.envs/.env.edge) |
| Caddy | [deploy/caddy/Caddyfile](../deploy/caddy/Caddyfile) |
| Compose base | [compose.base.yml](../compose.base.yml) |
| Compose prod | [compose.prod.yml](../compose.prod.yml) |
| Compose edge | [compose.edge.yml](../compose.edge.yml) |
| Catalog Dockerfile | [catalog/Dockerfile](../catalog/Dockerfile) |
| Catalog README | [catalog/README.md](../catalog/README.md) |
| Backend app README | [backend/apps/catalog/README.md](../backend/apps/catalog/README.md) |

---

## 11. Чеклист на день запуска

- [ ] DNS: A-записи `yembro.uz`, `www.yembro.uz`, `staging.yembro.uz` смотрят на сервер
- [ ] `.envs/.env.prod`: `CATALOG_REVALIDATE_SECRET` уникальный (готов)
- [ ] `.envs/.env.prod`: `CATALOG_NOTIFY_CHAT_IDS` заполнен (или оставлен на DEMO_NOTIFY_CHAT_IDS)
- [ ] `.envs/.env.prod`: `CATALOG_YM_ID` и `CATALOG_GA_ID` (если используются)
- [ ] Образ `registry.erp.yembro.uz/yembro/catalog:production` запушен
- [ ] Образ backend пересобран (содержит `apps.catalog`)
- [ ] Миграции применены (`apps.catalog.0001_initial`)
- [ ] `seed_catalog` выполнен или контент введён вручную через admin
- [ ] Caddy перезагружен и видит новые блоки
- [ ] HTTPS-сертификаты выпустились (логи: `docker compose -f compose.edge.yml logs proxy`)
- [ ] Smoke-тесты из §8 пройдены
- [ ] Google Search Console и Yandex.Webmaster подключены, sitemap отправлен
