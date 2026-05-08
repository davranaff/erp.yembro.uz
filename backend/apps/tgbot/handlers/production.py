"""
Производство: партии откорма, карточка партии, стадо маточника.

Reuse:
  - apps.feedlot.services.fcr.get_kpi(fb) — FCR / выживаемость / день
  - apps.batches.models.Batch — `current_module`, `accumulated_cost_uzs`
  - apps.matочник.models.BreedingHerd — heads, продуктивность недели
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal

from ..bot import edit_message_text, send_message
from ..dispatcher import HandlerCtx, command, has_module_access, on_callback
from ..keyboards import kb, kb_back

logger = logging.getLogger(__name__)


def _fmt_uzs(value) -> str:
    if value is None or value == "":
        return "—"
    n = Decimal(str(value))
    return f"{n:,.0f}".replace(",", " ")


# ─── home:batch / home:prod (callback от /menu) ─────────────────────────


def render_batches_section(ctx: HandlerCtx) -> None:
    """Список активных партий + drill-down по `/batch`."""
    if not has_module_access(ctx.link, "feedlot"):
        send_message(ctx.chat_id, "⛔ Нет доступа к модулю <b>Откорм</b>.")
        return
    _render_feedlot_list(ctx, edit=True)


def render_production_section(ctx: HandlerCtx) -> None:
    """Сводка по производству — heads по модулям. Reuse legacy /production."""
    from apps.dashboard.services import production_summary
    from ..notifications import fmt_production
    org = ctx.org()
    text = fmt_production(production_summary(org))
    markup = kb_back("home")
    if ctx.message_id:
        edit_message_text(ctx.chat_id, ctx.message_id, text, reply_markup=markup)
    else:
        send_message(ctx.chat_id, text, reply_markup=markup)


# ─── /feedlot ────────────────────────────────────────────────────────────


@command("/feedlot", help="Активные партии откорма", module="feedlot")
def handle_feedlot_cmd(ctx: HandlerCtx) -> None:
    _render_feedlot_list(ctx)


def _render_feedlot_list(ctx: HandlerCtx, *, edit: bool = False) -> None:
    from apps.feedlot.models import FeedlotBatch

    org = ctx.org()
    today = date.today()
    qs = (
        FeedlotBatch.objects
        .filter(
            organization=org,
            status__in=[
                FeedlotBatch.Status.PLACED,
                FeedlotBatch.Status.GROWING,
                FeedlotBatch.Status.READY_SLAUGHTER,
            ],
        )
        .select_related("house_block", "batch")
        .order_by("placed_date")[:15]
    )
    items = list(qs)

    lines = ["📦 <b>Активные партии откорма</b>", ""]
    if not items:
        lines.append("Нет активных партий.")
        markup = kb_back("home")
    else:
        # Моноширинная таблица: doc · корпус · день · поголовье.
        doc_w = max(8, min(14, max(len(fb.doc_number) for fb in items)))
        rows_text = []
        buttons: list[tuple[str, str]] = []
        for fb in items:
            day = (today - fb.placed_date).days if fb.placed_date else 0
            house = (fb.house_block.code if fb.house_block_id else "—")[:8]
            doc = fb.doc_number[:doc_w]
            rows_text.append(
                f"{doc:<{doc_w}}  {house:<8}  d{day:<3} {fb.current_heads:>6} гол"
            )
            if fb.batch_id:
                buttons.append((f"📋 {fb.doc_number}", f"prod:batch:{fb.batch.doc_number}"))
        lines.append("<pre>" + "\n".join(rows_text) + "</pre>")
        # max 8 кнопок (Telegram UX), оставшиеся юзер дёрнет через /batch
        markup = kb(buttons[:8] + [("← Назад", "home")], cols=2)

    text = "\n".join(lines)
    if edit and ctx.message_id:
        edit_message_text(ctx.chat_id, ctx.message_id, text, reply_markup=markup)
    else:
        send_message(ctx.chat_id, text, reply_markup=markup)


# ─── /batch <doc> ────────────────────────────────────────────────────────


@command("/batch", help="Карточка партии: /batch <doc_number>", module="feedlot")
def handle_batch_cmd(ctx: HandlerCtx) -> None:
    if not ctx.args:
        send_message(
            ctx.chat_id,
            "Использование: <code>/batch &lt;doc_number&gt;</code>\n"
            "Пример: <code>/batch П-2026-00042</code>",
        )
        return
    _render_batch_card(ctx, doc=ctx.args[0])


@on_callback("prod:batch")
def handle_batch_callback(ctx: HandlerCtx) -> None:
    """Callback `prod:batch:<doc>` от drill-down кнопки."""
    if len(ctx.args) < 1:
        return
    if not has_module_access(ctx.link, "feedlot"):
        send_message(ctx.chat_id, "⛔ Нет доступа.")
        return
    _render_batch_card(ctx, doc=":".join(ctx.args), edit=True)


def _render_batch_card(ctx: HandlerCtx, *, doc: str, edit: bool = False) -> None:
    from apps.batches.models import Batch

    org = ctx.org()
    batch = (
        Batch.objects
        .filter(organization=org, doc_number=doc)
        .select_related("current_module", "current_block", "nomenclature", "unit")
        .first()
    )
    if batch is None:
        send_message(ctx.chat_id, f"❌ Партия <code>{doc}</code> не найдена.")
        return

    module = batch.current_module.name if batch.current_module_id else "—"
    block = batch.current_block.code if batch.current_block_id else "—"
    unit = batch.unit.code if batch.unit_id else ""

    lines = [
        f"📋 <b>{batch.doc_number}</b>",
        f"<i>{batch.nomenclature.name if batch.nomenclature_id else ''}</i>",
        "",
        f"📍 Где: <b>{module}</b> · {block}",
        f"⚖️ Остаток: <code>{batch.current_quantity}</code> {unit}",
        f"📦 Изначально: <code>{batch.initial_quantity}</code> {unit}",
        f"💰 Накопленная себестоимость: <code>{_fmt_uzs(batch.accumulated_cost_uzs)}</code> сум",
        f"📅 Запущена: <code>{batch.started_at}</code>",
    ]

    # Если есть feedlot-привязка — добавим KPI.
    fb = batch.feedlot_placements.first() if hasattr(batch, "feedlot_placements") else None
    if fb is not None:
        try:
            from apps.feedlot.services.fcr import get_kpi
            kpi = get_kpi(fb)
            lines.append("")
            lines.append("<b>KPI откорма:</b>")
            lines.append(f"  День: {kpi.days_on_feedlot}")
            lines.append(f"  Поголовье: {kpi.current_heads}/{kpi.initial_heads}")
            lines.append(f"  Выживаемость: {kpi.survival_pct}%")
            if kpi.total_fcr is not None:
                lines.append(f"  FCR: {kpi.total_fcr}")
            if kpi.current_avg_weight_kg is not None:
                lines.append(f"  Ср. вес: {kpi.current_avg_weight_kg} кг")
        except Exception:  # noqa: BLE001
            logger.exception("get_kpi failed for fb=%s", fb.id)

    text = "\n".join(lines)
    markup = kb_back("home:batch")
    if edit and ctx.message_id:
        edit_message_text(ctx.chat_id, ctx.message_id, text, reply_markup=markup)
    else:
        send_message(ctx.chat_id, text, reply_markup=markup)


# ─── /herd <doc> ─────────────────────────────────────────────────────────


@command("/herd", help="Карточка стада маточника: /herd <doc_number>", module="matochnik")
def handle_herd_cmd(ctx: HandlerCtx) -> None:
    if not ctx.args:
        send_message(
            ctx.chat_id,
            "Использование: <code>/herd &lt;doc_number&gt;</code>",
        )
        return
    _render_herd_card(ctx, doc=ctx.args[0])


def _render_herd_card(ctx: HandlerCtx, *, doc: str) -> None:
    from django.db.models import Sum
    from apps.matochnik.models import (
        BreedingHerd, BreedingMortality, DailyEggProduction,
    )

    org = ctx.org()
    herd = (
        BreedingHerd.objects
        .filter(organization=org, doc_number=doc)
        .select_related("block")
        .first()
    )
    if herd is None:
        send_message(ctx.chat_id, f"❌ Стадо <code>{doc}</code> не найдено.")
        return

    today = date.today()
    week_start = today - timedelta(days=6)
    egg_agg = DailyEggProduction.objects.filter(
        herd=herd, date__gte=week_start, date__lte=today,
    ).aggregate(eggs=Sum("eggs_collected"), unfit=Sum("unfit_eggs"))
    eggs = (egg_agg["eggs"] or 0) - (egg_agg["unfit"] or 0)
    mort_week = (
        BreedingMortality.objects
        .filter(herd=herd, date__gte=week_start, date__lte=today)
        .aggregate(s=Sum("dead_count"))["s"] or 0
    )
    block = herd.block.code if herd.block_id else "—"

    lines = [
        f"🐔 <b>{herd.doc_number}</b>",
        "",
        f"📍 Корпус: <b>{block}</b>",
        f"👥 Поголовье: <b>{herd.current_heads}</b> / {herd.initial_heads}",
        f"📊 Статус: {herd.get_status_display()}",
        "",
        "<b>За неделю:</b>",
        f"  🥚 Яйцо чистое: <code>{eggs}</code> шт",
        f"  💀 Падёж: <code>{mort_week}</code> гол",
    ]
    text = "\n".join(lines)
    send_message(ctx.chat_id, text, reply_markup=kb_back("home"))
