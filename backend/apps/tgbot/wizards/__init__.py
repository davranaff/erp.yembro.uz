"""
Multi-step wizard'ы для бота — пакет.

Каждый wizard — отдельный модуль (e.g. `feed_purchase.py`) который
регистрирует себя через `register_wizard()`. Dispatcher проверяет
наличие активной `TgWizardSession` для chat_id ПЕРЕД command-routing'ом
и направляет ввод (текст или callback) в соответствующий handler.

Контракт wizard-handler:
    fn(ctx: HandlerCtx, *, session: TgWizardSession, text: str | None) -> None

`text` заполнен только для message-handlers (state ждёт ввода).
Для callback-handler'ов callback_data доступна через `ctx.callback_data`.
Wizard вызывает `session.advance(state=..., payload_update=...)` при
переходе на следующий шаг и `session.delete()` при завершении.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ..dispatcher import HandlerCtx


WizardHandler = Callable[..., None]


@dataclass
class WizardSpec:
    code: str
    """Уникальный код wizard'а — `feed_purchase`, `feed_writeoff`, etc."""
    on_callback: dict[str, WizardHandler] = field(default_factory=dict)
    """state → handler для callback-кнопок."""
    on_message: dict[str, WizardHandler] = field(default_factory=dict)
    """state → handler для текстового ввода. Только указанные state'ы
    «ждут ввода» — все остальные state'ы реагируют только на callback."""

    @property
    def awaits_text_states(self) -> set[str]:
        return set(self.on_message.keys())


WIZARDS: dict[str, WizardSpec] = {}


def register_wizard(spec: WizardSpec) -> WizardSpec:
    """Идемпотентная регистрация. Повторный вызов с тем же code обновляет."""
    WIZARDS[spec.code] = spec
    return spec


def get_wizard(code: str) -> WizardSpec | None:
    return WIZARDS.get(code)


# ─── Helpers used by both wizards and dispatcher ──────────────────────────


def cancel_wizard(session) -> None:
    """Удалить session — wizard прерван."""
    session.delete()


__all__ = [
    "HandlerCtx",
    "WizardHandler",
    "WizardSpec",
    "WIZARDS",
    "register_wizard",
    "get_wizard",
    "cancel_wizard",
]
