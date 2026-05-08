"""
Wizard «Замес» — `/aralash`.

В отличие от Mini App, бот не создаёт новый ProductionTask с компонентами
(это много шагов, удобнее в вебе). Бот **проводит уже созданный** task
из статуса PLANNED → DONE через `execute_production_task`.

Флоу:
  1. TASK     — выбор PLANNED task'а (последние 8)
  2. OUTPUT   — выбор склада готового корма (feed warehouses) +
                storage_bin. Если по 1 элементу в каждом — автоматом.
  3. ACTUAL   — фактический выход кг (или «skip» = planned)
  4. CONFIRM  — резюме + Провести

execute_production_task делает:
  - списание сырья OUTGOING
  - FeedBatch (готовый корм) + INCOMING
  - JE 10.05 / 10.01

Если у компонентов task'а не назначены source_batch'и — wizard падает на
confirm с понятной ошибкой (это конфигурационная проблема, фиксится в
вебе). После аудита gap #1 — также проверка NomenclatureItem(sku=recipe.code).
"""
from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from ..bot import edit_message_text, send_message
from ..dispatcher import HandlerCtx, command
from ..keyboards import kb
from ..models import TgWizardSession
from . import WizardSpec, register_wizard


logger = logging.getLogger(__name__)


class S:
    TASK = "mix:task"
    OUTPUT = "mix:output"
    ACTUAL = "mix:actual"
    CONFIRM = "mix:confirm"


WIZARD_CODE = "feed_mix"


@command(
    "/aralash",
    help="Провести замес (выпуск партии корма)",
    module="feed",
    private=False,
)
def start_mix(ctx: HandlerCtx) -> None:
    org = ctx.org()
    if org is None:
        send_message(ctx.chat_id, "Tashkilot tanlanmagan.")
        return

    from apps.feed.models import ProductionTask
    tasks = list(
        ProductionTask.objects.filter(
            organization=org, status=ProductionTask.Status.PLANNED,
        )
        .select_related("recipe_version__recipe", "production_line")
        .order_by("scheduled_at")[:8]
    )
    if not tasks:
        send_message(
            ctx.chat_id,
            "❌ Нет заданий в статусе PLANNED.\n\n"
            "Создайте задание в /feed → Задания, затем повторите.",
        )
        return

    TgWizardSession.objects.update_or_create(
        chat_id=ctx.chat_id,
        defaults={
            "organization": org,
            "user": ctx.link.user if ctx.link else None,
            "wizard": WIZARD_CODE,
            "state": S.TASK,
            "payload": {},
        },
    )

    buttons = []
    for t in tasks:
        recipe_code = t.recipe_version.recipe.code if t.recipe_version_id else "?"
        label = f"📋 {t.doc_number} · {recipe_code} · {t.planned_quantity_kg:g} кг"
        buttons.append((label[:60], f"wiz:mix:task:{t.id}"))
    buttons.append(("❌ Bekor", "wiz:mix:cancel"))
    send_message(
        ctx.chat_id,
        "<b>🥣 Замес · шаг 1/3</b>\n\nВыберите PLANNED задание:",
        reply_markup=kb(buttons, cols=1),
    )


def on_task_picked(
    ctx: HandlerCtx, *, session: TgWizardSession, text: str | None,
) -> None:
    data = ctx.callback_data or ""
    if data == "wiz:mix:cancel":
        return _cancel(ctx, session)
    parts = data.split(":")
    if len(parts) != 4 or parts[2] != "task":
        return
    task_id = parts[3]

    from apps.feed.models import ProductionTask
    try:
        task = ProductionTask.objects.select_related(
            "recipe_version__recipe", "module",
        ).get(id=task_id, organization=session.organization)
    except ProductionTask.DoesNotExist:
        send_message(ctx.chat_id, "⚠️ Задание не найдено.")
        return
    if task.status != ProductionTask.Status.PLANNED:
        send_message(
            ctx.chat_id,
            f"⚠️ Задание в статусе <b>{task.get_status_display()}</b> — нельзя провести.",
        )
        return

    # Подберём склад выхода и storage_bin. Если их по одному — автоматом.
    from apps.warehouses.models import ProductionBlock, Warehouse
    warehouses = list(Warehouse.objects.filter(
        organization=session.organization, module=task.module, is_active=True,
    ).order_by("code"))
    bins = list(ProductionBlock.objects.filter(
        organization=session.organization, module=task.module,
        kind=ProductionBlock.Kind.STORAGE_BIN, is_active=True,
    ).order_by("code"))

    if not warehouses or not bins:
        _cancel(ctx, session)
        send_message(
            ctx.chat_id,
            "❌ В feed-модуле нет склада готового корма или бункера. "
            "Настройте их в /settings.",
        )
        return

    session.advance(
        state=S.OUTPUT,
        payload_update={
            "task_id": str(task.id),
            "task_doc": task.doc_number,
            "recipe_code": task.recipe_version.recipe.code,
            "planned_qty": str(task.planned_quantity_kg),
        },
    )

    # Если ровно по одной опции с каждой стороны — пропускаем выбор и сразу
    # переходим в actual. Иначе показываем кнопки склада.
    if len(warehouses) == 1 and len(bins) == 1:
        session.advance(
            state=S.ACTUAL,
            payload_update={
                "warehouse_id": str(warehouses[0].id),
                "warehouse_code": warehouses[0].code,
                "bin_id": str(bins[0].id),
                "bin_code": bins[0].code,
            },
        )
        _ask_actual(ctx, session)
        return

    # Сначала показываем склады (по 1 на ряд). Каждая кнопка вшивает оба id.
    # callback: wiz:mix:wh:{wh_id}:{bin_id} — но 64 байт мало для двух uuid'ов.
    # Поэтому показываем сначала склад, потом bin отдельным шагом.
    buttons = [
        (f"📦 {w.code} · {w.name[:24]}", f"wiz:mix:wh:{w.id}")
        for w in warehouses[:8]
    ]
    buttons.append(("❌ Bekor", "wiz:mix:cancel"))
    edit_message_text(
        ctx.chat_id, ctx.message_id,
        (
            f"<b>🥣 Замес · шаг 2/3</b>\n"
            f"Задание: <code>{task.doc_number}</code>\n"
            f"Рецепт: <b>{task.recipe_version.recipe.code}</b> · {task.planned_quantity_kg:g} кг\n\n"
            f"Выберите склад готового корма:"
        ),
        reply_markup=kb(buttons, cols=1),
    )


def on_output_picked(
    ctx: HandlerCtx, *, session: TgWizardSession, text: str | None,
) -> None:
    data = ctx.callback_data or ""
    if data == "wiz:mix:cancel":
        return _cancel(ctx, session)
    parts = data.split(":")
    if len(parts) < 4:
        return

    if parts[2] == "wh":
        wh_id = parts[3]
        from apps.warehouses.models import ProductionBlock, Warehouse
        try:
            wh = Warehouse.objects.get(id=wh_id, organization=session.organization)
        except Warehouse.DoesNotExist:
            return
        # Запоминаем склад, показываем выбор бункера.
        session.advance(
            state=S.OUTPUT,
            payload_update={"warehouse_id": str(wh.id), "warehouse_code": wh.code},
        )
        bins = list(ProductionBlock.objects.filter(
            organization=session.organization,
            kind=ProductionBlock.Kind.STORAGE_BIN, is_active=True,
        ).order_by("code"))
        buttons = [
            (f"🛢 {b.code} · {b.name[:24]}", f"wiz:mix:bin:{b.id}")
            for b in bins[:8]
        ]
        buttons.append(("❌ Bekor", "wiz:mix:cancel"))
        edit_message_text(
            ctx.chat_id, ctx.message_id,
            f"Склад: <code>{wh.code}</code>\n\nВыберите бункер хранения:",
            reply_markup=kb(buttons, cols=1),
        )
        return

    if parts[2] == "bin":
        bin_id = parts[3]
        from apps.warehouses.models import ProductionBlock
        try:
            blk = ProductionBlock.objects.get(
                id=bin_id, organization=session.organization,
                kind=ProductionBlock.Kind.STORAGE_BIN,
            )
        except ProductionBlock.DoesNotExist:
            return
        session.advance(
            state=S.ACTUAL,
            payload_update={"bin_id": str(blk.id), "bin_code": blk.code},
        )
        _ask_actual(ctx, session)
        return


def _ask_actual(ctx: HandlerCtx, session: TgWizardSession) -> None:
    p = session.payload
    msg = (
        f"<b>🥣 Замес · шаг 3/3</b>\n"
        f"Задание: <code>{p['task_doc']}</code> · {p['recipe_code']}\n"
        f"План: <code>{p['planned_qty']} кг</code>\n"
        f"Склад: <code>{p['warehouse_code']}</code> / Бункер: <code>{p['bin_code']}</code>\n\n"
        f"Введите фактический выход в кг (или нажмите «Как план»):"
    )
    send_message(
        ctx.chat_id, msg,
        reply_markup=kb([
            ("= План", "wiz:mix:actual:planned"),
            ("❌ Bekor", "wiz:mix:cancel"),
        ], cols=2),
    )


def on_actual_callback(
    ctx: HandlerCtx, *, session: TgWizardSession, text: str | None,
) -> None:
    data = ctx.callback_data or ""
    if data == "wiz:mix:cancel":
        return _cancel(ctx, session)
    if data == "wiz:mix:actual:planned":
        actual = Decimal(session.payload["planned_qty"])
        _go_to_confirm(ctx, session, actual)
        return


def on_actual_text(
    ctx: HandlerCtx, *, session: TgWizardSession, text: str | None,
) -> None:
    actual = _parse_decimal(text)
    if actual is None or actual <= 0:
        send_message(
            ctx.chat_id,
            "⚠️ Введите положительное число или нажмите «= План».",
        )
        return
    _go_to_confirm(ctx, session, actual)


def _go_to_confirm(
    ctx: HandlerCtx, session: TgWizardSession, actual: Decimal,
) -> None:
    p = session.payload
    session.advance(
        state=S.CONFIRM,
        payload_update={"actual_qty": str(actual)},
    )
    summary = (
        f"<b>🥣 Замес · подтверждение</b>\n\n"
        f"Задание: <code>{p['task_doc']}</code>\n"
        f"Рецепт: <b>{p['recipe_code']}</b>\n"
        f"План: <code>{p['planned_qty']} кг</code>\n"
        f"Факт: <code>{actual} кг</code>\n"
        f"Склад: <code>{p['warehouse_code']}</code> / Бункер: <code>{p['bin_code']}</code>"
    )
    send_message(
        ctx.chat_id, summary,
        reply_markup=kb([
            ("✅ Провести", "wiz:mix:do"),
            ("❌ Bekor", "wiz:mix:cancel"),
        ], cols=2),
    )


def on_confirm(
    ctx: HandlerCtx, *, session: TgWizardSession, text: str | None,
) -> None:
    data = ctx.callback_data or ""
    if data == "wiz:mix:cancel":
        return _cancel(ctx, session)
    if data != "wiz:mix:do":
        return

    p = session.payload
    try:
        feed_batch = _execute_task(p, user=session.user)
    except Exception as exc:  # noqa: BLE001
        logger.exception("feed_mix wizard execute failed")
        send_message(
            ctx.chat_id,
            f"❌ Не удалось провести замес: <code>{str(exc)[:300]}</code>",
        )
        session.delete()
        return

    session.delete()
    edit_message_text(
        ctx.chat_id, ctx.message_id,
        (
            f"✅ <b>Замес проведён</b>\n\n"
            f"Партия корма: <code>{feed_batch.doc_number}</code>\n"
            f"Количество: <code>{feed_batch.quantity_kg} кг</code>\n"
            f"Себест.: <code>{feed_batch.unit_cost_uzs:,} сум/кг</code>".replace(",", " ")
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


def _execute_task(payload: dict, *, user):
    from apps.feed.models import ProductionTask
    from apps.feed.services.execute_task import execute_production_task
    from apps.warehouses.models import ProductionBlock, Warehouse

    task = ProductionTask.objects.get(id=payload["task_id"])
    output_warehouse = Warehouse.objects.get(id=payload["warehouse_id"])
    storage_bin = ProductionBlock.objects.get(id=payload["bin_id"])
    actual = Decimal(payload["actual_qty"])

    res = execute_production_task(
        task,
        output_warehouse=output_warehouse,
        storage_bin=storage_bin,
        actual_quantity_kg=actual,
        user=user,
    )
    return res.feed_batch


register_wizard(WizardSpec(
    code=WIZARD_CODE,
    on_callback={
        S.TASK: on_task_picked,
        S.OUTPUT: on_output_picked,
        S.ACTUAL: on_actual_callback,
        S.CONFIRM: on_confirm,
    },
    on_message={
        S.ACTUAL: on_actual_text,
    },
))
