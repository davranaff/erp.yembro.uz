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

    link, _ = TgLink.objects.update_or_create(
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

    # Персональный список / команд для этого чата (RBAC-aware для админ-линка,
    # клиент-набор для counterparty). Telegram сразу спрячет недоступные
    # команды в popup'е, юзер не увидит /pnl если он клиент и т.п.
    try:
        from ..bot import set_my_commands
        from ..services.menu_scope import (
            commands_for_counterparty,
            commands_for_user,
            user_module_levels,
        )
        if link.user_id:
            commands = commands_for_user(user_module_levels(link))
        else:
            commands = commands_for_counterparty()
        set_my_commands(commands, chat_id=ctx.chat_id)
    except Exception:  # noqa: BLE001
        logger.warning("setMyCommands failed for chat %s", ctx.chat_id, exc_info=True)

    send_message(
        ctx.chat_id,
        f"✅ <b>Akkaunt bog'landi!</b>\n\n"
        f"👤 {name}\n"
        f"🏢 Tashkilot: {link_token.organization}\n",
        reply_markup=kb([
            ("📋 Menyuni ochish", "home"),
        ], cols=1),
    )
