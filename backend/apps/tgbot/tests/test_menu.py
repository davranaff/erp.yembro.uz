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


def test_menu_renders_buttons_for_owner(tg_link, fake_send):
    dispatch_message({"chat": {"id": tg_link.chat_id}, "text": "/menu"})
    sent = fake_send.calls
    assert sent
    chat_id, text, markup = sent[0]
    assert chat_id == tg_link.chat_id
    assert "Asosiy menyu" in text
    rows = markup["inline_keyboard"]
    flat = [btn for row in rows for btn in row]
    callbacks = {b["callback_data"] for b in flat}
    # Плоское меню после рефактора: финансовые подразделы поднялись
    # на верхний уровень + 2 кнопки скачивания Excel. Modullar и
    # Hisobotlar убраны.
    assert "fin:cash" in callbacks
    assert "fin:debt" in callbacks
    assert "fin:cred" in callbacks
    assert "fin:pnl:week" in callbacks
    assert "fin:sales:week" in callbacks
    assert "fin:stock" in callbacks
    assert "dl:debtors" in callbacks
    assert "dl:stock" in callbacks
    # Удалённые группировки
    assert "home:modules" not in callbacks
    assert "home:reports" not in callbacks
    assert "home:fin" not in callbacks


def test_callback_home_fin_renders_finance_submenu(tg_link, fake_send):
    """Legacy callback home:fin — оставлен для старых сообщений со
    старыми inline-кнопками. Должен открыть финансовое подменю."""
    dispatch_callback(_cbq(tg_link.chat_id, "home:fin"))
    # Финансовое подменю на узбекском после Phase B1.
    assert any("Moliya" in t for _, _, t, _ in fake_send.edits)


def test_callback_home_returns_to_main(tg_link, fake_send):
    dispatch_callback(_cbq(tg_link.chat_id, "home"))
    assert any("Asosiy menyu" in t for _, _, t, _ in fake_send.edits)
