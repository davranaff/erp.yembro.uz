"""
Регрессия: notify_admins_task должна корректно резолвить кому слать.

История бага: фильтр права через `role__user_roles__membership_id` падал
с FieldError (правильное имя reverse-relation у Role.assignments). В
итоге любая попытка разослать notification (закуп/продажа/платёж)
улетала в exception, ни одно сообщение не доходило.
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
from apps.tgbot.tasks import _resolve_allowed_users, notify_admins_task
from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_sales():
    return Module.objects.get(code="sales")


def _make_user(email):
    return User.objects.create(email=email, full_name=email)


def test_resolver_allows_user_with_role_assignment(org, m_sales):
    """Если у юзера право через UserRole → Role → RolePermission — он в allowed."""
    u = _make_user("with-role@y.local")
    m = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True,
    )
    role = Role.objects.create(organization=org, code="sales-r", name="sales-r")
    RolePermission.objects.create(
        role=role, module=m_sales, level=AccessLevel.READ,
    )
    UserRole.objects.create(membership=m, role=role)

    allowed = _resolve_allowed_users(
        organization_id=str(org.id),
        user_ids=[u.id],
        module_code="sales",
    )
    assert u.id in allowed


def test_resolver_allows_user_with_override(org, m_sales):
    """Override с уровнем r — пускаем."""
    u = _make_user("with-override@y.local")
    m = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True,
    )
    UserModuleAccessOverride.objects.create(
        membership=m, module=m_sales, level=AccessLevel.READ,
    )
    allowed = _resolve_allowed_users(
        organization_id=str(org.id),
        user_ids=[u.id],
        module_code="sales",
    )
    assert u.id in allowed


def test_resolver_blocks_user_without_module_access(org, m_sales):
    """Без override и без role-permission — не пускаем."""
    u = _make_user("noaccess@y.local")
    OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True,
    )
    allowed = _resolve_allowed_users(
        organization_id=str(org.id),
        user_ids=[u.id],
        module_code="sales",
    )
    assert u.id not in allowed


def test_notify_admins_task_sends_to_users_with_module_access(org, m_sales):
    """End-to-end: notify_admins_task шлёт send_message только тем у кого
    есть TgLink + право >= r на модуль. Раньше падал с FieldError."""
    # Юзер 1: имеет доступ к sales + TgLink → должен получить
    u_yes = _make_user("yes@y.local")
    m = OrganizationMembership.objects.create(
        user=u_yes, organization=org, is_active=True,
    )
    UserModuleAccessOverride.objects.create(
        membership=m, module=m_sales, level=AccessLevel.READ,
    )
    TgLink.objects.create(
        organization=org, user=u_yes, chat_id=1001, is_active=True,
    )
    # Юзер 2: TgLink есть, доступа к sales нет → не получит
    u_no = _make_user("no@y.local")
    OrganizationMembership.objects.create(
        user=u_no, organization=org, is_active=True,
    )
    TgLink.objects.create(
        organization=org, user=u_no, chat_id=1002, is_active=True,
    )

    with patch("apps.tgbot.bot.send_message") as mock_send:
        mock_send.return_value = True
        result = notify_admins_task(
            "test message", str(org.id), "sales",
        )

    assert result == {"sent": 1}
    sent_chat_ids = {c.args[0] for c in mock_send.call_args_list}
    assert sent_chat_ids == {1001}
