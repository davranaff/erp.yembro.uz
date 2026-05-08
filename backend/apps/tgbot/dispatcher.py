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
    audience: str = "admin"      # "admin" | "counterparty" | "any"
    category: str = "misc"       # см. apps.tgbot.categories — для группировки в /help


COMMANDS: dict[str, CommandSpec] = {}
CALLBACKS: list[tuple[str, Handler]] = []

# Reply-клавиатура шлёт текст кнопки. Здесь маппим эти тексты в /команды
# чтобы dispatch работал единообразно. Каждый handler-модуль может
# дописать сюда свои кнопки через update().
TEXT_TO_COMMAND: dict[str, str] = {}
"""Список `(prefix, handler)`. Длинные префиксы матчатся раньше — порядок
регистрации важен. Для предсказуемости сортируем по убыванию длины
непосредственно при поиске handler-а."""


def command(
    name: str,
    *,
    help: str = "",
    module: str | None = None,
    private: bool = False,
    audience: str = "admin",
    category: str | None = None,
) -> Callable[[Handler], Handler]:
    """Декоратор регистрации текстовой команды.

    ``audience``:
      - "admin"        (default): доступно только для user-link (RBAC по module).
      - "counterparty": доступно только для counterparty-link (клиент-кабинет).
      - "any"          : доступно обоим типам (например /menu, /help).

    ``category``:
      Явная категория для группировки в /help. Если не задана, резолвится
      автоматом из module (см. apps.tgbot.categories.MODULE_TO_CATEGORY).
    """
    def deco(fn: Handler) -> Handler:
        from .categories import resolve_category
        resolved_category = resolve_category(
            explicit=category, module=module, audience=audience,
        )
        COMMANDS[name] = CommandSpec(
            name=name, handler=fn, help_line=help,
            module=module, private=private, audience=audience,
            category=resolved_category,
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


def get_counterparty_link(chat_id: int):
    """Возвращает активный TgLink контрагента (cp-link) или None.

    Counterparty-линки используются клиентами для self-service кабинета:
    свои заказы, долги, статус блокировки. Dispatcher ищет их когда
    admin-link не найден — благодаря XOR-constraint на TgLink один chat
    одновременно либо admin, либо cp в одной org.
    """
    from .models import TgLink
    return (
        TgLink.objects
        .filter(chat_id=chat_id, is_active=True, counterparty__isnull=False)
        .select_related("organization", "counterparty")
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

    # Text-button mapping: reply-клавиатура шлёт текст кнопки (без слеша).
    # Преобразуем известные тексты в /команды чтобы handler dispatch работал
    # одинаково. Если текст не совпадает — оставляем как есть (попадёт в
    # /help как unknown command).
    cmd_from_text = TEXT_TO_COMMAND.get(text.strip())
    if cmd_from_text:
        text = cmd_from_text

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

    # Сначала ищем admin-link (сотрудник), потом counterparty-link (клиент).
    # XOR-constraint на TgLink (organization, chat_id) гарантирует что в
    # одной org один chat — это либо admin, либо cp, не оба.
    link = get_admin_link(chat_id)
    is_counterparty = False
    if link is None:
        link = get_counterparty_link(chat_id)
        is_counterparty = link is not None

    if link is None:
        send_message(
            chat_id,
            "❌ Akkaunt bog'lanmagan.\n\nERP'da bog'lang: Sozlamalar → Telegram.",
        )
        return

    # Wizard-перехват: если у пользователя есть активная wizard-сессия и
    # текущий state ждёт текст-ввод — направляем сообщение туда. Команды
    # с / всё ещё имеют приоритет: `/cancel` отменяет wizard, любая другая
    # команда тоже прерывает (новый command-flow явно).
    if not is_counterparty and not text.startswith("/"):
        if _try_route_wizard_message(
            HandlerCtx(chat_id=chat_id, link=link), text=text,
        ):
            return

    spec = COMMANDS.get(cmd_name)
    if spec is None:
        # Неизвестная команда → /help
        from .handlers.help_cmd import handle_help
        handle_help(HandlerCtx(chat_id=chat_id, link=link))
        return

    # Audience-gate: counterparty не может звать admin-команды и наоборот.
    audience = getattr(spec, "audience", "admin")
    if audience == "admin" and is_counterparty:
        send_message(chat_id, "⛔ Bu buyruq xodimlar uchun.")
        return
    if audience == "counterparty" and not is_counterparty:
        send_message(chat_id, "⛔ Bu buyruq mijozlar uchun.")
        return

    # RBAC-gate (только для admin-link, у counterparty нет module-доступов).
    if not is_counterparty and spec.module and not has_module_access(link, spec.module):
        send_message(chat_id, f"⛔ Modulga ruxsat yo'q: <b>{spec.module}</b>.")
        return

    try:
        spec.handler(HandlerCtx(chat_id=chat_id, link=link, args=args))
    except Exception:  # noqa: BLE001
        logger.exception("command %s crashed", cmd_name)
        send_message(chat_id, "⚠️ Xatolik yuz berdi. Keyinroq qayta urinib ko'ring.")


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
    from . import wizards  # noqa: F401  — регистрирует wizard-handlers

    link = get_admin_link(chat_id) or get_counterparty_link(chat_id)
    if link is None:
        send_message(chat_id, "❌ Sessiya tugadi. Akkauntni qaytadan bog'lang.")
        return

    # Callback'и wizard'ов идут с префиксом `wiz:<wizard_code>:...`. Если
    # есть активная session — direct route в её handler (по state).
    if data.startswith("wiz:"):
        if _try_route_wizard_callback(
            HandlerCtx(
                chat_id=chat_id, link=link, callback_data=data,
                callback_id=callback_id, message_id=message_id,
            ),
            data=data,
        ):
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


def _try_route_wizard_message(ctx: HandlerCtx, *, text: str) -> bool:
    """Возвращает True если сообщение поглощено wizard-handler'ом."""
    from .models import TgWizardSession
    from .wizards import get_wizard

    session = TgWizardSession.get_active(ctx.chat_id)
    if session is None:
        return False
    wizard = get_wizard(session.wizard)
    if wizard is None:
        # Сессия ссылается на исчезнувший wizard — чистим, ничего не делаем.
        session.delete()
        return False
    handler = wizard.on_message.get(session.state)
    if handler is None:
        return False
    try:
        handler(ctx, session=session, text=text)
    except Exception:  # noqa: BLE001
        logger.exception("wizard %s state=%s message handler crashed",
                         session.wizard, session.state)
        send_message(ctx.chat_id, "⚠️ Xatolik yuz berdi. /bekor — отменить.")
    return True


def _try_route_wizard_callback(ctx: HandlerCtx, *, data: str) -> bool:
    """Возвращает True если callback поглощён wizard'ом."""
    from .models import TgWizardSession
    from .wizards import get_wizard

    session = TgWizardSession.get_active(ctx.chat_id)
    if session is None:
        send_message(
            ctx.chat_id,
            "Sessiya muddati o'tdi. Buyrug'ni qayta ishga tushiring.",
        )
        return True
    wizard = get_wizard(session.wizard)
    if wizard is None:
        session.delete()
        return False
    handler = wizard.on_callback.get(session.state)
    if handler is None:
        # Поведение «непривязанный callback» — игнорируем, но не пропускаем
        # дальше (чтобы не дёрнуть какой-нибудь home:fin).
        logger.warning(
            "wizard %s state=%s has no callback handler for %r",
            session.wizard, session.state, data,
        )
        return True
    try:
        handler(ctx, session=session, text=None)
    except Exception:  # noqa: BLE001
        logger.exception("wizard %s state=%s callback handler crashed",
                         session.wizard, session.state)
        send_message(ctx.chat_id, "⚠️ Xatolik yuz berdi. /bekor — отменить.")
    return True


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
