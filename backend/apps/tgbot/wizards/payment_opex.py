"""
Wizard «Расход» — `/xarajat`.

Создаёт Payment(direction=OUT, kind=OPEX, status=POSTED).

Шаги:
  1. ARTICLE — выбор статьи расхода (поиск + пагинация)
  2. CHANNEL — cash / transfer
  3. CASH    — выбор cash_subaccount (касса/банк)
  4. AMOUNT  — сумма
  5. NOTES   — описание (свободный текст)
  6. CONFIRM → post_payment

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
    ARTICLE = "xarajat:article"
    CHANNEL = "xarajat:channel"
    CASH = "xarajat:cash"
    AMOUNT = "xarajat:amount"
    NOTES = "xarajat:notes"
    CONFIRM = "xarajat:confirm"


WIZARD_CODE = "payment_opex"


@command("/xarajat", help="Расход (касса / банк)", module="payments")
def start_opex(ctx: HandlerCtx) -> None:
    org = ctx.org()
    if org is None:
        send_message(ctx.chat_id, "Tashkilot tanlanmagan.")
        return
    if _articles_qs(org).count() == 0:
        send_message(ctx.chat_id, "❌ Нет статей расхода. Создайте в /settings.")
        return
    TgWizardSession.objects.update_or_create(
        chat_id=ctx.chat_id,
        defaults={
            "organization": org,
            "user": ctx.link.user if ctx.link else None,
            "wizard": WIZARD_CODE,
            "state": S.ARTICLE,
            "payload": {},
        },
    )
    session = TgWizardSession.objects.get(chat_id=ctx.chat_id)
    _render_articles(ctx, session, query="", page=0, edit=False)


def _articles_qs(org, query: str = ""):
    from apps.accounting.models import ExpenseArticle
    qs = ExpenseArticle.objects.filter(
        organization=org, is_active=True,
        kind=ExpenseArticle.Kind.EXPENSE,
    )
    q = (query or "").strip()
    if q:
        from django.db.models import Q
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))
    return qs.order_by("code")


def _cash_qs(org):
    from apps.accounting.models import GLSubaccount
    return GLSubaccount.objects.filter(
        account__organization=org,
        account__code__in=("50", "51"),
    ).select_related("account").order_by("code")


def _render_articles(ctx, session, *, query: str, page: int, edit: bool) -> None:
    qs = _articles_qs(session.organization, query)
    total = qs.count()
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    items = list(qs[page * PAGE_SIZE:(page + 1) * PAGE_SIZE])
    buttons = [
        (f"📑 {a.code} · {a.name[:30]}", f"wiz:xarajat:art:{a.id}")
        for a in items
    ]
    nav = []
    if page > 0:
        nav.append(("← Назад", f"wiz:xarajat:art:page:{page - 1}"))
    if page < pages - 1:
        nav.append(("Вперёд →", f"wiz:xarajat:art:page:{page + 1}"))
    if nav:
        buttons.extend(nav)
    if query:
        buttons.append(("🔄 Сбросить", "wiz:xarajat:art:clear"))
    buttons.append(("❌ Bekor", "wiz:xarajat:cancel"))
    session.advance(state=S.ARTICLE, payload_update={"art_query": query})
    msg = (
        "<b>💸 Расход · шаг 1/5</b>\n\n"
        + (f"🔎 Поиск: <code>{query}</code> · найдено {total}\n" if query else "")
        + f"Страница {page + 1}/{pages} (всего {total})\n\n"
        + "Выберите статью расхода или введите название/код:"
    )
    if edit and ctx.message_id:
        edit_message_text(ctx.chat_id, ctx.message_id, msg, reply_markup=kb(buttons, cols=1))
    else:
        send_message(ctx.chat_id, msg, reply_markup=kb(buttons, cols=1))


def on_article_callback(ctx, *, session, text):
    data = ctx.callback_data or ""
    if data == "wiz:xarajat:cancel":
        return _cancel(ctx, session)
    parts = data.split(":")
    if len(parts) >= 5 and parts[2] == "art" and parts[3] == "page":
        page = int(parts[4]) if parts[4].isdigit() else 0
        _render_articles(ctx, session, query=session.payload.get("art_query", ""), page=page, edit=True)
        return
    if len(parts) >= 4 and parts[2] == "art" and parts[3] == "clear":
        _render_articles(ctx, session, query="", page=0, edit=True)
        return
    if len(parts) != 4 or parts[2] != "art":
        return
    from apps.accounting.models import ExpenseArticle
    try:
        a = ExpenseArticle.objects.select_related("default_subaccount").get(
            id=parts[3], organization=session.organization,
        )
    except ExpenseArticle.DoesNotExist:
        return
    session.advance(state=S.CHANNEL, payload_update={
        "art_id": str(a.id), "art_name": a.name,
        "default_contra_id": str(a.default_subaccount_id) if a.default_subaccount_id else None,
    })
    edit_message_text(
        ctx.chat_id, ctx.message_id,
        f"<b>💸 Расход · шаг 2/5</b>\nСтатья: <b>{a.name}</b>\n\nКанал:",
        reply_markup=kb([
            ("💰 Наличные", "wiz:xarajat:ch:cash"),
            ("🏦 Перечисление", "wiz:xarajat:ch:transfer"),
            ("❌ Bekor", "wiz:xarajat:cancel"),
        ], cols=1),
    )


def on_article_text(ctx, *, session, text):
    _render_articles(ctx, session, query=(text or "").strip(), page=0, edit=False)


def on_channel_callback(ctx, *, session, text):
    data = ctx.callback_data or ""
    if data == "wiz:xarajat:cancel":
        return _cancel(ctx, session)
    parts = data.split(":")
    if len(parts) != 4 or parts[2] != "ch":
        return
    if parts[3] not in ("cash", "transfer"):
        return
    cashes = list(_cash_qs(session.organization))
    if not cashes:
        _cancel(ctx, session)
        send_message(ctx.chat_id, "❌ Нет настроенных касс / банков (счета 50/51).")
        return
    session.advance(state=S.CASH, payload_update={"channel": parts[3]})
    buttons = [(f"💼 {sub.code} · {sub.name[:30]}", f"wiz:xarajat:cash:{sub.id}") for sub in cashes[:8]]
    buttons.append(("❌ Bekor", "wiz:xarajat:cancel"))
    edit_message_text(
        ctx.chat_id, ctx.message_id,
        f"<b>💸 Расход · шаг 3/5</b>\nКанал: <code>{parts[3]}</code>\n\nИз какой кассы/счёта?",
        reply_markup=kb(buttons, cols=1),
    )


def on_cash_callback(ctx, *, session, text):
    data = ctx.callback_data or ""
    if data == "wiz:xarajat:cancel":
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
        f"<b>💸 Расход · шаг 4/5</b>\nКасса: <code>{sub.code} · {sub.name}</code>\n\nВведите сумму (сум):",
        reply_markup=kb([("❌ Bekor", "wiz:xarajat:cancel")], cols=1),
    )


def on_amount_text(ctx, *, session, text):
    amount = _parse_decimal(text)
    if amount is None or amount <= 0:
        send_message(ctx.chat_id, "⚠️ Введите положительную сумму.")
        return
    session.advance(state=S.NOTES, payload_update={"amount": str(amount)})
    send_message(
        ctx.chat_id,
        f"<b>💸 Расход · шаг 5/5</b>\nСумма: <code>{amount:,} сум</code>\n\nОпишите расход (мин 3 символа):".replace(",", " "),
        reply_markup=kb([("❌ Bekor", "wiz:xarajat:cancel")], cols=1),
    )


def on_notes_text(ctx, *, session, text):
    notes = (text or "").strip()
    if len(notes) < 3:
        send_message(ctx.chat_id, "⚠️ Минимум 3 символа.")
        return
    session.advance(state=S.CONFIRM, payload_update={"notes": notes[:500]})
    p = session.payload
    summary = (
        f"<b>💸 Расход · подтверждение</b>\n\n"
        f"Статья: <b>{p['art_name']}</b>\n"
        f"Канал: <code>{p['channel']}</code>\n"
        f"Касса: <code>{p['cash_code']} · {p['cash_name']}</code>\n"
        f"Сумма: <code>{Decimal(p['amount']):,} сум</code>\n"
        f"Заметка: <i>{p['notes']}</i>".replace(",", " ")
    )
    send_message(
        ctx.chat_id, summary,
        reply_markup=kb([
            ("✅ Провести", "wiz:xarajat:do"),
            ("❌ Bekor", "wiz:xarajat:cancel"),
        ], cols=2),
    )


def on_confirm(ctx, *, session, text):
    data = ctx.callback_data or ""
    if data == "wiz:xarajat:cancel":
        return _cancel(ctx, session)
    if data != "wiz:xarajat:do":
        return
    try:
        p = _create_and_post(session.payload, org=session.organization, user=session.user)
    except Exception as exc:  # noqa: BLE001
        logger.exception("payment_opex confirm failed")
        send_message(ctx.chat_id, f"❌ Не удалось провести: <code>{str(exc)[:300]}</code>")
        session.delete()
        return
    session.delete()
    edit_message_text(
        ctx.chat_id, ctx.message_id,
        f"✅ <b>Расход проведён</b>\n\nДокумент: <code>{p.doc_number}</code>",
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
            doc_number=next_doc_number(Payment, organization=org, prefix="РАС", on_date=today),
            date=today,
            direction=Payment.Direction.OUT,
            channel=payload["channel"],
            kind=Payment.Kind.OPEX,
            status=Payment.Status.DRAFT,
            cash_subaccount_id=payload["cash_id"],
            contra_subaccount_id=payload.get("default_contra_id"),
            expense_article_id=payload["art_id"],
            amount_uzs=Decimal(payload["amount"]),
            notes=payload.get("notes", ""),
        )
        post_payment(p, user=user)
    p.refresh_from_db()
    return p


register_wizard(WizardSpec(
    code=WIZARD_CODE,
    on_callback={
        S.ARTICLE: on_article_callback,
        S.CHANNEL: on_channel_callback,
        S.CASH: on_cash_callback,
        S.CONFIRM: on_confirm,
    },
    on_message={
        S.ARTICLE: on_article_text,
        S.AMOUNT: on_amount_text,
        S.NOTES: on_notes_text,
    },
))
