"""
Команды для управления подпиской на owner-digest.

  /digest      — preview сводки за вчера (полный текст, как пришёл бы в 08:00)
  /digest_on   — включить ежедневную автодоставку
  /digest_off  — отключить
"""
from __future__ import annotations

from ..bot import send_message
from ..dispatcher import HandlerCtx, command


@command("/digest", help="Сводка за вчера (preview)")
def handle_digest_preview(ctx: HandlerCtx) -> None:
    from ..services.digest import build_digest, format_digest

    org = ctx.org()
    data = build_digest(org)
    send_message(ctx.chat_id, format_digest(data, organization_name=org.name))


@command("/digest_on", help="Включить ежедневную сводку (08:00)")
def handle_digest_on(ctx: HandlerCtx) -> None:
    if not ctx.link.digest_enabled:
        ctx.link.digest_enabled = True
        ctx.link.save(update_fields=["digest_enabled"])
    send_message(
        ctx.chat_id,
        "✅ Ежедневная сводка <b>включена</b>.\n"
        "Будет приходить каждое утро в 08:00 (Asia/Tashkent).",
    )


@command("/digest_off", help="Отключить ежедневную сводку")
def handle_digest_off(ctx: HandlerCtx) -> None:
    if ctx.link.digest_enabled:
        ctx.link.digest_enabled = False
        ctx.link.save(update_fields=["digest_enabled"])
    send_message(
        ctx.chat_id,
        "🔕 Ежедневная сводка <b>отключена</b>.\n"
        "Можно вернуть командой /digest_on или вручную дёрнуть /digest.",
    )
