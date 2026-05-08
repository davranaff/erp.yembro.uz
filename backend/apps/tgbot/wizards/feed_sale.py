"""
Wizard «Продажа мешка корма» — `/sotuv`.

Шаги:
  1. BAG_LOT — выбор FeedBagLot (active, bags_remaining > 0). Поиск + пагинация.
  2. CUSTOMER — выбор покупателя (Counterparty kind=buyer). Поиск + пагинация.
  3. QTY — кол-во мешков (≤ bags_remaining).
  4. PRICE — цена за 1 мешок (UZS).
  5. CONFIRM → SaleOrder + SaleItem(feed_bag_lot=..., qty=шт) → confirm_sale.

RBAC: module="sales".
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
    BAG_LOT = "sale:bag"
    CUSTOMER = "sale:customer"
    QTY = "sale:qty"
    PRICE = "sale:price"
    CONFIRM = "sale:confirm"


WIZARD_CODE = "feed_sale"


@command("/sotuv", help="Продажа корма (мешками)", module="sales")
def start_sale(ctx: HandlerCtx) -> None:
    org = ctx.org()
    if org is None:
        send_message(ctx.chat_id, "Tashkilot tanlanmagan.")
        return
    if _bag_lots_qs(org).count() == 0:
        send_message(ctx.chat_id, "❌ Нет партий мешков на продажу.")
        return
    TgWizardSession.objects.update_or_create(
        chat_id=ctx.chat_id,
        defaults={
            "organization": org,
            "user": ctx.link.user if ctx.link else None,
            "wizard": WIZARD_CODE,
            "state": S.BAG_LOT,
            "payload": {},
        },
    )
    session = TgWizardSession.objects.get(chat_id=ctx.chat_id)
    _render_bags(ctx, session, query="", page=0, edit=False)


# ─── Querysets ────────────────────────────────────────────────────────────


def _bag_lots_qs(org, query: str = ""):
    from apps.feed.models import FeedBagLot
    qs = FeedBagLot.objects.filter(
        organization=org, status=FeedBagLot.Status.ACTIVE, bags_remaining__gt=0,
    ).select_related("recipe_version__recipe", "storage_warehouse")
    q = (query or "").strip()
    if q:
        from django.db.models import Q
        qs = qs.filter(
            Q(doc_number__icontains=q)
            | Q(recipe_version__recipe__code__icontains=q)
            | Q(recipe_version__recipe__name__icontains=q),
        )
    return qs.order_by("-packaged_at")


def _buyers_qs(org, query: str = ""):
    from apps.counterparties.models import Counterparty
    qs = Counterparty.objects.filter(
        organization=org, is_active=True,
        kind__in=[Counterparty.Kind.BUYER, Counterparty.Kind.OTHER],
    )
    q = (query or "").strip()
    if q:
        from django.db.models import Q
        qs = qs.filter(
            Q(name__icontains=q) | Q(code__icontains=q) | Q(phone__icontains=q),
        )
    return qs.order_by("-created_at")


# ─── Render ────────────────────────────────────────────────────────────────


def _render_bags(ctx, session, *, query: str, page: int, edit: bool) -> None:
    qs = _bag_lots_qs(session.organization, query)
    total = qs.count()
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    items = list(qs[page * PAGE_SIZE:(page + 1) * PAGE_SIZE])
    buttons = []
    for fb in items:
        rcode = fb.recipe_version.recipe.code if fb.recipe_version_id else "?"
        kg = fb.bags_remaining * Decimal(fb.bag_weight_kg)
        buttons.append((
            f"📦 {rcode} · {fb.bags_remaining}шт · {kg:g}кг",
            f"wiz:sale:bag:{fb.id}",
        ))
    nav = []
    if page > 0:
        nav.append(("← Назад", f"wiz:sale:bag:page:{page - 1}"))
    if page < pages - 1:
        nav.append(("Вперёд →", f"wiz:sale:bag:page:{page + 1}"))
    if nav:
        buttons.extend(nav)
    if query:
        buttons.append(("🔄 Сбросить поиск", "wiz:sale:bag:clear"))
    buttons.append(("❌ Bekor", "wiz:sale:cancel"))
    session.advance(state=S.BAG_LOT, payload_update={"bag_query": query})
    msg = (
        "<b>💰 Продажа · шаг 1/4</b>\n\n"
        + (f"🔎 Поиск: <code>{query}</code> · найдено {total}\n" if query else "")
        + f"Страница {page + 1}/{pages} (всего {total})\n\n"
        + "Выберите партию мешков или введите рецепт/документ для поиска:"
    )
    if edit and ctx.message_id:
        edit_message_text(ctx.chat_id, ctx.message_id, msg, reply_markup=kb(buttons, cols=1))
    else:
        send_message(ctx.chat_id, msg, reply_markup=kb(buttons, cols=1))


def _render_customers(ctx, session, *, query: str, page: int, edit: bool) -> None:
    qs = _buyers_qs(session.organization, query)
    total = qs.count()
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    items = list(qs[page * PAGE_SIZE:(page + 1) * PAGE_SIZE])
    buttons = [
        (f"👤 {c.code} · {c.name[:30]}", f"wiz:sale:cust:{c.id}")
        for c in items
    ]
    nav = []
    if page > 0:
        nav.append(("← Назад", f"wiz:sale:cust:page:{page - 1}"))
    if page < pages - 1:
        nav.append(("Вперёд →", f"wiz:sale:cust:page:{page + 1}"))
    if nav:
        buttons.extend(nav)
    if query:
        buttons.append(("🔄 Сбросить поиск", "wiz:sale:cust:clear"))
    buttons.append(("❌ Bekor", "wiz:sale:cancel"))
    session.advance(state=S.CUSTOMER, payload_update={"cust_query": query})
    p = session.payload
    msg = (
        f"<b>💰 Продажа · шаг 2/4</b>\n"
        f"Партия: <code>{p.get('bag_doc')}</code> · {p.get('bag_recipe')}\n\n"
        + (f"🔎 Поиск: <code>{query}</code> · найдено {total}\n" if query else "")
        + f"Страница {page + 1}/{pages} (всего {total})\n\n"
        + "Выберите покупателя или введите имя/телефон для поиска:"
    )
    if edit and ctx.message_id:
        edit_message_text(ctx.chat_id, ctx.message_id, msg, reply_markup=kb(buttons, cols=1))
    else:
        send_message(ctx.chat_id, msg, reply_markup=kb(buttons, cols=1))


# ─── Step handlers ────────────────────────────────────────────────────────


def on_bag_callback(ctx: HandlerCtx, *, session: TgWizardSession, text: str | None) -> None:
    data = ctx.callback_data or ""
    if data == "wiz:sale:cancel":
        return _cancel(ctx, session)
    parts = data.split(":")
    if len(parts) >= 5 and parts[2] == "bag" and parts[3] == "page":
        try:
            page = int(parts[4])
        except ValueError:
            page = 0
        _render_bags(ctx, session, query=session.payload.get("bag_query", ""), page=page, edit=True)
        return
    if len(parts) >= 4 and parts[2] == "bag" and parts[3] == "clear":
        _render_bags(ctx, session, query="", page=0, edit=True)
        return
    if len(parts) != 4 or parts[2] != "bag":
        return
    bag_id = parts[3]
    from apps.feed.models import FeedBagLot
    try:
        fb = FeedBagLot.objects.select_related("recipe_version__recipe").get(
            id=bag_id, organization=session.organization,
        )
    except FeedBagLot.DoesNotExist:
        send_message(ctx.chat_id, "⚠️ Партия не найдена.")
        return
    rcode = fb.recipe_version.recipe.code if fb.recipe_version_id else "?"
    session.advance(
        state=S.CUSTOMER,
        payload_update={
            "bag_id": str(fb.id),
            "bag_doc": fb.doc_number,
            "bag_recipe": rcode,
            "bag_weight_kg": str(fb.bag_weight_kg),
            "bags_remaining": str(fb.bags_remaining),
            "warehouse_id": str(fb.storage_warehouse_id) if fb.storage_warehouse_id else None,
            "module_id": str(fb.module_id),
        },
    )
    _render_customers(ctx, session, query="", page=0, edit=True)


def on_bag_text(ctx: HandlerCtx, *, session: TgWizardSession, text: str | None) -> None:
    _render_bags(ctx, session, query=(text or "").strip(), page=0, edit=False)


def on_customer_callback(ctx: HandlerCtx, *, session: TgWizardSession, text: str | None) -> None:
    data = ctx.callback_data or ""
    if data == "wiz:sale:cancel":
        return _cancel(ctx, session)
    parts = data.split(":")
    if len(parts) >= 5 and parts[2] == "cust" and parts[3] == "page":
        try:
            page = int(parts[4])
        except ValueError:
            page = 0
        _render_customers(ctx, session, query=session.payload.get("cust_query", ""), page=page, edit=True)
        return
    if len(parts) >= 4 and parts[2] == "cust" and parts[3] == "clear":
        _render_customers(ctx, session, query="", page=0, edit=True)
        return
    if len(parts) != 4 or parts[2] != "cust":
        return
    cust_id = parts[3]
    from apps.counterparties.models import Counterparty
    try:
        c = Counterparty.objects.get(id=cust_id, organization=session.organization, is_active=True)
    except Counterparty.DoesNotExist:
        send_message(ctx.chat_id, "⚠️ Клиент не найден.")
        return
    session.advance(
        state=S.QTY,
        payload_update={"cust_id": str(c.id), "cust_name": c.name},
    )
    p = session.payload
    edit_message_text(
        ctx.chat_id, ctx.message_id,
        (
            f"<b>💰 Продажа · шаг 3/4</b>\n"
            f"Партия: <code>{p['bag_doc']}</code> · {p['bag_recipe']}\n"
            f"Клиент: <b>{c.name}</b>\n"
            f"Доступно: <code>{p['bags_remaining']} шт × {p['bag_weight_kg']} кг</code>\n\n"
            f"Введите количество мешков:"
        ),
        reply_markup=kb([("❌ Bekor", "wiz:sale:cancel")], cols=1),
    )


def on_customer_text(ctx: HandlerCtx, *, session: TgWizardSession, text: str | None) -> None:
    _render_customers(ctx, session, query=(text or "").strip(), page=0, edit=False)


def on_qty_text(ctx: HandlerCtx, *, session: TgWizardSession, text: str | None) -> None:
    qty = _parse_int(text)
    if qty is None or qty <= 0:
        send_message(ctx.chat_id, "⚠️ Введите целое число > 0.")
        return
    available = int(Decimal(session.payload["bags_remaining"]))
    if qty > available:
        send_message(ctx.chat_id, f"⚠️ Доступно только {available} шт.")
        return
    session.advance(state=S.PRICE, payload_update={"qty": str(qty)})
    p = session.payload
    send_message(
        ctx.chat_id,
        (
            f"<b>💰 Продажа · шаг 4/4</b>\n"
            f"Количество: <code>{qty} мешков × {p['bag_weight_kg']} кг</code>\n\n"
            f"Введите цену за 1 мешок (сум):"
        ),
        reply_markup=kb([("❌ Bekor", "wiz:sale:cancel")], cols=1),
    )


def on_price_text(ctx: HandlerCtx, *, session: TgWizardSession, text: str | None) -> None:
    price = _parse_decimal(text)
    if price is None or price <= 0:
        send_message(ctx.chat_id, "⚠️ Введите положительное число.")
        return
    qty = Decimal(session.payload["qty"])
    total = (qty * price).quantize(Decimal("0.01"))
    session.advance(state=S.CONFIRM, payload_update={"price": str(price), "total": str(total)})
    p = session.payload
    summary = (
        f"<b>💰 Продажа · подтверждение</b>\n\n"
        f"Партия: <code>{p['bag_doc']}</code> · {p['bag_recipe']}\n"
        f"Клиент: <b>{p['cust_name']}</b>\n"
        f"Кол-во: <code>{qty} мешков ({(qty * Decimal(p['bag_weight_kg'])):g} кг)</code>\n"
        f"Цена/мешок: <code>{price:,} сум</code>\n"
        f"<b>Сумма: <code>{total:,} сум</code></b>".replace(",", " ")
    )
    send_message(
        ctx.chat_id, summary,
        reply_markup=kb([
            ("✅ Провести", "wiz:sale:do"),
            ("❌ Bekor", "wiz:sale:cancel"),
        ], cols=2),
    )


def on_confirm(ctx: HandlerCtx, *, session: TgWizardSession, text: str | None) -> None:
    data = ctx.callback_data or ""
    if data == "wiz:sale:cancel":
        return _cancel(ctx, session)
    if data != "wiz:sale:do":
        return
    try:
        order = _create_and_confirm(session.payload, org=session.organization, user=session.user)
    except Exception as exc:  # noqa: BLE001
        logger.exception("feed_sale wizard confirm failed")
        send_message(ctx.chat_id, f"❌ Не удалось провести продажу: <code>{str(exc)[:300]}</code>")
        session.delete()
        return
    session.delete()
    edit_message_text(
        ctx.chat_id, ctx.message_id,
        (
            f"✅ <b>Продажа проведена</b>\n\n"
            f"Документ: <code>{order.doc_number}</code>\n"
            f"Сумма: <code>{order.amount_uzs:,} сум</code>".replace(",", " ")
        ),
    )


# ─── Helpers ────────────────────────────────────────────────────────────


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


def _parse_int(s):
    d = _parse_decimal(s)
    if d is None:
        return None
    try:
        return int(d)
    except (TypeError, ValueError):
        return None


def _create_and_confirm(payload, *, org, user):
    from django.db import transaction
    from apps.common.services.numbering import next_doc_number
    from apps.feed.models import FeedBagLot
    from apps.modules.models import Module
    from apps.nomenclature.models import NomenclatureItem
    from apps.sales.models import SaleItem, SaleOrder
    from apps.sales.services.confirm import confirm_sale
    today = timezone.localdate()
    bag = FeedBagLot.objects.select_related("recipe_version__recipe").get(id=payload["bag_id"])
    # nomenclature готового корма (sku == recipe.code)
    nom = NomenclatureItem.objects.get(
        organization=org, sku=bag.recipe_version.recipe.code,
    )
    module = Module.objects.get(id=payload["module_id"]) if payload.get("module_id") else bag.module
    with transaction.atomic():
        order = SaleOrder.objects.create(
            organization=org,
            module=module,
            doc_number=next_doc_number(SaleOrder, organization=org, prefix="ПР", on_date=today),
            date=today,
            customer_id=payload["cust_id"],
            warehouse_id=payload.get("warehouse_id"),
            status=SaleOrder.Status.DRAFT,
            currency=None,
            notes="Создано через Telegram-бот",
        )
        SaleItem.objects.create(
            order=order,
            nomenclature=nom,
            feed_bag_lot=bag,
            quantity=Decimal(payload["qty"]),
            unit_price_uzs=Decimal(payload["price"]),
        )
        confirm_sale(order, user=user)
    order.refresh_from_db()
    return order


register_wizard(WizardSpec(
    code=WIZARD_CODE,
    on_callback={
        S.BAG_LOT: on_bag_callback,
        S.CUSTOMER: on_customer_callback,
        S.CONFIRM: on_confirm,
    },
    on_message={
        S.BAG_LOT: on_bag_text,
        S.CUSTOMER: on_customer_text,
        S.QTY: on_qty_text,
        S.PRICE: on_price_text,
    },
))
