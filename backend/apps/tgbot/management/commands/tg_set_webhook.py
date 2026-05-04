"""
manage.py tg_set_webhook --url https://staging.erp.yembro.uz/api/tg/webhook/

Регистрирует webhook в Telegram + явно подписывает на нужные типы updates.

Главная причина существования: по дефолту BotFather / setWebhook без
параметра `allowed_updates` подписывает только на `message` —
**inline-кнопки (callback_query) в наш backend не приходят**, и любые
сообщения «вашу нажатую кнопку никто не обработал» происходят не из-за
бага в dispatcher, а потому что Telegram физически не шлёт нам этот
тип update.

После любого relaunch / перевыпуска токена нужно пере-выставлять.
В .env должны быть TELEGRAM_BOT_TOKEN и TELEGRAM_WEBHOOK_SECRET.
"""
from __future__ import annotations

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


# Минимально нужный набор: текстовые команды + inline-кнопки + редакции.
# Расширите если будете обрабатывать channel_post, inline_query и т.п.
DEFAULT_ALLOWED = ["message", "edited_message", "callback_query"]


class Command(BaseCommand):
    help = "Set Telegram webhook URL with the right allowed_updates list."

    def add_arguments(self, parser):
        parser.add_argument(
            "--url", required=True,
            help=(
                "Полный URL webhook'а, например "
                "https://staging.erp.yembro.uz/api/tg/webhook/"
            ),
        )
        parser.add_argument(
            "--drop-pending", action="store_true",
            help="Drop_pending_updates=true — выкинуть очередь зависших updates.",
        )

    def handle(self, *args, **opts):
        token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
        secret = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", "")
        if not token:
            raise CommandError("TELEGRAM_BOT_TOKEN не задан в settings/env.")

        payload = {
            "url": opts["url"],
            "allowed_updates": DEFAULT_ALLOWED,
        }
        if secret:
            payload["secret_token"] = secret
        if opts["drop_pending"]:
            payload["drop_pending_updates"] = True

        r = requests.post(
            f"https://api.telegram.org/bot{token}/setWebhook",
            json=payload, timeout=15,
        )
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if not r.ok or not data.get("ok"):
            raise CommandError(
                f"setWebhook failed: status={r.status_code} body={r.text[:300]}"
            )

        # Покажем итог + getWebhookInfo для подтверждения.
        info = requests.get(
            f"https://api.telegram.org/bot{token}/getWebhookInfo", timeout=10,
        ).json().get("result", {})
        self.stdout.write(self.style.SUCCESS(
            f"setWebhook → ok. URL: {info.get('url')}\n"
            f"  allowed_updates: {info.get('allowed_updates')}\n"
            f"  pending_update_count: {info.get('pending_update_count')}"
        ))
