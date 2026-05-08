"""
Глобальные команды для управления wizard-сессией.

  /bekor   — отменить активный wizard и удалить сессию.
"""
from __future__ import annotations

from ..bot import send_message
from ..dispatcher import HandlerCtx, command


@command("/bekor", help="Отменить текущий wizard", audience="any")
def handle_cancel_wizard(ctx: HandlerCtx) -> None:
    from ..models import TgWizardSession

    session = TgWizardSession.objects.filter(chat_id=ctx.chat_id).first()
    if session is None:
        send_message(ctx.chat_id, "Активный wizard не найден.")
        return
    session.delete()
    send_message(ctx.chat_id, "❌ Wizard отменён.")
