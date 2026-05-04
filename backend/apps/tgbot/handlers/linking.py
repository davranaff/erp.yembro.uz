"""
/start <token> и /link <token> — привязка ERP-аккаунта к Telegram-чату.

Особый случай: handler работает БЕЗ привязанного TgLink (юзер только что начал
общение с ботом). Регистрируется в dispatcher хардкодом, не через @command.
"""
from __future__ import annotations

import logging

from ..bot import send_message
from ..dispatcher import HandlerCtx
from ..keyboards import kb

logger = logging.getLogger(__name__)


def handle_link(ctx: HandlerCtx, *, tg_user: dict) -> None:
    from ..models import TgLink, TgLinkToken

    token_str = ctx.args[0].strip() if ctx.args else ""
    if not token_str:
        send_message(
            ctx.chat_id,
            "👋 Привет! Чтобы привязать аккаунт, получите токен в ERP:\n"
            "Настройки → Telegram → «Подключить Telegram»\n\n"
            "Затем отправьте: <code>/link ВАШ_ТОКЕН</code>",
        )
        return

    try:
        link_token = TgLinkToken.objects.select_related(
            "organization", "user", "counterparty",
        ).get(token=token_str)
    except TgLinkToken.DoesNotExist:
        send_message(ctx.chat_id, "❌ Токен не найден. Запросите новый в ERP.")
        return

    if not link_token.is_valid:
        send_message(
            ctx.chat_id,
            "⏰ Токен истёк или уже использован. Запросите новый в ERP.",
        )
        return

    tg_username = tg_user.get("username", "")

    TgLink.objects.update_or_create(
        organization=link_token.organization,
        chat_id=ctx.chat_id,
        defaults={
            "user": link_token.user,
            "counterparty": link_token.counterparty,
            "tg_username": tg_username,
            "is_active": True,
        },
    )
    link_token.used = True
    link_token.save(update_fields=["used"])

    who = link_token.user or link_token.counterparty
    name = getattr(who, "get_full_name", None)
    if callable(name):
        name = name() or getattr(who, "email", str(who))
    else:
        name = getattr(who, "name", str(who))

    send_message(
        ctx.chat_id,
        f"✅ <b>Аккаунт привязан!</b>\n\n"
        f"👤 {name}\n"
        f"🏢 Организация: {link_token.organization}\n",
        reply_markup=kb([
            ("📋 Открыть меню", "home"),
        ], cols=1),
    )
