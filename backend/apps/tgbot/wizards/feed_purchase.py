"""
Wizard «Приход в склад feed» — закупка с поставщиком через `confirm_purchase`.

Шаги:
  1. WAREHOUSE — выбор склада feed-модуля
  2. SUPPLIER  — выбор поставщика (последние 5 + пагинация при необходимости)
  3. NOM       — выбор номенклатуры (последние 5 в категориях feed-модуля)
  4. QTY       — text input количества (Decimal > 0)
  5. PRICE     — text input цены за единицу в сумах (Decimal > 0)
  6. CONFIRM   — резюме + кнопка «Провести» / «Отмена»

Под капотом: создаётся PurchaseOrder(status=DRAFT) + PurchaseItem,
вызывается `confirm_purchase` — он создаёт StockMovement(INCOMING),
JournalEntry, RawMaterialBatch (через сигнал на purchases.confirm).

Команда запуска: `/qabul`. RBAC: module="purchases".
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


# ─── State enum ────────────────────────────────────────────────────────────


class S:
    WAREHOUSE = "purchase:warehouse"
    SUPPLIER = "purchase:supplier"
    NOM = "purchase:nom"
    QTY = "purchase:qty"
    PRICE = "purchase:price"
    CONFIRM = "purchase:confirm"


WIZARD_CODE = "feed_purchase"


# ─── Entry command ─────────────────────────────────────────────────────────


@command(
    "/qabul",
    help="Приход на склад (закупка)",
    module="purchases",
    private=False,
)
def start_purchase(ctx: HandlerCtx) -> None:
    org = ctx.org()
    if org is None:
        send_message(ctx.chat_id, "Tashkilot tanlanmagan.")
        return

    # Список feed-warehouses этой организации.
    from apps.warehouses.models import Warehouse
    warehouses = list(
        Warehouse.objects.filter(
            organization=org, module__code="feed", is_active=True,
        ).order_by("code")[:8]
    )
    if not warehouses:
        send_message(
            ctx.chat_id,
            "❌ В feed-модуле нет складов. Создайте склад в /settings → Склады.",
        )
        return

    # Стартуем session (старая, если была — затирается).
    TgWizardSession.objects.update_or_create(
        chat_id=ctx.chat_id,
        defaults={
            "organization": org,
            "user": ctx.link.user if ctx.link else None,
            "wizard": WIZARD_CODE,
            "state": S.WAREHOUSE,
            "payload": {},
        },
    )

    buttons = [(f"📦 {w.code} · {w.name}", f"wiz:purchase:wh:{w.id}") for w in warehouses]
    buttons.append(("❌ Bekor", "wiz:purchase:cancel"))
    send_message(
        ctx.chat_id,
        "<b>📥 Приход на склад · шаг 1/5</b>\n\nВыберите склад:",
        reply_markup=kb(buttons, cols=1),
    )


# ─── Step 1 → 2: warehouse picked ─────────────────────────────────────────


def on_warehouse_picked(
    ctx: HandlerCtx, *, session: TgWizardSession, text: str | None,
) -> None:
    data = ctx.callback_data or ""
    if data == "wiz:purchase:cancel":
        return _cancel(ctx, session)

    # data: wiz:purchase:wh:<uuid>
    parts = data.split(":")
    if len(parts) != 4 or parts[2] != "wh":
        send_message(ctx.chat_id, "⚠️ Неверный выбор. /bekor — отменить.")
        return
    warehouse_id = parts[3]

    from apps.warehouses.models import Warehouse
    try:
        wh = Warehouse.objects.get(
            id=warehouse_id, organization=session.organization, module__code="feed",
        )
    except Warehouse.DoesNotExist:
        send_message(ctx.chat_id, "⚠️ Склад не найден.")
        return

    if _count_suppliers(session.organization) == 0:
        _cancel(ctx, session)
        send_message(
            ctx.chat_id,
            "❌ В системе нет активных поставщиков. Создайте контрагента kind=supplier.",
        )
        return

    session.advance(
        state=S.SUPPLIER,
        payload_update={"warehouse_id": warehouse_id, "warehouse_code": wh.code},
    )
    _render_suppliers(ctx, session, query="", page=0, edit=True)


# ─── Step 2 → 3: supplier picked ──────────────────────────────────────────


def on_supplier_picked(
    ctx: HandlerCtx, *, session: TgWizardSession, text: str | None,
) -> None:
    data = ctx.callback_data or ""
    if data == "wiz:purchase:cancel":
        return _cancel(ctx, session)

    parts = data.split(":")
    # Pagination/search reset через callback `wiz:purchase:sup:page:N`
    if len(parts) >= 5 and parts[2] == "sup" and parts[3] == "page":
        try:
            page = int(parts[4])
        except ValueError:
            page = 0
        query = (session.payload or {}).get("supplier_query", "")
        _render_suppliers(ctx, session, query=query, page=page, edit=True)
        return
    if len(parts) >= 4 and parts[2] == "sup" and parts[3] == "clear":
        # сброс поиска
        session.advance(state=S.SUPPLIER, payload_update={"supplier_query": ""})
        _render_suppliers(ctx, session, query="", page=0, edit=True)
        return

    if len(parts) != 4 or parts[2] != "sup":
        send_message(ctx.chat_id, "⚠️ Неверный выбор.")
        return
    supplier_id = parts[3]

    from apps.counterparties.models import Counterparty
    try:
        sup = Counterparty.objects.get(
            id=supplier_id, organization=session.organization, is_active=True,
        )
    except Counterparty.DoesNotExist:
        send_message(ctx.chat_id, "⚠️ Поставщик не найден.")
        return

    if _count_feed_nomenclatures(session.organization) == 0:
        _cancel(ctx, session)
        send_message(
            ctx.chat_id,
            "❌ В feed-модуле нет номенклатур. Добавьте позиции в /settings → Номенклатура.",
        )
        return

    session.advance(
        state=S.NOM,
        payload_update={
            "supplier_id": str(sup.id),
            "supplier_name": sup.name,
        },
    )
    _render_noms(ctx, session, query="", page=0, edit=True)


# ─── Step 3 → 4: nomenclature picked ──────────────────────────────────────


def on_nom_picked(
    ctx: HandlerCtx, *, session: TgWizardSession, text: str | None,
) -> None:
    data = ctx.callback_data or ""
    if data == "wiz:purchase:cancel":
        return _cancel(ctx, session)

    parts = data.split(":")
    # Пагинация / сброс поиска для номенклатуры
    if len(parts) >= 5 and parts[2] == "nom" and parts[3] == "page":
        try:
            page = int(parts[4])
        except ValueError:
            page = 0
        query = (session.payload or {}).get("nom_query", "")
        _render_noms(ctx, session, query=query, page=page, edit=True)
        return
    if len(parts) >= 4 and parts[2] == "nom" and parts[3] == "clear":
        session.advance(state=S.NOM, payload_update={"nom_query": ""})
        _render_noms(ctx, session, query="", page=0, edit=True)
        return

    if len(parts) != 4 or parts[2] != "nom":
        send_message(ctx.chat_id, "⚠️ Неверный выбор.")
        return
    nom_id = parts[3]

    from apps.nomenclature.models import NomenclatureItem
    try:
        nom = NomenclatureItem.objects.select_related("unit").get(
            id=nom_id, organization=session.organization,
        )
    except NomenclatureItem.DoesNotExist:
        send_message(ctx.chat_id, "⚠️ Товар не найден.")
        return

    session.advance(
        state=S.QTY,
        payload_update={
            "nom_id": nom_id, "nom_sku": nom.sku, "nom_name": nom.name,
            "unit_code": nom.unit.code if nom.unit_id else "",
        },
    )

    edit_message_text(
        ctx.chat_id, ctx.message_id,
        (
            f"<b>📥 Приход · шаг 4/5</b>\n"
            f"Товар: <b>{nom.sku}</b> — {nom.name}\n\n"
            f"Введите количество ({nom.unit.code if nom.unit_id else '?'}):\n"
            f"<i>например: 500</i>"
        ),
        reply_markup=kb([("❌ Bekor", "wiz:purchase:cancel")], cols=1),
    )


# ─── Step 4 → 5: qty input ────────────────────────────────────────────────


def on_qty_text(
    ctx: HandlerCtx, *, session: TgWizardSession, text: str | None,
) -> None:
    qty = _parse_decimal(text)
    if qty is None or qty <= 0:
        send_message(
            ctx.chat_id,
            "⚠️ Введите положительное число (например: 500 или 12.5).\n"
            "Или отмените: /bekor",
        )
        return

    session.advance(
        state=S.PRICE,
        payload_update={"quantity": str(qty)},
    )
    send_message(
        ctx.chat_id,
        (
            f"<b>📥 Приход · шаг 5/5</b>\n"
            f"Количество: <code>{qty} {session.payload.get('unit_code', '')}</code>\n\n"
            f"Введите цену за 1 {session.payload.get('unit_code', 'ед.')} в сумах:\n"
            f"<i>например: 18000</i>"
        ),
        reply_markup=kb([("❌ Bekor", "wiz:purchase:cancel")], cols=1),
    )


# ─── Step 5 → 6: price input + confirm ────────────────────────────────────


def on_price_text(
    ctx: HandlerCtx, *, session: TgWizardSession, text: str | None,
) -> None:
    price = _parse_decimal(text)
    if price is None or price <= 0:
        send_message(
            ctx.chat_id,
            "⚠️ Введите положительное число (например: 18000).\n"
            "Или отмените: /bekor",
        )
        return

    qty = Decimal(session.payload["quantity"])
    total = (qty * price).quantize(Decimal("0.01"))
    session.advance(
        state=S.CONFIRM,
        payload_update={"price": str(price), "total": str(total)},
    )

    p = session.payload
    summary = (
        f"<b>📥 Приход · подтверждение</b>\n\n"
        f"Склад: <code>{p['warehouse_code']}</code>\n"
        f"Поставщик: <b>{p['supplier_name']}</b>\n"
        f"Товар: <b>{p['nom_sku']}</b> — {p['nom_name']}\n"
        f"Количество: <code>{qty} {p.get('unit_code', '')}</code>\n"
        f"Цена за ед.: <code>{price:,} сум</code>\n"
        f"<b>Сумма: <code>{total:,} сум</code></b>".replace(",", " ")
    )
    send_message(
        ctx.chat_id,
        summary,
        reply_markup=kb(
            [
                ("✅ Провести", "wiz:purchase:do"),
                ("❌ Bekor", "wiz:purchase:cancel"),
            ],
            cols=2,
        ),
    )


# ─── Step 6: confirm ──────────────────────────────────────────────────────


def on_confirm(
    ctx: HandlerCtx, *, session: TgWizardSession, text: str | None,
) -> None:
    data = ctx.callback_data or ""
    if data == "wiz:purchase:cancel":
        return _cancel(ctx, session)
    if data != "wiz:purchase:do":
        send_message(ctx.chat_id, "⚠️ Неверная кнопка.")
        return

    p = session.payload
    org = session.organization
    user = session.user

    try:
        order = _create_and_confirm(p, org=org, user=user)
    except Exception as exc:  # noqa: BLE001
        logger.exception("feed_purchase wizard confirm failed")
        send_message(
            ctx.chat_id,
            f"❌ Не удалось провести закуп: <code>{str(exc)[:300]}</code>",
        )
        session.delete()
        return

    session.delete()
    edit_message_text(
        ctx.chat_id, ctx.message_id,
        (
            f"✅ <b>Закуп проведён</b>\n\n"
            f"Документ: <code>{order.doc_number}</code>\n"
            f"Сумма: <code>{order.amount_uzs:,} сум</code>".replace(",", " ")
        ),
    )


# ─── Helpers ──────────────────────────────────────────────────────────────


def _cancel(ctx: HandlerCtx, session: TgWizardSession) -> None:
    session.delete()
    edit_message_text(
        ctx.chat_id, ctx.message_id,
        "❌ Отменено.",
    )


def _parse_decimal(s: str | None) -> Decimal | None:
    if not s:
        return None
    s = s.strip().replace(",", ".").replace(" ", "")
    if not s:
        return None
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


PAGE_SIZE = 8


def _suppliers_qs(org, query: str = ""):
    from apps.counterparties.models import Counterparty
    qs = Counterparty.objects.filter(
        organization=org, is_active=True,
        kind__in=[Counterparty.Kind.SUPPLIER, Counterparty.Kind.OTHER],
    )
    q = (query or "").strip()
    if q:
        from django.db.models import Q
        qs = qs.filter(
            Q(name__icontains=q) | Q(code__icontains=q) | Q(inn__icontains=q),
        )
    return qs.order_by("-created_at")


def _count_suppliers(org) -> int:
    return _suppliers_qs(org).count()


def _feed_noms_qs(org, query: str = ""):
    from apps.nomenclature.models import NomenclatureItem
    qs = NomenclatureItem.objects.filter(
        organization=org, category__module__code="feed", is_active=True,
    ).select_related("unit")
    q = (query or "").strip()
    if q:
        from django.db.models import Q
        qs = qs.filter(Q(sku__icontains=q) | Q(name__icontains=q))
    return qs.order_by("-created_at")


def _count_feed_nomenclatures(org) -> int:
    return _feed_noms_qs(org).count()


def _render_suppliers(ctx, session, *, query: str, page: int, edit: bool) -> None:
    qs = _suppliers_qs(session.organization, query)
    total = qs.count()
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    items = list(qs[page * PAGE_SIZE:(page + 1) * PAGE_SIZE])
    buttons = [
        (f"🏭 {s.code} · {s.name[:30]}", f"wiz:purchase:sup:{s.id}")
        for s in items
    ]
    nav = []
    if page > 0:
        nav.append(("← Назад", f"wiz:purchase:sup:page:{page - 1}"))
    if page < pages - 1:
        nav.append(("Вперёд →", f"wiz:purchase:sup:page:{page + 1}"))
    if nav:
        buttons.extend(nav)
    if query:
        buttons.append(("🔄 Сбросить поиск", "wiz:purchase:sup:clear"))
    buttons.append(("❌ Bekor", "wiz:purchase:cancel"))
    session.advance(state=S.SUPPLIER, payload_update={"supplier_query": query})
    msg = (
        f"<b>📥 Приход · шаг 2/5</b>\n"
        f"Склад: <code>{session.payload.get('warehouse_code')}</code>\n\n"
        + (f"🔎 Поиск: <code>{query}</code> · найдено {total}\n" if query else "")
        + f"Страница {page + 1}/{pages} (всего {total})\n\n"
        + "Выберите поставщика или введите название/код для поиска:"
    )
    if edit and ctx.message_id:
        edit_message_text(ctx.chat_id, ctx.message_id, msg, reply_markup=kb(buttons, cols=1))
    else:
        send_message(ctx.chat_id, msg, reply_markup=kb(buttons, cols=1))


def _render_noms(ctx, session, *, query: str, page: int, edit: bool) -> None:
    qs = _feed_noms_qs(session.organization, query)
    total = qs.count()
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    items = list(qs[page * PAGE_SIZE:(page + 1) * PAGE_SIZE])
    buttons = [
        (f"🌾 {n.sku} · {n.name[:28]}", f"wiz:purchase:nom:{n.id}")
        for n in items
    ]
    nav = []
    if page > 0:
        nav.append(("← Назад", f"wiz:purchase:nom:page:{page - 1}"))
    if page < pages - 1:
        nav.append(("Вперёд →", f"wiz:purchase:nom:page:{page + 1}"))
    if nav:
        buttons.extend(nav)
    if query:
        buttons.append(("🔄 Сбросить поиск", "wiz:purchase:nom:clear"))
    buttons.append(("❌ Bekor", "wiz:purchase:cancel"))
    session.advance(state=S.NOM, payload_update={"nom_query": query})
    msg = (
        f"<b>📥 Приход · шаг 3/5</b>\n"
        f"Склад: <code>{session.payload.get('warehouse_code')}</code>\n"
        f"Поставщик: <b>{session.payload.get('supplier_name', '—')}</b>\n\n"
        + (f"🔎 Поиск: <code>{query}</code> · найдено {total}\n" if query else "")
        + f"Страница {page + 1}/{pages} (всего {total})\n\n"
        + "Выберите товар или введите SKU/название для поиска:"
    )
    if edit and ctx.message_id:
        edit_message_text(ctx.chat_id, ctx.message_id, msg, reply_markup=kb(buttons, cols=1))
    else:
        send_message(ctx.chat_id, msg, reply_markup=kb(buttons, cols=1))


def on_supplier_text(
    ctx: HandlerCtx, *, session: TgWizardSession, text: str | None,
) -> None:
    """Юзер ввёл текст на supplier-step → поиск."""
    query = (text or "").strip()
    _render_suppliers(ctx, session, query=query, page=0, edit=False)


def on_nom_text(
    ctx: HandlerCtx, *, session: TgWizardSession, text: str | None,
) -> None:
    """Юзер ввёл текст на nom-step → поиск."""
    query = (text or "").strip()
    _render_noms(ctx, session, query=query, page=0, edit=False)


def _create_and_confirm(payload: dict, *, org, user):
    """Создаёт DRAFT PurchaseOrder + items и сразу проводит."""
    from django.db import transaction

    from apps.common.services.numbering import next_doc_number
    from apps.modules.models import Module
    from apps.purchases.models import PurchaseItem, PurchaseOrder
    from apps.purchases.services.confirm import confirm_purchase

    feed_module = Module.objects.get(code="feed")
    today = timezone.localdate()

    with transaction.atomic():
        order = PurchaseOrder.objects.create(
            organization=org,
            module=feed_module,
            doc_number=next_doc_number(
                PurchaseOrder, organization=org, prefix="ЗК", on_date=today,
            ),
            date=today,
            counterparty_id=payload["supplier_id"],
            warehouse_id=payload["warehouse_id"],
            status=PurchaseOrder.Status.DRAFT,
            currency=None,  # UZS
            notes="Создано через Telegram-бот",
        )
        PurchaseItem.objects.create(
            order=order,
            nomenclature_id=payload["nom_id"],
            quantity=Decimal(payload["quantity"]),
            unit_price=Decimal(payload["price"]),
        )
        confirm_purchase(order, user=user)

    order.refresh_from_db()
    return order


# ─── Registration ─────────────────────────────────────────────────────────


register_wizard(WizardSpec(
    code=WIZARD_CODE,
    on_callback={
        S.WAREHOUSE: on_warehouse_picked,
        S.SUPPLIER: on_supplier_picked,
        S.NOM: on_nom_picked,
        S.CONFIRM: on_confirm,
    },
    on_message={
        S.SUPPLIER: on_supplier_text,
        S.NOM: on_nom_text,
        S.QTY: on_qty_text,
        S.PRICE: on_price_text,
    },
))
