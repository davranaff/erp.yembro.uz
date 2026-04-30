from __future__ import annotations

import logging

from .bot import send_message
from .notifications import fmt_cashflow, fmt_production, fmt_report, fmt_stock

logger = logging.getLogger(__name__)

HELP_TEXT = (
    "🤖 <b>Yembro ERP Bot</b>\n\n"
    "Доступные команды:\n"
    "/report — финансовый отчёт за месяц\n"
    "/balance — остатки кассы и банка\n"
    "/cashflow — кэш-флоу за 30 дней\n"
    "/production — поголовье и партии\n"
    "/help — список команд"
)


def dispatch(update: dict) -> None:
    msg = update.get("message") or update.get("edited_message") or {}
    chat_id = msg.get("chat", {}).get("id")
    text = (msg.get("text") or "").strip()
    tg_user = msg.get("from", {})

    if not chat_id or not text:
        return

    if text.startswith("/start") or text.startswith("/link"):
        _handle_link(chat_id, text, tg_user)
        return

    link = _get_admin_link(chat_id)
    if link is None:
        send_message(
            chat_id,
            "❌ Нет доступа.\n\nПривяжите аккаунт в ERP: Настройки → Telegram.",
        )
        return

    org = link.organization
    if text == "/report":
        if not _has_module_access(link, "reports"):
            send_message(chat_id, "⛔ Нет доступа к модулю <b>Отчёты</b>.")
            return
        _handle_report(chat_id, org)
    elif text == "/balance" or text == "/stock":
        # /stock — устаревший alias, остаётся для совместимости со старыми
        # пользователями. Семантически команда про остатки касс/банка → finance,
        # поэтому требуем доступ к модулю «Отчёты», а не к складу/проводкам.
        if not _has_module_access(link, "reports"):
            send_message(chat_id, "⛔ Нет доступа к модулю <b>Отчёты</b>.")
            return
        _handle_stock(chat_id, org)
    elif text == "/cashflow":
        if not _has_module_access(link, "reports"):
            send_message(chat_id, "⛔ Нет доступа к модулю <b>Отчёты</b>.")
            return
        _handle_cashflow(chat_id, org)
    elif text == "/production":
        if not _has_module_access(link, "feedlot"):
            send_message(chat_id, "⛔ Нет доступа к модулю <b>Производство</b>.")
            return
        _handle_production(chat_id, org)
    else:
        send_message(chat_id, HELP_TEXT)


def _get_admin_link(chat_id: int):
    from .models import TgLink
    return TgLink.objects.filter(
        chat_id=chat_id, is_active=True, user__isnull=False
    ).select_related("organization", "user").first()


def _has_module_access(link, module_code: str) -> bool:
    """Проверяет, есть ли у пользователя link доступ >= 'r' к модулю."""
    from apps.common.permissions import _effective_level, level_satisfies
    from apps.organizations.models import OrganizationMembership

    membership = OrganizationMembership.objects.filter(
        organization=link.organization,
        user=link.user,
    ).first()
    if membership is None:
        return False
    return level_satisfies(_effective_level(membership, module_code), "r")


def _handle_link(chat_id: int, text: str, tg_user: dict) -> None:
    from .models import TgLink, TgLinkToken

    parts = text.split(maxsplit=1)
    token_str = parts[1].strip() if len(parts) > 1 else ""

    if not token_str:
        send_message(
            chat_id,
            "👋 Привет! Чтобы привязать аккаунт, получите токен в ERP:\n"
            "Настройки → Telegram → «Подключить Telegram»\n\n"
            "Затем отправьте: <code>/link ВАШ_ТОКЕН</code>",
        )
        return

    try:
        link_token = TgLinkToken.objects.select_related(
            "organization", "user", "counterparty"
        ).get(token=token_str)
    except TgLinkToken.DoesNotExist:
        send_message(chat_id, "❌ Токен не найден. Запросите новый в ERP.")
        return

    if not link_token.is_valid:
        send_message(chat_id, "⏰ Токен истёк или уже использован. Запросите новый в ERP.")
        return

    tg_username = tg_user.get("username", "")

    TgLink.objects.update_or_create(
        organization=link_token.organization,
        chat_id=chat_id,
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
        chat_id,
        f"✅ <b>Аккаунт привязан!</b>\n\n"
        f"👤 {name}\n"
        f"🏢 Организация: {link_token.organization}\n\n"
        f"Отправьте /help чтобы увидеть доступные команды.",
    )


def _handle_report(chat_id: int, org) -> None:
    from apps.dashboard.services import kpi_summary
    try:
        kpis = kpi_summary(org)
        send_message(chat_id, fmt_report(kpis))
    except Exception as exc:
        logger.error("report error: %s", exc)
        send_message(chat_id, "⚠️ Не удалось получить отчёт. Попробуйте позже.")


def _handle_stock(chat_id: int, org) -> None:
    from apps.dashboard.services import cash_balances
    try:
        cash = cash_balances(org)
        send_message(chat_id, fmt_stock(cash))
    except Exception as exc:
        logger.error("stock error: %s", exc)
        send_message(chat_id, "⚠️ Не удалось получить остатки.")


def _handle_cashflow(chat_id: int, org) -> None:
    from apps.dashboard.services import cashflow_chart
    try:
        points = cashflow_chart(org, days=30)
        send_message(chat_id, fmt_cashflow(points, 30))
    except Exception as exc:
        logger.error("cashflow error: %s", exc)
        send_message(chat_id, "⚠️ Не удалось получить кэш-флоу.")


def _handle_production(chat_id: int, org) -> None:
    from apps.dashboard.services import production_summary
    try:
        prod = production_summary(org)
        send_message(chat_id, fmt_production(prod))
    except Exception as exc:
        logger.error("production error: %s", exc)
        send_message(chat_id, "⚠️ Не удалось получить данные производства.")
