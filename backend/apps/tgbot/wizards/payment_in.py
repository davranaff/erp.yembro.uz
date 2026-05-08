"""
Wizard «Поступление от клиента» — `/tolov`.

Создаёт Payment(direction=IN, kind=COUNTERPARTY, status=POSTED).

Шаги:
  1. CUSTOMER — выбор клиента (поиск + пагинация)
  2. CHANNEL  — cash / transfer / click
  3. CASH     — выбор cash_subaccount (касса/банк)
  4. AMOUNT   — сумма (UZS)
  5. CONFIRM  → post_payment

RBAC: module="payments".
"""
from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from ..bot import edit_message_text, send_message
from ..dispatcher import HandlerCtx, command
from ..keyboards import kb
from ..models import TgWizardSession
from . import WizardSpec, register_wizard

logger = logging.getLogger(__name__)
PAGE_SIZE = 8


class S:
    CUSTOMER = "tolov:customer"
    CHANNEL = "tolov:channel"
    CASH = "tolov:cash"
    AMOUNT = "tolov:amount"
    CONFIRM = "tolov:confirm"


WIZARD_CODE = "payment_in"


@command("/tolov", help="Поступление от клиента", module="payments")
def start_payment_in(ctx: HandlerCtx) -> None:
    org = ctx.org()
    if org is None:
        send_message(ctx.chat_id, "Tashkilot tanlanmagan.")
        return
    TgWizardSession.objects.update_or_create(
        chat_id=ctx.chat_id,
        defaults={
            "organization": org,
            "user": ctx.link.user if ctx.link else None,
            "wizard": WIZARD_CODE,
            "state": S.CUSTOMER,
            "payload": {},
        },
    )
    session = TgWizardSession.objects.get(chat_id=ctx.chat_id)
    _render_customers(ctx, session, query="", page=0, edit=False)


def _customers_qs(org, query: str = ""):
    from apps.counterparties.models import Counterparty
    qs = Counterparty.objects.filter(organization=org, is_active=True)
    q = (query or "").strip()
    if q:
        from django.db.models import Q
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q) | Q(phone__icontains=q))
    return qs.order_by("-created_at")


def _cash_qs(org):
    from apps.accounting.models import GLSubaccount
    # Кассы и банки — корневые счета 50 и 51 в плане счетов.
    return GLSubaccount.objects.filter(
        account__organization=org,
        account__code__in=("50", "51"),
    ).select_related("account").order_by("code")


def _render_customers(ctx, session, *, query: str, page: int, edit: bool) -> None:
    qs = _customers_qs(session.organization, query)
    total = qs.count()
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    items = list(qs[page * PAGE_SIZE:(page + 1) * PAGE_SIZE])
    buttons = [
        (f"👤 {c.code} · {c.name[:30]}", f"wiz:tolov:cust:{c.id}")
        for c in items
    ]
    nav = []
    if page > 0:
        nav.append(("← Назад", f"wiz:tolov:cust:page:{page - 1}"))
    if page < pages - 1:
        nav.append(("Вперёд →", f"wiz:tolov:cust:page:{page + 1}"))
    if nav:
        buttons.extend(nav)
    if query:
        buttons.append(("🔄 Сбросить", "wiz:tolov:cust:clear"))
    buttons.append(("❌ Bekor", "wiz:tolov:cancel"))
    session.advance(state=S.CUSTOMER, payload_update={"cust_query": query})
    msg = (
        "<b>💵 Поступление · шаг 1/4</b>\n\n"
        + (f"🔎 Поиск: <code>{query}</code> · найдено {total}\n" if query else "")
        + f"Страница {page + 1}/{pages} (всего {total})\n\nВыберите клиента:"
    )
    if edit and ctx.message_id:
        edit_message_text(ctx.chat_id, ctx.message_id, msg, reply_markup=kb(buttons, cols=1))
    else:
        send_message(ctx.chat_id, msg, reply_markup=kb(buttons, cols=1))


def on_customer_callback(ctx, *, session, text):
    data = ctx.callback_data or ""
    if data == "wiz:tolov:cancel":
        return _cancel(ctx, session)
    parts = data.split(":")
    if len(parts) >= 5 and parts[2] == "cust" and parts[3] == "page":
        page = int(parts[4]) if parts[4].isdigit() else 0
        _render_customers(ctx, session, query=session.payload.get("cust_query", ""), page=page, edit=True)
        return
    if len(parts) >= 4 and parts[2] == "cust" and parts[3] == "clear":
        _render_customers(ctx, session, query="", page=0, edit=True)
        return
    if len(parts) != 4 or parts[2] != "cust":
        return
    from apps.counterparties.models import Counterparty
    try:
        c = Counterparty.objects.get(id=parts[3], organization=session.organization)
    except Counterparty.DoesNotExist:
        send_message(ctx.chat_id, "⚠️ Клиент не найден.")
        return
    session.advance(state=S.CHANNEL, payload_update={"cust_id": str(c.id), "cust_name": c.name})
    edit_message_text(
        ctx.chat_id, ctx.message_id,
        f"<b>💵 Поступление · шаг 2/4</b>\nКлиент: <b>{c.name}</b>\n\nВыберите канал:",
        reply_markup=kb([
            ("💰 Наличные", "wiz:tolov:ch:cash"),
            ("🏦 Перечисление", "wiz:tolov:ch:transfer"),
            ("📱 Click", "wiz:tolov:ch:click"),
            ("❌ Bekor", "wiz:tolov:cancel"),
        ], cols=1),
    )


def on_customer_text(ctx, *, session, text):
    _render_customers(ctx, session, query=(text or "").strip(), page=0, edit=False)


def on_channel_callback(ctx, *, session, text):
    data = ctx.callback_data or ""
    if data == "wiz:tolov:cancel":
        return _cancel(ctx, session)
    parts = data.split(":")
    if len(parts) != 4 or parts[2] != "ch":
        return
    channel = parts[3]
    if channel not in ("cash", "transfer", "click"):
        return
    cashes = list(_cash_qs(session.organization))
    if not cashes:
        _cancel(ctx, session)
        send_message(ctx.chat_id, "❌ Нет настроенных касс / банков (счета 50/51).")
        return
    session.advance(state=S.CASH, payload_update={"channel": channel})
    buttons = [(f"💼 {sub.code} · {sub.name[:30]}", f"wiz:tolov:cash:{sub.id}") for sub in cashes[:8]]
    buttons.append(("❌ Bekor", "wiz:tolov:cancel"))
    edit_message_text(
        ctx.chat_id, ctx.message_id,
        f"<b>💵 Поступление · шаг 3/4</b>\nКанал: <code>{channel}</code>\n\nВ какую кассу/счёт зачисляем?",
        reply_markup=kb(buttons, cols=1),
    )


def on_cash_callback(ctx, *, session, text):
    data = ctx.callback_data or ""
    if data == "wiz:tolov:cancel":
        return _cancel(ctx, session)
    parts = data.split(":")
    if len(parts) != 4 or parts[2] != "cash":
        return
    from apps.accounting.models import GLSubaccount
    try:
        sub = GLSubaccount.objects.select_related("account").get(
            id=parts[3], account__organization=session.organization,
        )
    except GLSubaccount.DoesNotExist:
        return
    session.advance(state=S.AMOUNT, payload_update={"cash_id": str(sub.id), "cash_code": sub.code, "cash_name": sub.name})
    edit_message_text(
        ctx.chat_id, ctx.message_id,
        (
            f"<b>💵 Поступление · шаг 4/4</b>\n"
            f"Касса/счёт: <code>{sub.code} · {sub.name}</code>\n\n"
            f"Введите сумму (сум):"
        ),
        reply_markup=kb([("❌ Bekor", "wiz:tolov:cancel")], cols=1),
    )


def on_amount_text(ctx, *, session, text):
    amount = _parse_decimal(text)
    if amount is None or amount <= 0:
        send_message(ctx.chat_id, "⚠️ Введите положительную сумму.")
        return
    session.advance(state=S.CONFIRM, payload_update={"amount": str(amount)})
    p = session.payload
    summary = (
        f"<b>💵 Поступление · подтверждение</b>\n\n"
        f"Клиент: <b>{p['cust_name']}</b>\n"
        f"Канал: <code>{p['channel']}</code>\n"
        f"Касса: <code>{p['cash_code']} · {p['cash_name']}</code>\n"
        f"<b>Сумма: <code>{amount:,} сум</code></b>".replace(",", " ")
    )
    send_message(
        ctx.chat_id, summary,
        reply_markup=kb([
            ("✅ Провести", "wiz:tolov:do"),
            ("❌ Bekor", "wiz:tolov:cancel"),
        ], cols=2),
    )


def on_confirm(ctx, *, session, text):
    data = ctx.callback_data or ""
    if data == "wiz:tolov:cancel":
        return _cancel(ctx, session)
    if data != "wiz:tolov:do":
        return
    try:
        payment = _create_and_post(session.payload, org=session.organization, user=session.user)
    except Exception as exc:  # noqa: BLE001
        logger.exception("payment_in confirm failed")
        send_message(ctx.chat_id, f"❌ Не удалось провести: <code>{str(exc)[:300]}</code>")
        session.delete()
        return
    session.delete()
    edit_message_text(
        ctx.chat_id, ctx.message_id,
        f"✅ <b>Платёж проведён</b>\n\nДокумент: <code>{payment.doc_number}</code>",
    )


def _cancel(ctx, session):
    session.delete()
    edit_message_text(ctx.chat_id, ctx.message_id, "❌ Отменено.")


def _parse_decimal(s):
    if not s:
        return None
    s = s.strip().replace(",", ".").replace(" ", "")
    if not s:
        return None
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def _create_and_post(payload, *, org, user):
    from django.db import transaction
    from apps.common.services.numbering import next_doc_number
    from apps.payments.models import Payment
    from apps.payments.services.post import post_payment
    today = timezone.localdate()
    with transaction.atomic():
        p = Payment.objects.create(
            organization=org,
            doc_number=next_doc_number(Payment, organization=org, prefix="ПЛТ", on_date=today),
            date=today,
            direction=Payment.Direction.IN,
            channel=payload["channel"],
            kind=Payment.Kind.COUNTERPARTY,
            status=Payment.Status.DRAFT,
            counterparty_id=payload["cust_id"],
            cash_subaccount_id=payload["cash_id"],
            amount_uzs=Decimal(payload["amount"]),
            notes="Создано через Telegram-бот",
        )
        post_payment(p, user=user)
    p.refresh_from_db()
    return p


register_wizard(WizardSpec(
    code=WIZARD_CODE,
    on_callback={
        S.CUSTOMER: on_customer_callback,
        S.CHANNEL: on_channel_callback,
        S.CASH: on_cash_callback,
        S.CONFIRM: on_confirm,
    },
    on_message={
        S.CUSTOMER: on_customer_text,
        S.AMOUNT: on_amount_text,
    },
))
