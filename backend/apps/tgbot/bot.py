"""
Низкоуровневые обёртки над Telegram Bot API.

Все функции возвращают bool/dict/None — не бросают исключения. Если token не
задан или сеть упала — логируем warning и возвращаем False/None. Это позволяет
команде / digest-таске пройти атомарно, даже если TG временно недоступен.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def _api_url(method: str) -> Optional[str]:
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set — skip %s", method)
        return None
    return f"https://api.telegram.org/bot{token}/{method}"


def _post(method: str, payload: dict) -> Optional[dict]:
    url = _api_url(method)
    if url is None:
        return None
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if not resp.ok:
            logger.warning(
                "Telegram %s failed: %s %s",
                method, resp.status_code, resp.text[:300],
            )
            return None
        return resp.json()
    except requests.RequestException as exc:
        logger.error("Telegram %s error: %s", method, exc)
        return None


def send_message(
    chat_id: int,
    text: str,
    parse_mode: str = "HTML",
    reply_markup: Optional[dict] = None,
) -> bool:
    """POST /sendMessage. `reply_markup` — InlineKeyboardMarkup dict (см. keyboards.py)."""
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if reply_markup is not None:
        # Telegram принимает reply_markup как JSON-строку, но через POST JSON
        # тоже понимает вложенный объект. Передаём как dict — проще.
        payload["reply_markup"] = reply_markup
    return _post("sendMessage", payload) is not None


def answer_callback_query(
    callback_query_id: str,
    text: Optional[str] = None,
    show_alert: bool = False,
) -> bool:
    """POST /answerCallbackQuery. Обязательно ответить за 15с, иначе Telegram
    показывает спиннер на кнопке. `text` опционален: короткий toast 200 chars max."""
    payload: dict[str, Any] = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text[:200]
        payload["show_alert"] = bool(show_alert)
    return _post("answerCallbackQuery", payload) is not None


def edit_message_text(
    chat_id: int,
    message_id: int,
    text: str,
    parse_mode: str = "HTML",
    reply_markup: Optional[dict] = None,
) -> bool:
    """POST /editMessageText. Используется для in-place смены контента
    (например при переключении периода в /pnl: чат не плодится)."""
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return _post("editMessageText", payload) is not None


def set_my_commands(commands: list[dict]) -> bool:
    """POST /setMyCommands. `commands` — список {"command": str, "description": str}."""
    return _post("setMyCommands", {"commands": commands}) is not None


# Process-local кеш юзернейма бота. getMe ходит в Telegram API, и не имеет
# смысла дёргать его на каждый запрос — username бота меняется не чаще
# чем раз в год при ребрендинге.
_BOT_USERNAME_CACHE: Optional[str] = None


def get_bot_username() -> Optional[str]:
    """Возвращает @username бота для построения deep-link.

    Приоритет источников:
        1. settings.TELEGRAM_BOT_USERNAME (если задан в env — fast-path,
           без сетевого запроса; полезно в офлайн-тестах и dev-окружении)
        2. Telegram getMe API (cached in-process)

    Возвращает `None` если token не задан или getMe упал. В этом случае
    серилизатор/UI должен показать понятную ошибку «бот не настроен»
    вместо ломаной ссылки `https://t.me/?start=...`.
    """
    global _BOT_USERNAME_CACHE

    explicit = getattr(settings, "TELEGRAM_BOT_USERNAME", "")
    if explicit:
        return explicit

    if _BOT_USERNAME_CACHE:
        return _BOT_USERNAME_CACHE

    payload = _post("getMe", {})
    if payload is None:
        return None
    username = (payload.get("result") or {}).get("username")
    if username:
        _BOT_USERNAME_CACHE = username
        return username
    return None


def reset_bot_username_cache() -> None:
    """Сбросить кеш юзернейма (для тестов и при смене токена)."""
    global _BOT_USERNAME_CACHE
    _BOT_USERNAME_CACHE = None
