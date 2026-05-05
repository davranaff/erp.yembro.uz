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
    # owner_user (conftest) даёт доступ к reports/feedlot/matочник/admin/ledger →
    # видит как минимум fin (через ledger) + batch + prod + reports.
    assert "Asosiy menyu" in text
    rows = markup["inline_keyboard"]
    flat = [btn for row in rows for btn in row]
    callbacks = {b["callback_data"] for b in flat}
    # admin модуль входит в owner_user'а override → owner → видит все 4.
    assert "home:fin" in callbacks
    assert "home:batch" in callbacks
    assert "home:prod" in callbacks
    assert "home:reports" in callbacks


def test_callback_home_fin_renders_finance_submenu(tg_link, fake_send):
    dispatch_callback(_cbq(tg_link.chat_id, "home:fin"))
    # Финансовое подменю на узбекском после Phase B1.
    assert any("Moliya" in t for _, _, t, _ in fake_send.edits)


def test_callback_home_returns_to_main(tg_link, fake_send):
    dispatch_callback(_cbq(tg_link.chat_id, "home"))
    assert any("Asosiy menyu" in t for _, _, t, _ in fake_send.edits)
