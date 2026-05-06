"""
TG-handler «Sklad qoldiqlari» — список складов и их текущие остатки по SKU.

Логика остатка та же, что в WarehouseViewSet.balance:
  Σ INCOMING (warehouse_to=X) + Σ TRANSFER_IN
  − Σ OUTGOING + WRITE_OFF (warehouse_from=X) − Σ TRANSFER_OUT

Команды:
  /qoldiq            — список складов (с пагинацией)

Callback:
  fin:stock          — то же что /qoldiq, открывается из меню Moliya
  wh:bal:<wh_id>     — баланс конкретного склада
  wh:list:<page>     — пагинация по списку складов
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from django.db.models import Q, Sum

from ..bot import edit_message_text, send_message
from ..dispatcher import HandlerCtx, command, on_callback
from ..keyboards import kb, kb_back, kb_pagination


PAGE_SIZE = 10


def _fmt_qty(v) -> str:
    n = float(v or 0)
    return f"{n:,.2f}".replace(",", " ").rstrip("0").rstrip(".")


def _send_or_edit(ctx: HandlerCtx, text: str, markup: dict) -> None:
    if ctx.message_id is not None:
        edit_message_text(ctx.chat_id, ctx.message_id, text, reply_markup=markup)
    else:
        send_message(ctx.chat_id, text, reply_markup=markup)


# ─── Список складов ─────────────────────────────────────────────────────


@command("/qoldiq", help="Sklad qoldiqlari", module="stock")
def handle_qoldiq_cmd(ctx: HandlerCtx) -> None:
    _render_warehouse_list(ctx, page=1)


@on_callback("fin:stock")
def handle_fin_stock(ctx: HandlerCtx) -> None:
    _render_warehouse_list(ctx, page=1)


@on_callback("wh:list")
def handle_wh_list(ctx: HandlerCtx) -> None:
    """callback_data = wh:list:<page>. Dispatcher отрезает prefix (`wh:list`)
    и разрезает остаток по `:` → ctx.args = ['<page>']."""
    try:
        page = int(ctx.args[0]) if ctx.args else 1
    except (ValueError, IndexError):
        page = 1
    _render_warehouse_list(ctx, page=page)


def _render_warehouse_list(ctx: HandlerCtx, *, page: int) -> None:
    from apps.warehouses.models import Warehouse

    org = ctx.org()
    qs = (
        Warehouse.objects
        .filter(organization=org, is_active=True)
        .select_related("module")
        .order_by("module__code", "code")
    )
    total = qs.count()
    if total == 0:
        send_message(ctx.chat_id, "Faol omborlar yo'q.", reply_markup=kb_back("home:fin"))
        return

    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, pages))
    offset = (page - 1) * PAGE_SIZE
    rows = list(qs[offset:offset + PAGE_SIZE])

    lines = [
        f"📦 <b>Sklad qoldiqlari</b>",
        f"<i>Jami omborlar: {total}</i>",
        "",
        "<i>Tanlang ombor — ushbu omborning qoldiqlari ko'rinadi:</i>",
    ]

    buttons: list[tuple[str, str]] = []
    for w in rows:
        mod = w.module.code if w.module_id else "—"
        buttons.append((
            f"📦 {w.code} · {w.name[:25]}",
            f"wh:bal:{w.id}",
        ))
        lines.append(f"• <code>{w.code}</code> · {w.name} <i>({mod})</i>")

    # Pagination
    nav: list[tuple[str, str]] = []
    if page > 1:
        nav.append(("← Oldingi", f"wh:list:{page - 1}"))
    if page < pages:
        nav.append(("Keyingi →", f"wh:list:{page + 1}"))
    if nav:
        buttons.extend(nav)
    buttons.append(("← Orqaga", "home:fin"))

    _send_or_edit(ctx, "\n".join(lines), kb(buttons, cols=1))


# ─── Баланс склада ──────────────────────────────────────────────────────


@on_callback("wh:bal")
def handle_wh_balance(ctx: HandlerCtx) -> None:
    """callback_data = wh:bal:<warehouse_id>[:page]. Dispatcher отрезает
    prefix (`wh:bal`) и разрезает остаток по `:` → ctx.args = ['<uuid>', '<page>']."""
    if not ctx.args:
        send_message(ctx.chat_id, "Noto'g'ri so'rov.")
        return
    wh_id = ctx.args[0]
    try:
        page = int(ctx.args[1]) if len(ctx.args) >= 2 else 1
    except (ValueError, IndexError):
        page = 1
    _render_warehouse_balance(ctx, wh_id=wh_id, page=page)


def _compute_balance(warehouse) -> list[dict]:
    """Возвращает список {sku, name, unit, in_qty, out_qty, balance} для SKU
    у которых были движения на этом складе. Сортировка: с положительным
    остатком сверху, потом нулевые, потом отрицательные."""
    from apps.warehouses.models import StockMovement

    movements = (
        StockMovement.objects
        .filter(organization=warehouse.organization)
        .filter(Q(warehouse_from=warehouse) | Q(warehouse_to=warehouse))
        .values(
            "nomenclature_id",
            "nomenclature__sku",
            "nomenclature__name",
            "nomenclature__unit__code",
        )
        .annotate(
            in_qty=Sum("quantity", filter=Q(
                warehouse_to=warehouse,
                kind__in=[StockMovement.Kind.INCOMING, StockMovement.Kind.TRANSFER],
            )),
            out_qty=Sum("quantity", filter=Q(
                warehouse_from=warehouse,
                kind__in=[
                    StockMovement.Kind.OUTGOING,
                    StockMovement.Kind.WRITE_OFF,
                    StockMovement.Kind.TRANSFER,
                ],
            )),
        )
    )

    agg: dict = defaultdict(lambda: {
        "sku": "", "name": "", "unit": "",
        "in_qty": Decimal(0), "out_qty": Decimal(0),
    })
    for r in movements:
        a = agg[r["nomenclature_id"]]
        a["sku"] = r["nomenclature__sku"]
        a["name"] = r["nomenclature__name"]
        a["unit"] = r["nomenclature__unit__code"]
        a["in_qty"] += r.get("in_qty") or Decimal(0)
        a["out_qty"] += r.get("out_qty") or Decimal(0)

    rows = []
    for nom_id, a in agg.items():
        bal = a["in_qty"] - a["out_qty"]
        if a["in_qty"] == 0 and a["out_qty"] == 0:
            continue
        rows.append({
            "sku": a["sku"],
            "name": a["name"],
            "unit": a["unit"],
            "in_qty": a["in_qty"],
            "out_qty": a["out_qty"],
            "balance": bal,
        })
    rows.sort(key=lambda r: (
        -1 if r["balance"] > 0 else (0 if r["balance"] == 0 else 1),
        r["sku"],
    ))
    return rows


def _render_warehouse_balance(ctx: HandlerCtx, *, wh_id: str, page: int) -> None:
    from apps.warehouses.models import Warehouse

    org = ctx.org()
    try:
        warehouse = Warehouse.objects.select_related("module").get(
            id=wh_id, organization=org,
        )
    except Warehouse.DoesNotExist:
        send_message(ctx.chat_id, "Ombor topilmadi.")
        return

    rows = _compute_balance(warehouse)
    total = len(rows)
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, pages))
    offset = (page - 1) * PAGE_SIZE
    page_rows = rows[offset:offset + PAGE_SIZE]

    mod = warehouse.module.code if warehouse.module_id else "—"
    with_balance = sum(1 for r in rows if r["balance"] > 0)
    lines = [
        f"📦 <b>{warehouse.code} · {warehouse.name}</b>",
        f"<i>Modul: {mod} · Qoldiqli SKU: {with_balance} / Jami SKU: {total}</i>",
        "",
    ]
    if not page_rows:
        lines.append("Bu omborda harakatlar yo'q.")
    else:
        for r in page_rows:
            bal = r["balance"]
            unit = r["unit"] or ""
            sign = "✅" if bal > 0 else ("⚪" if bal == 0 else "🔴")
            lines.append(
                f"{sign} <code>{r['sku']}</code>"
                f" — <b>{_fmt_qty(bal)} {unit}</b>"
            )
            lines.append(
                f"   <i>({r['name']}) · "
                f"+{_fmt_qty(r['in_qty'])} − {_fmt_qty(r['out_qty'])}</i>"
            )

    markup = kb_pagination(
        f"wh:bal:{wh_id}", page, total,
        back_to="fin:stock",
    )
    _send_or_edit(ctx, "\n".join(lines), markup)
