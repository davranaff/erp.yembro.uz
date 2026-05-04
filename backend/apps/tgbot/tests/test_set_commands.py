"""
Management команда tg_set_commands → Telegram setMyCommands API.
"""
from __future__ import annotations

from io import StringIO
from unittest.mock import patch

import pytest

from django.core.management import call_command


@pytest.mark.django_db
def test_set_commands_posts_payload():
    """Mock-ируем requests.post чтобы не звонить в Telegram реально."""
    with patch("apps.tgbot.bot.requests.post") as mock_post:
        mock_post.return_value.ok = True
        mock_post.return_value.json.return_value = {"ok": True}
        with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "test-token"}):
            from django.conf import settings
            settings.TELEGRAM_BOT_TOKEN = "test-token"
            out = StringIO()
            call_command("tg_set_commands", stdout=out)

    # Hit `setMyCommands` endpoint exactly once
    assert mock_post.call_count == 1
    url = mock_post.call_args[0][0]
    payload = mock_post.call_args[1]["json"]
    assert "setMyCommands" in url
    # Должны быть как минимум /menu /help /cash /pnl /sales (публичные)
    cmds = {c["command"] for c in payload["commands"]}
    assert "menu" in cmds
    assert "help" in cmds
    assert "cash" in cmds
    assert "pnl" in cmds
    assert "sales" in cmds
    # Legacy /report /balance /stock /cashflow /production — private, скрыты
    assert "report" not in cmds
    assert "balance" not in cmds
    assert "stock" not in cmds
    assert "cashflow" not in cmds
    assert "production" not in cmds

    output = out.getvalue()
    assert "ok" in output.lower()


@pytest.mark.django_db
def test_set_commands_handles_no_token():
    """Без токена API call не делается — но команда не падает."""
    from django.conf import settings
    settings.TELEGRAM_BOT_TOKEN = ""
    out = StringIO()
    call_command("tg_set_commands", stdout=out)
    output = out.getvalue()
    # Сообщение об ошибке должно быть.
    assert "не удалось" in output.lower() or "fail" in output.lower()
