"""Главное меню и роутинг подразделов через callback `home:*`."""
from __future__ import annotations

import pytest

from apps.tgbot.dispatcher import dispatch_callback, dispatch_message


pytestmark = pytest.mark.django_db


def _cbq(chat_id, data, message_id=10):
    return {
        "id": f"cbq-{data}",
        "data": data,
        "message": {"chat": {"id": chat_id}, "message_id": message_id},
    }


def test_menu_renders_4_buttons(tg_link, fake_send):
    dispatch_message({"chat": {"id": tg_link.chat_id}, "text": "/menu"})
    sent = fake_send.calls
    assert sent
    chat_id, text, markup = sent[0]
    assert chat_id == tg_link.chat_id
    assert "Главное меню" in text
    # 4 inline-кнопки → ровно 4 элемента, в 2 строки по 2.
    rows = markup["inline_keyboard"]
    flat = [btn for row in rows for btn in row]
    assert len(flat) == 4
    callbacks = {b["callback_data"] for b in flat}
    assert callbacks == {"home:fin", "home:batch", "home:prod", "home:reports"}


def test_callback_home_fin_renders_finance_submenu(tg_link, fake_send):
    dispatch_callback(_cbq(tg_link.chat_id, "home:fin"))
    # Финансовое меню рендерится через edit_message_text
    assert any("Финансы" in t for _, _, t, _ in fake_send.edits)


def test_callback_home_returns_to_main(tg_link, fake_send):
    dispatch_callback(_cbq(tg_link.chat_id, "home"))
    assert any("Главное меню" in t for _, _, t, _ in fake_send.edits)
