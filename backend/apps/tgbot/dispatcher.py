"""
Telegram update dispatcher с registry-подходом.

Раньше `commands.py:dispatch` был большим if/elif. Теперь:
  - команды регистрируются `@command("/sales", help="...", module="reports")`
  - callback'и регистрируются `@on_callback("fin:")` — префиксный матч
  - `dispatch_message` / `dispatch_callback` сами находят handler в реестре,
    проверяют RBAC и вызывают handler с `HandlerCtx`

Фронт-end остаётся прежним: `views.py` дёргает `dispatch(update)` (legacy
функция здесь же), которая внутри вызывает `dispatch_message` или
`dispatch_callback` в зависимости от типа update.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .bot import answer_callback_query, send_message

logger = logging.getLogger(__name__)


# ─── HandlerCtx ──────────────────────────────────────────────────────────


@dataclass
class HandlerCtx:
    """Контекст одного handler-вызова."""

    chat_id: int
    """Telegram chat_id, куда слать ответ."""

    link: Any = None
    """`TgLink` авторизованного пользователя. None для unauth-команд (/start)."""

    args: list[str] = field(default_factory=list)
    """Аргументы команды: всё после `/cmd`. Для callback — split('::') кроме prefix."""

    callback_data: str | None = None
    """Полная строка callback_data (для callback handlers)."""

    callback_id: str | None = None
    """ID callback_query — нужен чтобы answerCallbackQuery."""

    message_id: int | None = None
    """Telegram message_id — для editMessageText (in-place смена контента)."""

    def org(self):
        """Активная организация юзера. Возвращает `link.active_organization`
        или `link.organization` если переключения не было."""
        if self.link is None:
            return None
        active = getattr(self.link, "active_organization", None)
        return active or self.link.organization


Handler = Callable[[HandlerCtx], None]


# ─── Registries ──────────────────────────────────────────────────────────


@dataclass
class CommandSpec:
    name: str                    # "/sales"
    handler: Handler
    help_line: str               # «Продажи за период»
    module: str | None = None    # RBAC gate; None = публично (для /start, /help)
    private: bool = False        # если True — не показывать в setMyCommands


COMMANDS: dict[str, CommandSpec] = {}
CALLBACKS: list[tuple[str, Handler]] = []
"""Список `(prefix, handler)`. Длинные префиксы матчатся раньше — порядок
регистрации важен. Для предсказуемости сортируем по убыванию длины
непосредственно при поиске handler-а."""


def command(
    name: str,
    *,
    help: str = "",
    module: str | None = None,
    private: bool = False,
) -> Callable[[Handler], Handler]:
    """Декоратор регистрации текстовой команды."""
    def deco(fn: Handler) -> Handler:
        COMMANDS[name] = CommandSpec(
            name=name, handler=fn, help_line=help,
            module=module, private=private,
        )
        return fn
    return deco


def on_callback(prefix: str) -> Callable[[Handler], Handler]:
    """Декоратор регистрации callback_query handler-а по префиксу."""
    def deco(fn: Handler) -> Handler:
        CALLBACKS.append((prefix, fn))
        return fn
    return deco


# ─── Auth helpers ────────────────────────────────────────────────────────


def get_admin_link(chat_id: int):
    """Возвращает активный TgLink пользователя (admin-link) или None."""
    from .models import TgLink
    return (
        TgLink.objects
        .filter(chat_id=chat_id, is_active=True, user__isnull=False)
        .select_related("organization", "user", "active_organization")
        .first()
    )


def has_module_access(link, module_code: str) -> bool:
    """Проверяет доступ ≥ 'r' к модулю `module_code` для активной организации
    юзера (с учётом /org переключения)."""
    from apps.common.permissions import _effective_level, level_satisfies
    from apps.organizations.models import OrganizationMembership

    org = getattr(link, "active_organization", None) or link.organization
    membership = OrganizationMembership.objects.filter(
        organization=org, user=link.user,
    ).first()
    if membership is None:
        return False
    return level_satisfies(_effective_level(membership, module_code), "r")


# ─── Dispatchers ─────────────────────────────────────────────────────────


def dispatch(update: dict) -> None:
    """Главная точка входа. Совместимость с views.py / handle_tg_update_task."""
    try:
        if "callback_query" in update:
            dispatch_callback(update["callback_query"])
        else:
            msg = update.get("message") or update.get("edited_message")
            if msg:
                dispatch_message(msg)
    except Exception:  # noqa: BLE001
        logger.exception("dispatch failed for update %s", update.get("update_id"))


def dispatch_message(msg: dict) -> None:
    chat_id = (msg.get("chat") or {}).get("id")
    text = (msg.get("text") or "").strip()
    tg_user = msg.get("from") or {}
    if not chat_id or not text:
        return

    # Импорт legacy hook здесь, чтобы избежать circular import (handlers/menu.py
    # тоже импортирует dispatcher).
    from . import handlers  # noqa: F401  — регистрирует команды

    parts = text.split()
    cmd_name = parts[0]
    args = parts[1:]

    # /start <token> и /link <token> — особый случай: handler работает БЕЗ link.
    if cmd_name in ("/start", "/link"):
        from .handlers.linking import handle_link
        try:
            handle_link(HandlerCtx(chat_id=chat_id, args=args), tg_user=tg_user)
        except Exception:  # noqa: BLE001
            logger.exception("link handler crashed")
            send_message(chat_id, "⚠️ Ошибка обработки. Повторите позже.")
        return

    link = get_admin_link(chat_id)
    if link is None:
        send_message(
            chat_id,
            "❌ Нет доступа.\n\nПривяжите аккаунт в ERP: Настройки → Telegram.",
        )
        return

    spec = COMMANDS.get(cmd_name)
    if spec is None:
        # Неизвестная команда → /help (генерируется автоматически)
        from .handlers.help_cmd import handle_help
        handle_help(HandlerCtx(chat_id=chat_id, link=link))
        return

    if spec.module and not has_module_access(link, spec.module):
        send_message(chat_id, f"⛔ Нет доступа к модулю <b>{spec.module}</b>.")
        return

    try:
        spec.handler(HandlerCtx(chat_id=chat_id, link=link, args=args))
    except Exception:  # noqa: BLE001
        logger.exception("command %s crashed", cmd_name)
        send_message(chat_id, "⚠️ Ошибка обработки. Повторите позже.")


def dispatch_callback(cbq: dict) -> None:
    chat_id = (cbq.get("message") or {}).get("chat", {}).get("id")
    message_id = (cbq.get("message") or {}).get("message_id")
    callback_id = cbq.get("id")
    data = cbq.get("data") or ""
    if not chat_id or not callback_id:
        return

    # Telegram требует ответ за 15с. Сразу же дёргаем answerCallbackQuery
    # без текста — это убирает спиннер на кнопке у пользователя.
    answer_callback_query(callback_id)

    from . import handlers  # noqa: F401

    link = get_admin_link(chat_id)
    if link is None:
        send_message(chat_id, "❌ Сессия истекла. Привяжите аккаунт заново.")
        return

    resolved = _resolve_callback(data)
    if resolved is None:
        logger.warning("no handler for callback %r", data)
        return
    prefix, handler = resolved

    # Args = всё ПОСЛЕ matched prefix, разрезанное по `:`.
    # Раньше делали data.split(":")[1:] — это работало только для коротких
    # однотокеновых префиксов (`fin`, `home`). Для `prod:batch` оставляло
    # «batch» в args[0] → handler склеивал «batch:П-Ц-ОТК-...» и не находил
    # партию в БД («Партия batch:П-Ц-... не найдена»).
    remainder = data[len(prefix):].lstrip(":")
    args = remainder.split(":") if remainder else []

    try:
        handler(HandlerCtx(
            chat_id=chat_id,
            link=link,
            callback_data=data,
            callback_id=callback_id,
            message_id=message_id,
            args=args,
        ))
    except Exception:  # noqa: BLE001
        logger.exception("callback %s crashed", data)
        send_message(chat_id, "⚠️ Ошибка обработки. Повторите позже.")


def _resolve_callback(data: str) -> Optional[tuple[str, Handler]]:
    """Самый длинный соответствующий префикс побеждает (`fin:pnl:` > `fin:`).

    Возвращает (prefix, handler) или None — prefix нужен dispatcher'у чтобы
    правильно отрезать args (раньше отрезалось только до первого `:`,
    что ломало составные префиксы).
    """
    matches = [(p, h) for p, h in CALLBACKS if data.startswith(p)]
    if not matches:
        return None
    matches.sort(key=lambda kv: -len(kv[0]))
    return matches[0]
