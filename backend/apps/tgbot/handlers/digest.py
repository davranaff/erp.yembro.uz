"""
Команды для управления подпиской на owner-digest.

  /digest      — сводка за СЕГОДНЯ (live snapshot, отвечает на «как идём?»)
  /digest_on   — включить ежедневную автодоставку
  /digest_off  — отключить

Различие с авторассылкой 08:00 (`owner_digest_task`): автотаск шлёт сводку
за ВЧЕРА (закрытый рабочий день). Интерактивный `/digest` отвечает на
вопрос «как идут дела сейчас» — поэтому смотрит на сегодняшний день.
"""
from __future__ import annotations

from django.utils import timezone

from ..dispatcher import HandlerCtx, command


@command("/digest", help="Сводка за сегодня (live)", module="reports", category="reports")
def handle_digest_preview(ctx: HandlerCtx) -> None:
    from ..services.digest import build_digest, send_digest_to

    org = ctx.org()
    today = timezone.localdate()
    data = build_digest(org, on_date=today)
    send_digest_to(ctx.chat_id, data, org_name=org.name)


@command("/digest_on", help="Включить ежедневную сводку (08:00)", module="reports", category="reports")
def handle_digest_on(ctx: HandlerCtx) -> None:
    if not ctx.link.digest_enabled:
        ctx.link.digest_enabled = True
        ctx.link.save(update_fields=["digest_enabled"])
    send_message(
        ctx.chat_id,
        "✅ Ежедневная сводка <b>включена</b>.\n"
        "Будет приходить каждое утро в 08:00 (Asia/Tashkent).",
    )


@command("/digest_off", help="Отключить ежедневную сводку", module="reports", category="reports")
def handle_digest_off(ctx: HandlerCtx) -> None:
    if ctx.link.digest_enabled:
        ctx.link.digest_enabled = False
        ctx.link.save(update_fields=["digest_enabled"])
    send_message(
        ctx.chat_id,
        "🔕 Ежедневная сводка <b>отключена</b>.\n"
        "Можно вернуть командой /digest_on или вручную дёрнуть /digest.",
    )
