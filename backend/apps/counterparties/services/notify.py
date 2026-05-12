"""
Уведомления контрагентов: SMS-напоминание о долге, приглашение в TG-бот.

Точка сборки логики, чтобы view не разрастался:
  - текущий долг берётся из `sales.services.credit_check.check_customer_credit`,
  - SMS уходит через `apps.otp.send_sms` (журналируется в SmsMessage),
  - TG уходит через `apps.tgbot.bot.send_message` (журналируется в TgMessage),
  - приглашение в TG генерит `TgLinkToken` и шлёт SMS с deep-link'ом.

Текст SMS — на узбекском (latin script), так как кириллицу Eskiz считает как
2 байта на символ → стоимость в 3× выше. Латиница укладывается в стандартные
GSM-7, 160 chars в одном SMS.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.utils import timezone

from apps.otp.models import SmsMessage
from apps.otp.services import normalize_phone, send_sms
from apps.otp.services.eskiz import EskizError
from apps.otp.services.phone import PhoneError
from apps.tgbot.bot import send_message as tg_send_message
from apps.tgbot.models import TgLink, TgLinkToken, TgMessage

logger = logging.getLogger(__name__)


@dataclass
class ChannelResult:
    channel: str  # 'sms' | 'tg'
    ok: bool
    detail: str = ""  # error message or provider id
    record_id: Optional[str] = None  # SmsMessage.id или TgMessage.id


@dataclass
class NotifyResult:
    results: list[ChannelResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "results": [
                {
                    "channel": r.channel,
                    "ok": r.ok,
                    "detail": r.detail,
                    "record_id": r.record_id,
                }
                for r in self.results
            ],
            "any_ok": any(r.ok for r in self.results),
        }


# ── Тексты ─────────────────────────────────────────────────────────────────

def _fmt_uzs(amount: Decimal) -> str:
    """1234567.50 → '1 234 567'."""
    try:
        n = int(amount)
    except (TypeError, ValueError):
        return str(amount)
    s = f"{n:,}".replace(",", " ")
    return s


def _build_debt_sms_text(*, customer_name: str, debt_uzs: Decimal) -> str:
    """SMS-напоминание о долге, латиница (UZB)."""
    short_name = (customer_name or "").strip()[:30]
    return (
        f"Hurmatli {short_name}, sizning qarzingiz: "
        f"{_fmt_uzs(debt_uzs)} so'm. "
        "Iltimos, to'lov amalga oshiring. YemBro"
    )


def _build_tg_invite_sms_text(*, customer_name: str, deep_link: str) -> str:
    """SMS-приглашение в Telegram-бот, латиница (UZB)."""
    return (
        f"Salom! YemBro siz uchun Telegram-bot tayyorlab qo'ydi. "
        "Yangi xabarlar va eslatmalarni Telegram orqali olishingiz mumkin. "
        f"Botni ishga tushiring: {deep_link} "
        "(havola 30 daqiqa amal qiladi)."
    )


def _build_debt_tg_text(*, customer_name: str, debt_uzs: Decimal) -> str:
    """TG-напоминание (HTML, рендерим bold). Тут можем себе позволить русский."""
    return (
        f"💰 <b>Напоминание о долге</b>\n\n"
        f"Уважаемый <b>{customer_name}</b>, ваш текущий долг:\n"
        f"<b>{_fmt_uzs(debt_uzs)} сум</b>\n\n"
        f"Пожалуйста, погасите задолженность."
    )


# ── Долг ────────────────────────────────────────────────────────────────────

def _get_current_debt(counterparty, organization) -> Decimal:
    """Текущий долг клиента из aging-отчёта.

    Не используем check_customer_credit — у него fast-path с 0 если у
    клиента не задан credit_limit/max_overdue, что для большинства клиентов
    как раз и есть. Aging честно считает по непогашенным SaleOrder
    (включая синтетический OPENING_BALANCE).
    """
    from apps.sales.services.aging import compute_aging_report
    report = compute_aging_report(organization, customer_id=str(counterparty.id))
    if not report.rows:
        return Decimal("0")
    return Decimal(report.rows[0].total)


# ── notify_counterparty_debt ────────────────────────────────────────────────

def notify_counterparty_debt(
    *,
    counterparty,
    organization,
    channels: list[str],
    sender_user=None,
) -> NotifyResult:
    """
    Шлёт уведомление о текущем долге через выбранные каналы.

    channels: подмножество ['sms', 'tg']. Если в БД нет phone или
    TgLink — соответствующий канал отказывает с понятным detail'ом, но не
    выбрасывает исключение наверх — UI должен видеть статус по каждому каналу.
    """
    result = NotifyResult()
    debt = _get_current_debt(counterparty, organization)

    if debt <= 0:
        for ch in channels:
            result.results.append(ChannelResult(
                channel=ch, ok=False,
                detail="У клиента нет текущей задолженности.",
            ))
        return result

    if "sms" in channels:
        result.results.append(_send_debt_sms(
            counterparty=counterparty, debt=debt, sender_user=sender_user,
        ))
    if "tg" in channels:
        result.results.append(_send_debt_tg(
            counterparty=counterparty, organization=organization,
            debt=debt, sender_user=sender_user,
        ))
    return result


def _send_debt_sms(*, counterparty, debt, sender_user) -> ChannelResult:
    if not counterparty.phone:
        return ChannelResult(
            channel="sms", ok=False, detail="У контрагента не указан телефон.",
        )
    try:
        phone = normalize_phone(counterparty.phone)
    except PhoneError as exc:
        return ChannelResult(channel="sms", ok=False, detail=str(exc))

    text = _build_debt_sms_text(
        customer_name=counterparty.name, debt_uzs=debt,
    )
    try:
        sms = send_sms(
            phone=phone, message=text,
            source=SmsMessage.Source.NOTIFY,
            purpose="debt_reminder",
            created_by=sender_user,
        )
    except EskizError as exc:
        return ChannelResult(channel="sms", ok=False, detail=str(exc)[:200])
    return ChannelResult(
        channel="sms", ok=True,
        detail=f"SMS отправлено (provider_id={sms.provider_message_id})",
        record_id=str(sms.id),
    )


def _send_debt_tg(*, counterparty, organization, debt, sender_user) -> ChannelResult:
    link = (
        TgLink.objects
        .filter(counterparty=counterparty, organization=organization, is_active=True)
        .first()
    )
    if not link:
        return ChannelResult(
            channel="tg", ok=False,
            detail="Клиент не привязан к Telegram-боту. "
                   "Сначала отправьте приглашение «Пригласить в TG».",
        )
    text = _build_debt_tg_text(
        customer_name=counterparty.name, debt_uzs=debt,
    )
    now = timezone.now()
    msg = TgMessage.objects.create(
        organization=organization,
        chat_id=link.chat_id,
        counterparty=counterparty,
        text=text,
        source=TgMessage.Source.DEBT_REMINDER,
        status=TgMessage.Status.SENT,
        sent_at=now,
        created_by=sender_user,
    )
    if not tg_send_message(link.chat_id, text):
        msg.status = TgMessage.Status.FAILED
        msg.failed_at = now
        msg.sent_at = None
        msg.error_msg = "Telegram API вернул ошибку (см. логи)."
        msg.save(update_fields=[
            "status", "failed_at", "sent_at", "error_msg", "updated_at",
        ])
        return ChannelResult(
            channel="tg", ok=False,
            detail="Telegram не доставил — возможно бот удалён из чата.",
            record_id=str(msg.id),
        )
    return ChannelResult(
        channel="tg", ok=True,
        detail=f"TG доставлено (chat_id={link.chat_id})",
        record_id=str(msg.id),
    )


# ── invite_counterparty_to_tg ────────────────────────────────────────────────

def invite_counterparty_to_tg(
    *,
    counterparty,
    organization,
    sender_user=None,
) -> ChannelResult:
    """
    Генерирует TgLinkToken, формирует deep-link `https://t.me/<bot>?start=<token>`,
    отправляет SMS на номер контрагента с приглашением (узбекская латиница).
    """
    if not counterparty.phone:
        return ChannelResult(
            channel="sms", ok=False, detail="У контрагента не указан телефон.",
        )
    try:
        phone = normalize_phone(counterparty.phone)
    except PhoneError as exc:
        return ChannelResult(channel="sms", ok=False, detail=str(exc))

    bot_username = getattr(settings, "TELEGRAM_BOT_USERNAME", "") or ""
    if not bot_username:
        return ChannelResult(
            channel="sms", ok=False,
            detail="TELEGRAM_BOT_USERNAME не настроен.",
        )

    # Чистим возможный @-префикс.
    bot_username = bot_username.lstrip("@")
    token = TgLinkToken.objects.create(
        organization=organization, counterparty=counterparty,
    )
    deep_link = f"https://t.me/{bot_username}?start={token.token}"
    text = _build_tg_invite_sms_text(
        customer_name=counterparty.name, deep_link=deep_link,
    )

    try:
        sms = send_sms(
            phone=phone, message=text,
            source=SmsMessage.Source.NOTIFY,
            purpose="tg_invite",
            created_by=sender_user,
        )
    except EskizError as exc:
        return ChannelResult(channel="sms", ok=False, detail=str(exc)[:200])

    return ChannelResult(
        channel="sms", ok=True,
        detail=f"SMS-приглашение отправлено (token={token.token[:8]}…)",
        record_id=str(sms.id),
    )
