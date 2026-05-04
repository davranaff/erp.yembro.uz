"""
/org switcher: юзер с 2 memberships → переключение active_organization →
все команды смотрят на новую org.
"""
from __future__ import annotations

import pytest

from apps.modules.models import Module
from apps.organizations.models import Organization, OrganizationMembership
from apps.rbac.models import AccessLevel, UserModuleAccessOverride
from apps.tgbot.dispatcher import dispatch_callback, dispatch_message


pytestmark = pytest.mark.django_db


def _msg(chat_id, text):
    return {"chat": {"id": chat_id}, "text": text, "from": {"id": chat_id}}


def _cbq(chat_id, data, message_id=10):
    return {
        "id": f"cbq-{data}",
        "data": data,
        "message": {"chat": {"id": chat_id}, "message_id": message_id},
    }


@pytest.fixture
def second_org(db, owner_user):
    org_b = Organization.objects.create(
        code="ORG-B-TG", name="Орг Б",
        accounting_currency=Organization.objects.get(code="DEFAULT").accounting_currency,
    )
    membership_b = OrganizationMembership.objects.create(
        user=owner_user, organization=org_b, is_active=True,
    )
    UserModuleAccessOverride.objects.create(
        membership=membership_b,
        module=Module.objects.get(code="reports"),
        level=AccessLevel.READ,
    )
    return org_b


def test_org_command_lists_orgs(tg_link, second_org, fake_send):
    dispatch_message(_msg(tg_link.chat_id, "/org"))
    text = fake_send.calls[0][1]
    assert "Выберите организацию" in text


def test_org_set_callback_switches_active(tg_link, second_org, fake_send):
    dispatch_callback(_cbq(tg_link.chat_id, f"org:set:{second_org.id}"))
    tg_link.refresh_from_db()
    assert tg_link.active_organization_id == second_org.id


def test_command_uses_active_org_after_switch(tg_link, second_org, fake_send, org):
    """После /org switch к second_org — /cash должен брать данные из second_org."""
    # До switch — active = DEFAULT (через fallback)
    dispatch_message(_msg(tg_link.chat_id, "/cash"))
    fake_send.calls.clear()

    # Switch
    dispatch_callback(_cbq(tg_link.chat_id, f"org:set:{second_org.id}"))
    fake_send.calls.clear()

    # Cash должен запрашивать second_org. Раз там нет платежей — итого = 0.
    dispatch_message(_msg(tg_link.chat_id, "/cash"))
    text = fake_send.calls[0][1]
    assert "Касса и банк" in text
    # Sanity: tg_link обновлён
    tg_link.refresh_from_db()
    assert tg_link.active_organization_id == second_org.id


def test_org_set_foreign_org_rejected(tg_link, fake_send):
    """callback с org_id, к которой у юзера нет membership → отказ."""
    foreign = Organization.objects.create(
        code="FOREIGN-TG", name="Чужая",
        accounting_currency=Organization.objects.get(code="DEFAULT").accounting_currency,
    )
    dispatch_callback(_cbq(tg_link.chat_id, f"org:set:{foreign.id}"))
    text = fake_send.calls[0][1]
    assert "нет доступа" in text.lower()
    tg_link.refresh_from_db()
    assert tg_link.active_organization_id is None
