"""
Общие фикстуры для tgbot-тестов: org, owner-пользователь с RBAC ко всем
нужным модулям, привязанный TgLink, mock send_message.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.modules.models import Module
from apps.organizations.models import Organization, OrganizationMembership
from apps.rbac.models import AccessLevel, UserModuleAccessOverride
from apps.tgbot.models import TgLink
from apps.users.models import User


@pytest.fixture
def org(db):
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def owner_user(db, org):
    """Полноправный owner: reports.admin + feedlot.admin + matочник.admin + admin.admin."""
    u = User.objects.create(email="owner@y.local", full_name="Owner")
    membership = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True,
    )
    for code in ("reports", "feedlot", "matochnik", "admin", "ledger"):
        UserModuleAccessOverride.objects.create(
            membership=membership,
            module=Module.objects.get(code=code),
            level=AccessLevel.ADMIN,
        )
    return u


@pytest.fixture
def tg_link(db, org, owner_user):
    return TgLink.objects.create(
        organization=org,
        user=owner_user,
        chat_id=11111,
        is_active=True,
    )


@pytest.fixture
def fake_send():
    """Mock send_message + edit_message_text — capture все исходящие.

    `fake_send.calls` — список (chat_id, text, reply_markup) для send.
    `fake_send.edits` — список (chat_id, message_id, text, reply_markup) для edit.
    `fake_send.callbacks` — answer_callback_query вызовы.
    """
    class Fake:
        def __init__(self):
            self.calls = []
            self.edits = []
            self.callbacks = []

        def send(self, chat_id, text, parse_mode="HTML", reply_markup=None):
            self.calls.append((chat_id, text, reply_markup))
            return True

        def edit(self, chat_id, message_id, text, parse_mode="HTML", reply_markup=None):
            self.edits.append((chat_id, message_id, text, reply_markup))
            return True

        def answer_cb(self, callback_query_id, text=None, show_alert=False):
            self.callbacks.append((callback_query_id, text))
            return True

        def all_text(self) -> str:
            """Конкатенация всех отправленных текстов — удобно для assert in."""
            return "\n".join(t for _, t, _ in self.calls + [
                (c, t, m) for c, _, t, m in self.edits
            ])

    fake = Fake()
    with patch("apps.tgbot.bot.send_message", side_effect=fake.send), \
         patch("apps.tgbot.bot.edit_message_text", side_effect=fake.edit), \
         patch("apps.tgbot.bot.answer_callback_query", side_effect=fake.answer_cb):
        # Также патчим re-export-ы внутри handler'ов (они уже импортнули
        # имена в namespace модуля).
        from apps.tgbot import dispatcher as _disp
        from apps.tgbot.handlers import (
            menu as _menu,
            finance as _fin,
            production as _prod,
            reports as _rep,
            org as _org,
            help_cmd as _help,
            legacy as _leg,
            linking as _link,
            digest as _dig,
            counterparty as _cp,
            modules_hub as _mod_hub,
            wizard_cmds as _wc,
        )
        from apps.tgbot.wizards import (
            feed_mix as _wmx,
            feed_purchase as _wp,
            feed_writeoff as _wwo,
        )
        for mod in (
            _disp, _menu, _fin, _prod, _rep, _org, _help, _leg, _link,
            _dig, _cp, _mod_hub, _wc, _wp, _wwo, _wmx,
        ):
            if hasattr(mod, "send_message"):
                mod.send_message = fake.send
            if hasattr(mod, "edit_message_text"):
                mod.edit_message_text = fake.edit
            if hasattr(mod, "answer_callback_query"):
                mod.answer_callback_query = fake.answer_cb
        yield fake
