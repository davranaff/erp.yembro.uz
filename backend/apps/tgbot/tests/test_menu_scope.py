"""
Тесты RBAC-фильтрации меню: head feed-модуля видит только feed-разделы,
owner — все, юзер без прав — пустое меню (только help-fallback).
"""
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
from apps.tgbot.services.menu_scope import (
    can_see_section,
    commands_for_counterparty,
    commands_for_user,
    is_owner,
    user_module_levels,
)
from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


def _link_with_overrides(org, email, modules_levels):
    """user → membership → overrides → TgLink. Возвращает TgLink."""
    u = User.objects.create(email=email, full_name=email)
    m = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True,
    )
    for code, level in modules_levels.items():
        UserModuleAccessOverride.objects.create(
            membership=m, module=Module.objects.get(code=code), level=level,
        )
    return TgLink.objects.create(
        organization=org, user=u, chat_id=hash(email) % 1_000_000,
        is_active=True,
    )


def test_owner_sees_all_sections(org):
    link = _link_with_overrides(org, "owner@y.local", {"admin": AccessLevel.ADMIN})
    levels = user_module_levels(link)
    assert is_owner(levels) is True
    for section in ["fin", "batch", "prod", "reports"]:
        assert can_see_section(levels, section) is True


def test_feed_head_sees_only_production(org):
    link = _link_with_overrides(org, "feed-head@y.local", {"feed": AccessLevel.ADMIN})
    levels = user_module_levels(link)
    assert is_owner(levels) is False
    # feed входит в 'modules' раздел; 'reports' тоже включает feed (per-module
    # аналитика), 'fin' нет (sales/purchases/payments/ledger).
    assert can_see_section(levels, "modules") is True
    assert can_see_section(levels, "reports") is True
    assert can_see_section(levels, "fin") is False


def test_sales_manager_sees_fin_and_reports(org):
    link = _link_with_overrides(
        org, "sales-mgr@y.local", {"sales": AccessLevel.READ_WRITE},
    )
    levels = user_module_levels(link)
    assert can_see_section(levels, "fin") is True       # sales входит
    assert can_see_section(levels, "reports") is True   # sales тоже reports gate
    assert can_see_section(levels, "modules") is False  # production-модулей нет


def test_user_with_role_assignment_inherits_levels(org):
    """RolePermission через UserRole тоже учитывается."""
    u = User.objects.create(email="role-user@y.local", full_name="r")
    m = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True,
    )
    role = Role.objects.create(organization=org, code="warehouse-mgr", name="Warehouse")
    RolePermission.objects.create(
        role=role, module=Module.objects.get(code="feedlot"),
        level=AccessLevel.READ,
    )
    UserRole.objects.create(membership=m, role=role)
    link = TgLink.objects.create(
        organization=org, user=u, chat_id=22222, is_active=True,
    )

    levels = user_module_levels(link)
    assert levels.get("feedlot") == AccessLevel.READ
    # feedlot входит в 'modules' и в 'reports' (per-module аналитика)
    assert can_see_section(levels, "modules") is True
    assert can_see_section(levels, "fin") is False


def test_user_without_membership_gets_empty_levels(org):
    u = User.objects.create(email="no-member@y.local", full_name="x")
    link = TgLink.objects.create(
        organization=org, user=u, chat_id=33333, is_active=True,
    )
    assert user_module_levels(link) == {}


def test_commands_for_user_owner_sees_all():
    levels = {"admin": AccessLevel.ADMIN}
    cmds = commands_for_user(levels)
    cmd_names = [c["command"] for c in cmds]
    # Owner видит и /pnl, и /cash, и /feedlot
    assert "menu" in cmd_names
    assert "pnl" in cmd_names
    assert "feedlot" in cmd_names
    assert "debt" in cmd_names


def test_commands_for_user_feed_only():
    levels = {"feed": AccessLevel.ADMIN}
    cmds = commands_for_user(levels)
    cmd_names = [c["command"] for c in cmds]
    # Безусловные есть
    assert "menu" in cmd_names
    assert "help" in cmd_names
    # PnL/cash требуют reports/ledger — не дано
    assert "pnl" not in cmd_names
    assert "cash" not in cmd_names
    assert "debt" not in cmd_names
    # /feedlot требует feedlot — не дано
    assert "feedlot" not in cmd_names


def test_commands_for_counterparty_uzbek():
    cmds = commands_for_counterparty()
    cmd_names = [c["command"] for c in cmds]
    assert "buyurtmalar" in cmd_names
    assert "qarz" in cmd_names
    assert "holat" in cmd_names
    # И описания на узбекском
    descriptions = " ".join(c["description"] for c in cmds)
    assert "buyurtmalar" in descriptions.lower() or "Mening" in descriptions
