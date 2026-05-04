FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.settings

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# collectstatic at build time so static is bundled in the image.
# Pass a dummy SECRET_KEY because settings.py requires it.
RUN DJANGO_SECRET_KEY=build-only-key \
    DJANGO_DEBUG=False \
    DJANGO_ALLOWED_HOSTS=* \
    POSTGRES_HOST=localhost \
    python manage.py collectstatic --noinput || echo "collectstatic skipped (static dirs missing — non-fatal)"

EXPOSE 30000

# Default command runs Gunicorn on port 30000 (matches compose.base.yml + Caddyfile).
# `migrate` service in compose runs migrations separately.
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:30000", "--workers", "3", "--access-logfile", "-", "--error-logfile", "-"]
