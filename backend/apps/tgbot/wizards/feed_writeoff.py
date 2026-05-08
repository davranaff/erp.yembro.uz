"""
Wizard «Списание со склада» — `/chiqim`.

Создаёт `StockMovement(WRITE_OFF)` для feed-склада через
`create_manual_movement`. Используется для порчи/потерь — это **не**
производственное списание (для замеса есть отдельный wizard).

Шаги:
  1. WAREHOUSE — выбор склада feed-модуля
  2. NOM       — выбор номенклатуры (последние 8 в feed)
  3. QTY       — ввод количества (≤ текущего остатка по WH)
  4. REASON    — текстовая причина (≥ 3 символа)
  5. CONFIRM   — резюме + Провести / Отмена

Цена для списания берётся как WAC по INCOMING на этом складе
(средневзвешенная по amount/quantity). Если приходов не было —
WRITE_OFF недопустим (нечего списывать).
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


class S:
    WAREHOUSE = "writeoff:warehouse"
    NOM = "writeoff:nom"
    QTY = "writeoff:qty"
    REASON = "writeoff:reason"
    CONFIRM = "writeoff:confirm"


WIZARD_CODE = "feed_writeoff"


@command(
    "/chiqim",
    help="Списание со склада (потеря/порча)",
    module="stock",
    private=False,
)
def start_writeoff(ctx: HandlerCtx) -> None:
    org = ctx.org()
    if org is None:
        send_message(ctx.chat_id, "Tashkilot tanlanmagan.")
        return

    from apps.warehouses.models import Warehouse
    warehouses = list(
        Warehouse.objects.filter(
            organization=org, module__code="feed", is_active=True,
        ).order_by("code")[:8]
    )
    if not warehouses:
        send_message(ctx.chat_id, "❌ В feed-модуле нет складов.")
        return

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

    buttons = [(f"📦 {w.code} · {w.name}", f"wiz:writeoff:wh:{w.id}") for w in warehouses]
    buttons.append(("❌ Bekor", "wiz:writeoff:cancel"))
    send_message(
        ctx.chat_id,
        "<b>📤 Списание · шаг 1/4</b>\n\nВыберите склад:",
        reply_markup=kb(buttons, cols=1),
    )


def on_warehouse_picked(
    ctx: HandlerCtx, *, session: TgWizardSession, text: str | None,
) -> None:
    data = ctx.callback_data or ""
    if data == "wiz:writeoff:cancel":
        return _cancel(ctx, session)

    parts = data.split(":")
    if len(parts) != 4 or parts[2] != "wh":
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

    if _count_feed_nomenclatures(session.organization) == 0:
        _cancel(ctx, session)
        send_message(ctx.chat_id, "❌ В feed-модуле нет номенклатур.")
        return

    session.advance(
        state=S.NOM,
        payload_update={"warehouse_id": warehouse_id, "warehouse_code": wh.code},
    )
    _render_noms(ctx, session, query="", page=0, edit=True)


def on_nom_picked(
    ctx: HandlerCtx, *, session: TgWizardSession, text: str | None,
) -> None:
    data = ctx.callback_data or ""
    if data == "wiz:writeoff:cancel":
        return _cancel(ctx, session)

    parts = data.split(":")
    # Пагинация / сброс поиска
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

    balance, wac = _stock_balance_and_wac(
        nomenclature_id=nom.id,
        warehouse_id=session.payload["warehouse_id"],
    )
    if balance <= 0:
        _cancel(ctx, session)
        send_message(
            ctx.chat_id,
            f"❌ Остаток <b>{nom.sku}</b> на складе "
            f"<code>{session.payload['warehouse_code']}</code> равен нулю.",
        )
        return

    session.advance(
        state=S.QTY,
        payload_update={
            "nom_id": str(nom.id), "nom_sku": nom.sku, "nom_name": nom.name,
            "unit_code": nom.unit.code if nom.unit_id else "",
            "balance": str(balance),
            "unit_price": str(wac),
        },
    )
    edit_message_text(
        ctx.chat_id, ctx.message_id,
        (
            f"<b>📤 Списание · шаг 3/4</b>\n"
            f"Товар: <b>{nom.sku}</b> — {nom.name}\n"
            f"Остаток: <code>{balance} {nom.unit.code if nom.unit_id else ''}</code>\n"
            f"Себест.: <code>{wac:,} сум/ед.</code>\n\n"
            f"Введите количество к списанию:".replace(",", " ")
        ),
        reply_markup=kb([("❌ Bekor", "wiz:writeoff:cancel")], cols=1),
    )


def on_qty_text(
    ctx: HandlerCtx, *, session: TgWizardSession, text: str | None,
) -> None:
    qty = _parse_decimal(text)
    if qty is None or qty <= 0:
        send_message(
            ctx.chat_id,
            "⚠️ Введите положительное число (например: 5 или 12.5).",
        )
        return
    balance = Decimal(session.payload["balance"])
    if qty > balance:
        send_message(
            ctx.chat_id,
            f"⚠️ Количество <code>{qty}</code> > остатка <code>{balance}</code>.",
        )
        return

    session.advance(
        state=S.REASON,
        payload_update={"quantity": str(qty)},
    )
    send_message(
        ctx.chat_id,
        (
            f"<b>📤 Списание · шаг 4/4</b>\n"
            f"Количество: <code>{qty} {session.payload.get('unit_code', '')}</code>\n\n"
            f"Опишите причину (порча / потеря / экспертиза):"
        ),
        reply_markup=kb([("❌ Bekor", "wiz:writeoff:cancel")], cols=1),
    )


def on_reason_text(
    ctx: HandlerCtx, *, session: TgWizardSession, text: str | None,
) -> None:
    reason = (text or "").strip()
    if len(reason) < 3:
        send_message(ctx.chat_id, "⚠️ Минимум 3 символа в причине.")
        return

    session.advance(
        state=S.CONFIRM,
        payload_update={"reason": reason[:200]},
    )

    p = session.payload
    qty = Decimal(p["quantity"])
    price = Decimal(p["unit_price"])
    total = (qty * price).quantize(Decimal("0.01"))
    summary = (
        f"<b>📤 Списание · подтверждение</b>\n\n"
        f"Склад: <code>{p['warehouse_code']}</code>\n"
        f"Товар: <b>{p['nom_sku']}</b> — {p['nom_name']}\n"
        f"Количество: <code>{qty} {p.get('unit_code', '')}</code>\n"
        f"Себест.: <code>{price:,} сум/ед.</code>\n"
        f"<b>Сумма: <code>{total:,} сум</code></b>\n"
        f"Причина: <i>{p['reason']}</i>".replace(",", " ")
    )
    send_message(
        ctx.chat_id,
        summary,
        reply_markup=kb(
            [
                ("✅ Списать", "wiz:writeoff:do"),
                ("❌ Bekor", "wiz:writeoff:cancel"),
            ],
            cols=2,
        ),
    )


def on_confirm(
    ctx: HandlerCtx, *, session: TgWizardSession, text: str | None,
) -> None:
    data = ctx.callback_data or ""
    if data == "wiz:writeoff:cancel":
        return _cancel(ctx, session)
    if data != "wiz:writeoff:do":
        return

    p = session.payload
    org = session.organization
    user = session.user

    try:
        movement = _create_writeoff(p, org=org, user=user)
    except Exception as exc:  # noqa: BLE001
        logger.exception("feed_writeoff wizard confirm failed")
        send_message(
            ctx.chat_id,
            f"❌ Не удалось списать: <code>{str(exc)[:300]}</code>",
        )
        session.delete()
        return

    session.delete()
    edit_message_text(
        ctx.chat_id, ctx.message_id,
        (
            f"✅ <b>Списание проведено</b>\n\n"
            f"Документ: <code>{movement.doc_number}</code>\n"
            f"Сумма: <code>{movement.amount_uzs:,} сум</code>".replace(",", " ")
        ),
    )


# ─── Helpers ──────────────────────────────────────────────────────────────


def _cancel(ctx: HandlerCtx, session: TgWizardSession) -> None:
    session.delete()
    edit_message_text(ctx.chat_id, ctx.message_id, "❌ Отменено.")


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


def _render_noms(ctx, session, *, query: str, page: int, edit: bool) -> None:
    qs = _feed_noms_qs(session.organization, query)
    total = qs.count()
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    items = list(qs[page * PAGE_SIZE:(page + 1) * PAGE_SIZE])
    buttons = [
        (f"🌾 {n.sku} · {n.name[:28]}", f"wiz:writeoff:nom:{n.id}")
        for n in items
    ]
    nav = []
    if page > 0:
        nav.append(("← Назад", f"wiz:writeoff:nom:page:{page - 1}"))
    if page < pages - 1:
        nav.append(("Вперёд →", f"wiz:writeoff:nom:page:{page + 1}"))
    if nav:
        buttons.extend(nav)
    if query:
        buttons.append(("🔄 Сбросить поиск", "wiz:writeoff:nom:clear"))
    buttons.append(("❌ Bekor", "wiz:writeoff:cancel"))
    session.advance(state=S.NOM, payload_update={"nom_query": query})
    msg = (
        f"<b>📤 Списание · шаг 2/4</b>\n"
        f"Склад: <code>{session.payload.get('warehouse_code')}</code>\n\n"
        + (f"🔎 Поиск: <code>{query}</code> · найдено {total}\n" if query else "")
        + f"Страница {page + 1}/{pages} (всего {total})\n\n"
        + "Выберите товар или введите SKU/название для поиска:"
    )
    if edit and ctx.message_id:
        edit_message_text(ctx.chat_id, ctx.message_id, msg, reply_markup=kb(buttons, cols=1))
    else:
        send_message(ctx.chat_id, msg, reply_markup=kb(buttons, cols=1))


def on_nom_text(
    ctx: HandlerCtx, *, session: TgWizardSession, text: str | None,
) -> None:
    query = (text or "").strip()
    _render_noms(ctx, session, query=query, page=0, edit=False)


def _stock_balance_and_wac(
    *, nomenclature_id, warehouse_id,
) -> tuple[Decimal, Decimal]:
    """
    Возвращает (текущий_остаток, средневзвешенная_цена) для пары
    (warehouse, nomenclature). Учитывает все INCOMING/OUTGOING/WRITE_OFF.

    WAC = Σ(INCOMING.amount) / Σ(INCOMING.quantity). Если приходов не
    было — WAC = 0 (в этом случае balance тоже 0, операция отвергнута).
    """
    from django.db.models import Sum
    from apps.warehouses.models import StockMovement

    incoming = StockMovement.objects.filter(
        nomenclature_id=nomenclature_id, warehouse_to_id=warehouse_id,
        kind=StockMovement.Kind.INCOMING,
    ).aggregate(qty=Sum("quantity"), amt=Sum("amount_uzs"))
    outgoing = StockMovement.objects.filter(
        nomenclature_id=nomenclature_id, warehouse_from_id=warehouse_id,
        kind__in=[
            StockMovement.Kind.OUTGOING,
            StockMovement.Kind.WRITE_OFF,
            StockMovement.Kind.SHRINKAGE,
        ],
    ).aggregate(qty=Sum("quantity"))

    in_qty = Decimal(incoming["qty"] or 0)
    in_amt = Decimal(incoming["amt"] or 0)
    out_qty = Decimal(outgoing["qty"] or 0)

    balance = in_qty - out_qty
    wac = (in_amt / in_qty).quantize(Decimal("0.01")) if in_qty > 0 else Decimal(0)
    return balance, wac


def _create_writeoff(payload: dict, *, org, user):
    from apps.modules.models import Module
    from apps.nomenclature.models import NomenclatureItem
    from apps.warehouses.models import Warehouse
    from apps.warehouses.services.create import create_manual_movement

    feed_module = Module.objects.get(code="feed")
    wh = Warehouse.objects.get(id=payload["warehouse_id"])
    nom = NomenclatureItem.objects.get(id=payload["nom_id"])

    res = create_manual_movement(
        organization=org,
        module=feed_module,
        kind="write_off",
        nomenclature=nom,
        quantity=Decimal(payload["quantity"]),
        unit_price_uzs=Decimal(payload["unit_price"]),
        warehouse_from=wh,
        date_value=timezone.now(),
        user=user,
    )
    movement = res.movement
    # У StockMovement нет поля для reason. Пишем причину в audit-trail
    # отдельной записью с action_verb — её видно в /audit-log как комментарий.
    if payload.get("reason"):
        from apps.audit.models import AuditLog
        from apps.audit.services.writer import audit_log
        audit_log(
            organization=org,
            module=feed_module,
            actor=user,
            action=AuditLog.Action.UPDATE,
            entity=movement,
            action_verb=f"причина списания: {payload['reason']}",
        )
    return movement


register_wizard(WizardSpec(
    code=WIZARD_CODE,
    on_callback={
        S.WAREHOUSE: on_warehouse_picked,
        S.NOM: on_nom_picked,
        S.CONFIRM: on_confirm,
    },
    on_message={
        S.NOM: on_nom_text,
        S.QTY: on_qty_text,
        S.REASON: on_reason_text,
    },
))
