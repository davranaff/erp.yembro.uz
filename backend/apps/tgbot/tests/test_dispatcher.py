"""
Базовые тесты dispatcher: routing message + callback_query, auth gate,
fallback на /help для unknown.
"""
from __future__ import annotations

import pytest

from apps.tgbot.dispatcher import dispatch, dispatch_callback, dispatch_message


pytestmark = pytest.mark.django_db


def _msg(chat_id: int, text: str) -> dict:
    return {"chat": {"id": chat_id}, "text": text, "from": {"id": chat_id}}


def test_unauth_user_gets_link_prompt(fake_send):
    # chat_id 99999 — нет TgLink
    dispatch_message(_msg(99999, "/menu"))
    assert any("Привяжите аккаунт" in t for _, t, _ in fake_send.calls)


def test_known_command_dispatched(tg_link, fake_send):
    dispatch_message(_msg(tg_link.chat_id, "/menu"))
    # /menu рендерит главное меню (на узбекском после Phase B1)
    assert any("Asosiy menyu" in t for _, t, _ in fake_send.calls)


def test_unknown_command_falls_to_help(tg_link, fake_send):
    dispatch_message(_msg(tg_link.chat_id, "/qwerty_unknown"))
    assert any("Yembro ERP Bot" in t for _, t, _ in fake_send.calls)


def test_module_gate_blocks_command(tg_link, fake_send):
    """Юзер без feedlot-доступа → /feedlot вернёт 'Нет доступа'."""
    from apps.modules.models import Module
    from apps.rbac.models import UserModuleAccessOverride
    UserModuleAccessOverride.objects.filter(
        membership__user=tg_link.user,
        module=Module.objects.get(code="feedlot"),
    ).delete()
    dispatch_message(_msg(tg_link.chat_id, "/feedlot"))
    assert any("Нет доступа" in t for _, t, _ in fake_send.calls)


def test_dispatch_routes_callback_query(tg_link, fake_send):
    """update с callback_query идёт в dispatch_callback и answer_callback_query."""
    update = {
        "callback_query": {
            "id": "cbq-123",
            "data": "home",
            "from": {"id": tg_link.chat_id},
            "message": {
                "chat": {"id": tg_link.chat_id},
                "message_id": 42,
            },
        },
    }
    dispatch(update)
    # answerCallbackQuery должен был дёрнуться чтобы убрать спиннер
    assert fake_send.callbacks
    # И главное меню — отредактировано in-place (узбекский после Phase B1)
    assert any("Asosiy menyu" in t for _, _, t, _ in fake_send.edits)


def test_callback_unauth_user_silenced(fake_send):
    """callback от unauth юзера не падает, но и не редактирует чужое сообщение."""
    update = {
        "callback_query": {
            "id": "cbq-x",
            "data": "home:fin",
            "message": {"chat": {"id": 88888}, "message_id": 1},
        },
    }
    dispatch(update)
    # answer_callback_query всё равно дёрнут (закрываем спиннер на стороне TG),
    # но потом отправлено сообщение «Сессия истекла»
    assert any("Сессия истекла" in t for _, t, _ in fake_send.calls)


def test_dispatch_swallows_handler_crash(tg_link, fake_send):
    """Если handler упал — пользователь получит «Ошибка», не stack trace.

    Подменяем handler прямо в реестре — patch на module-attr не сработает,
    т.к. dispatcher хранит ссылку на функцию в `CommandSpec`.
    """
    from apps.tgbot.dispatcher import COMMANDS

    def _boom(ctx):
        raise RuntimeError("boom")

    spec = COMMANDS["/help"]
    original = spec.handler
    spec.handler = _boom
    try:
        dispatch_message(_msg(tg_link.chat_id, "/help"))
    finally:
        spec.handler = original
    assert any("Ошибка обработки" in t for _, t, _ in fake_send.calls)
