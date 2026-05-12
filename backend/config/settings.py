from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="change-me-in-production")
DEBUG = env.bool("DJANGO_DEBUG", default=True)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["*"])
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

BEHIND_TLS_PROXY = env.bool("DJANGO_BEHIND_TLS_PROXY", default=not DEBUG)
if BEHIND_TLS_PROXY:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

INSTALLED_APPS = [
    # modeltranslation должен идти ДО django.contrib.admin, иначе админка
    # не подхватит i18n-поля.
    "modeltranslation",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "corsheaders",
    "django_celery_beat",
    "django_celery_results",
    "mptt",
    "imagekit",
    "apps.common",
    "apps.users",
    "apps.organizations",
    "apps.modules",
    "apps.rbac",
    "apps.audit",
    "apps.currency",
    "apps.counterparties",
    "apps.accounting",
    "apps.nomenclature",
    "apps.warehouses",
    "apps.batches",
    "apps.transfers",
    "apps.purchases",
    "apps.feed",
    "apps.matochnik",
    "apps.incubation",
    "apps.feedlot",
    "apps.slaughter",
    "apps.vet",
    "apps.payments",
    "apps.holding",
    "apps.dashboard",
    "apps.sales",
    "apps.payroll",
    "apps.seeding",
    "apps.tgbot",
    "apps.landing",
    "apps.catalog",
    "apps.otp",
]

AUTH_USER_MODEL = "users.User"

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.common.middleware.OrganizationMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", default="erp"),
        "USER": env("POSTGRES_USER", default="erp"),
        "PASSWORD": env("POSTGRES_PASSWORD", default="erp"),
        "HOST": env("POSTGRES_HOST", default="db"),
        "PORT": env("POSTGRES_PORT", default="5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ru"
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True

# ── i18n каталога (django-modeltranslation) ───────────────────────────────
LANGUAGES = [
    ("ru", "Русский"),
    ("uz", "Oʻzbekcha"),
    ("en", "English"),
]
MODELTRANSLATION_DEFAULT_LANGUAGE = "ru"
MODELTRANSLATION_LANGUAGES = ("ru", "uz", "en")
MODELTRANSLATION_FALLBACK_LANGUAGES = {"default": ("ru",)}

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
# Override через env, потому что в проде /app/media — НЕ volume, и любой
# rebuild контейнера терял загруженные файлы. На проде ставим
# DJANGO_MEDIA_ROOT=/data/uploads — тот же volume что для покупок,
# переживает rebuild/redeploy.
MEDIA_ROOT = env.str("DJANGO_MEDIA_ROOT", default=str(BASE_DIR / "media"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:3000"],
)
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-organization-code",
]


# ─── DRF + JWT + OpenAPI ──────────────────────────────────────────────────
from datetime import timedelta  # noqa: E402

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": (
        "apps.common.pagination.FlexiblePageNumberPagination"
    ),
    "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Throttle scopes (rates указываются для конкретных классов через
    # `scope` атрибут на классе throttle). На каждый endpoint можно
    # навешать свой класс throttle, унаследованный от AnonRateThrottle/
    # UserRateThrottle, и задать ему rate в этом dict'е.
    "DEFAULT_THROTTLE_RATES": {
        "landing-demo": "5/min",
        "catalog-contact": "5/hour",
        # OTP: даём по 10 запросов кода с IP в минуту (внутри сервиса
        # ещё есть per-phone resend-cooldown через OTP_RESEND_INTERVAL_SECONDS).
        # Verify пускаем щедрее — пользователь может опечататься несколько раз,
        # счётчик попыток на конкретный код всё равно ограничивает подбор.
        "otp-request": "10/min",
        "otp-verify": "20/min",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Yembro ERP API",
    "DESCRIPTION": "ERP для птицеводческого предприятия",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://redis:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="django-db")
CELERY_CACHE_BACKEND = "django-cache"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True

# ── FX / валюты ─────────────────────────────────────────────────────────────
# Сколько дней назад get_rate_for() допустимо «откатываться» при отсутствии
# точного курса на дату документа (выходные, праздники CBU). Хардкод по
# умолчанию — 7 дней; повышайте через env, если ЦБ долго не публикует.
FX_FALLBACK_DAYS = env.int("FX_FALLBACK_DAYS", default=7)

# ── Telegram Bot ─────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", default="")
TELEGRAM_BOT_USERNAME = env("TELEGRAM_BOT_USERNAME", default="")
TELEGRAM_WEBHOOK_SECRET = env("TELEGRAM_WEBHOOK_SECRET", default="")

# ── Landing / Demo leads ──────────────────────────────────────────────────────
# Telegram chat_id через запятую — куда слать уведомления о новых заявках с лендинга
DEMO_NOTIFY_CHAT_IDS = env.str("DEMO_NOTIFY_CHAT_IDS", default="")

# ── Catalog (yembro.uz публичный сайт) ──────────────────────────────────────
# Куда стучаться для ISR-revalidation Next.js (catalog/) при изменениях контента.
CATALOG_FRONTEND_URL = env.str("CATALOG_FRONTEND_URL", default="https://yembro.uz")
CATALOG_REVALIDATE_SECRET = env.str("CATALOG_REVALIDATE_SECRET", default="")
# Базовый URL для absolute media-ссылок в публичном API каталога.
# Берётся вместо request.build_absolute_uri() — иначе при server-side fetch
# из Next.js (Host: prod-api:30000) URL получался бы внутренним и битым.
CATALOG_PUBLIC_MEDIA_BASE = env.str(
    "CATALOG_PUBLIC_MEDIA_BASE", default="https://api.erp.yembro.uz",
)
# Telegram chat_id через запятую для уведомлений о заявках с каталога.
# Если пусто — fallback на DEMO_NOTIFY_CHAT_IDS.
CATALOG_NOTIFY_CHAT_IDS = env.str("CATALOG_NOTIFY_CHAT_IDS", default="")

# ── Feed shrinkage ──────────────────────────────────────────────────────────
# Если True — при первой партии новой номенклатуры (или нового рецепта корма)
# автоматически создаётся дефолтный профиль усушки. Пользователь не настраивает
# вручную, но может подкрутить или деактивировать после.
FEED_AUTO_CREATE_SHRINKAGE_PROFILE = env.bool(
    "FEED_AUTO_CREATE_SHRINKAGE_PROFILE", default=True,
)

# ── Feedlot KPI-алерты ──────────────────────────────────────────────────────
# Пороги для ежедневной таски `apps.feedlot.kpi_alerts_task`. При превышении
# в TG уходит уведомление пользователям с feedlot-доступом.
FEEDLOT_MORTALITY_ALERT_PCT = env.float("FEEDLOT_MORTALITY_ALERT_PCT", default=5.0)
FEEDLOT_FCR_ALERT_VALUE = env.float("FEEDLOT_FCR_ALERT_VALUE", default=2.0)
FEEDLOT_FCR_ALERT_MIN_DAY = env.int("FEEDLOT_FCR_ALERT_MIN_DAY", default=14)

# ── Incubation KPI-алерты ───────────────────────────────────────────────────
# Hatch rate ниже этого % → TG-уведомление пользователям с incubation-доступом.
INCUBATION_HATCH_RATE_ALERT_PCT = env.float(
    "INCUBATION_HATCH_RATE_ALERT_PCT", default=80.0,
)
# На партиях меньше этого числа fertile_eggs не алертим — статистика шумная.
INCUBATION_MIN_FERTILE_FOR_ALERT = env.int(
    "INCUBATION_MIN_FERTILE_FOR_ALERT", default=100,
)

# ── OTP / SMS (Eskiz) ───────────────────────────────────────────────────────
# Креды личного кабинета Eskiz (notify.eskiz.uz). При пустых значениях боевая
# отправка SMS невозможна — endpoint вернёт 503. Для локальной разработки
# включите OTP_DEV_PRINT=true: код будет писаться в лог.
ESKIZ_BASE_URL = env.str("ESKIZ_BASE_URL", default="https://notify.eskiz.uz")
ESKIZ_EMAIL = env.str("ESKIZ_EMAIL", default="")
ESKIZ_PASSWORD = env.str("ESKIZ_PASSWORD", default="")
# Sender ID / alpha-name. По умолчанию тестовый "4546" — он работает только
# с прошитым тестовым текстом "Bu Eskiz dan test". Для прода в кабинете
# Eskiz регистрируется свой alpha-name (напр. YEMBRO) и подставляется сюда.
ESKIZ_FROM = env.str("ESKIZ_FROM", default="4546")
ESKIZ_TIMEOUT_SECONDS = env.float("ESKIZ_TIMEOUT_SECONDS", default=10.0)
# Опциональный публичный URL, на который Eskiz пришлёт статус доставки
# каждого SMS. Полезно для прода (увидеть delivered/failed без поллинга).
# Пока endpoint /api/otp/callback/ не реализован — оставляем пустым и
# просто доверяем синхронному ответу send_sms.
ESKIZ_CALLBACK_URL = env.str("ESKIZ_CALLBACK_URL", default="")

# Длина и время жизни кода. 6 цифр × 5 минут — стандарт.
OTP_CODE_LENGTH = env.int("OTP_CODE_LENGTH", default=6)
OTP_TTL_SECONDS = env.int("OTP_TTL_SECONDS", default=300)
OTP_MAX_ATTEMPTS = env.int("OTP_MAX_ATTEMPTS", default=5)
# Сколько секунд между повторными запросами кода для одного телефона+purpose.
OTP_RESEND_INTERVAL_SECONDS = env.int("OTP_RESEND_INTERVAL_SECONDS", default=60)
# Шаблон сообщения. {code} подставляется. Текст должен быть предварительно
# согласован в кабинете Eskiz, иначе провайдер откажет (кроме sender 4546
# + текста "Bu Eskiz dan test" — тестовый режим).
OTP_MESSAGE_TEMPLATE = env.str(
    "OTP_MESSAGE_TEMPLATE",
    default="Bu Eskiz dan test",
)
# Можно ли клиенту присылать свой текст SMS (через поле message_template
# в /api/otp/request/). По умолчанию выключено — иначе наш endpoint
# превращается в spam-шлюз для произвольных текстов.
OTP_ALLOW_CLIENT_TEMPLATE = env.bool("OTP_ALLOW_CLIENT_TEMPLATE", default=False)
# В DEBUG по умолчанию шлём не в Eskiz, а в лог — чтобы не тратить SMS
# на дев-сборках. На проде должен быть False.
OTP_DEV_PRINT = env.bool("OTP_DEV_PRINT", default=DEBUG)

# ── Matochnik KPI-алерты ────────────────────────────────────────────────────
# Средняя яйценоскость за неделю ниже этого % → TG-алерт.
MATOCHNIK_LOW_PRODUCTIVITY_ALERT_PCT = env.float(
    "MATOCHNIK_LOW_PRODUCTIVITY_ALERT_PCT", default=50.0,
)
# Недельный падёж выше этого % от current_heads → TG-алерт.
MATOCHNIK_MORTALITY_ALERT_PCT_WEEK = env.float(
    "MATOCHNIK_MORTALITY_ALERT_PCT_WEEK", default=1.0,
)
# Стада младше этого возраста не алертим по продуктивности (ещё не несут).
MATOCHNIK_PRODUCTIVITY_MIN_AGE_WEEKS = env.int(
    "MATOCHNIK_PRODUCTIVITY_MIN_AGE_WEEKS", default=22,
)

