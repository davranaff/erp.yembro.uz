"""
Back-compat shim для старого `from apps.tgbot.commands import dispatch`.

Реальная логика — в `apps.tgbot.dispatcher` (registry-based) и
`apps.tgbot.handlers.*` (по разделам). Файл оставлен чтобы не ломать
старые импорты в `tasks.handle_tg_update_task`, тестах, документации.
"""
from __future__ import annotations

from .dispatcher import (
    CALLBACKS,
    COMMANDS,
    HandlerCtx,
    command,
    dispatch,
    dispatch_callback,
    dispatch_message,
    get_admin_link,
    has_module_access,
    on_callback,
)

# Алиасы для самых ранних импортов (приватные имена с подчёркиванием).
_get_admin_link = get_admin_link
_has_module_access = has_module_access

__all__ = [
    "CALLBACKS",
    "COMMANDS",
    "HandlerCtx",
    "command",
    "dispatch",
    "dispatch_callback",
    "dispatch_message",
    "get_admin_link",
    "has_module_access",
    "on_callback",
    "_get_admin_link",
    "_has_module_access",
]
