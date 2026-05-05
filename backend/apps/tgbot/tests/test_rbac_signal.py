"""
Тесты RBAC-signal: при добавлении/удалении прав юзера его /команды
в Telegram-popup'е автоматически обновляются (set_my_commands).
"""
from unittest.mock import patch

import pytest

from apps.modules.models import Module
from apps.organizations.models import Organization, OrganizationMembership
from apps.rbac.models import (
    AccessLevel,
    Role,
    RolePermission,
    UserModuleAccessOverride,
    UserRole,
)
from apps.tgbot.models import TgLink
from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def linked_user(org):
    """Юзер с membership в org + admin-линком в TG."""
    u = User.objects.create(email="rbac-sync@y.local", full_name="rs")
    OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True,
    )
    TgLink.objects.create(
        organization=org, user=u, chat_id=789789, is_active=True,
    )
    return u


def _set_my_commands_called_for(mock, chat_id):
    """Вернёт True если был вызов с этим chat_id."""
    return any(
        c.kwargs.get("chat_id") == chat_id for c in mock.call_args_list
    )


def test_override_save_triggers_set_my_commands(linked_user, org):
    membership = OrganizationMembership.objects.get(
        user=linked_user, organization=org,
    )
    m_sales = Module.objects.get(code="sales")

    with patch("apps.tgbot.bot.set_my_commands") as mock_smc:
        UserModuleAccessOverride.objects.create(
            membership=membership, module=m_sales,
            level=AccessLevel.READ_WRITE,
        )

    assert _set_my_commands_called_for(mock_smc, 789789), (
        "Override save должен был перезаписать setMyCommands для chat=789789"
    )


def test_override_delete_triggers_set_my_commands(linked_user, org):
    membership = OrganizationMembership.objects.get(
        user=linked_user, organization=org,
    )
    m_sales = Module.objects.get(code="sales")
    ovr = UserModuleAccessOverride.objects.create(
        membership=membership, module=m_sales, level=AccessLevel.ADMIN,
    )

    with patch("apps.tgbot.bot.set_my_commands") as mock_smc:
        ovr.delete()

    assert _set_my_commands_called_for(mock_smc, 789789), (
        "Override delete должен был перезаписать setMyCommands"
    )


def test_user_role_save_triggers_set_my_commands(linked_user, org):
    membership = OrganizationMembership.objects.get(
        user=linked_user, organization=org,
    )
    role = Role.objects.create(organization=org, code="rs-role", name="rs")
    RolePermission.objects.create(
        role=role, module=Module.objects.get(code="feed"),
        level=AccessLevel.READ,
    )

    with patch("apps.tgbot.bot.set_my_commands") as mock_smc:
        UserRole.objects.create(membership=membership, role=role)

    assert _set_my_commands_called_for(mock_smc, 789789)


def test_signal_does_not_break_when_no_links(org):
    """Юзер без TgLink — signal не падает, просто ничего не шлёт."""
    u = User.objects.create(email="no-link@y.local", full_name="nl")
    membership = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True,
    )
    m_sales = Module.objects.get(code="sales")

    with patch("apps.tgbot.bot.set_my_commands") as mock_smc:
        UserModuleAccessOverride.objects.create(
            membership=membership, module=m_sales, level=AccessLevel.READ,
        )

    # Юзера нет в TgLink → set_my_commands не должен вызываться.
    assert mock_smc.call_count == 0
