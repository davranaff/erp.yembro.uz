"""
Тесты management-команды `revoke_module_access`.

Покрытые кейсы:
  - dry-run (default) ничего не записывает
  - --apply создаёт override level=NONE
  - --apply на уже существующем override — обновляет
  - --restore --apply удаляет override
  - --organization фильтрует по конкретной организации
  - неизвестный email / module_code → CommandError
"""
from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.modules.models import Module
from apps.organizations.models import Organization, OrganizationMembership
from apps.rbac.models import AccessLevel, UserModuleAccessOverride
from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def feedlot_module():
    return Module.objects.get(code="feedlot")


@pytest.fixture
def user_with_membership(org):
    u = User.objects.create(email="head_feed@test.local", full_name="Head Feed")
    OrganizationMembership.objects.create(user=u, organization=org, is_active=True)
    return u


def _run(*args, **opts) -> str:
    out = StringIO()
    call_command("revoke_module_access", *args, stdout=out, **opts)
    return out.getvalue()


def test_dry_run_does_not_write(user_with_membership, feedlot_module, org):
    out = _run("head_feed@test.local", "feedlot")
    assert "DRY-RUN" in out
    assert UserModuleAccessOverride.objects.filter(
        membership__user=user_with_membership, module=feedlot_module,
    ).count() == 0


def test_apply_creates_override_with_level_none(
    user_with_membership, feedlot_module, org,
):
    _run("head_feed@test.local", "feedlot", apply=True)
    ov = UserModuleAccessOverride.objects.get(
        membership__user=user_with_membership,
        membership__organization=org,
        module=feedlot_module,
    )
    assert ov.level == AccessLevel.NONE
    assert "manage.py" in ov.reason


def test_apply_updates_existing_override(
    user_with_membership, feedlot_module, org,
):
    membership = user_with_membership.memberships.get(organization=org)
    UserModuleAccessOverride.objects.create(
        membership=membership, module=feedlot_module, level=AccessLevel.READ,
    )
    _run("head_feed@test.local", "feedlot", apply=True)
    ov = UserModuleAccessOverride.objects.get(
        membership=membership, module=feedlot_module,
    )
    assert ov.level == AccessLevel.NONE


def test_restore_deletes_override(user_with_membership, feedlot_module, org):
    membership = user_with_membership.memberships.get(organization=org)
    UserModuleAccessOverride.objects.create(
        membership=membership, module=feedlot_module, level=AccessLevel.NONE,
    )
    _run("head_feed@test.local", "feedlot", restore=True, apply=True)
    assert not UserModuleAccessOverride.objects.filter(
        membership=membership, module=feedlot_module,
    ).exists()


def test_organization_filter_isolates(
    user_with_membership, feedlot_module, org,
):
    """С --organization применяется только к указанной org, не к остальным."""
    other = Organization.objects.create(
        code="OTHER-RBAC", name="Other",
        accounting_currency=org.accounting_currency,
    )
    OrganizationMembership.objects.create(
        user=user_with_membership, organization=other, is_active=True,
    )

    _run(
        "head_feed@test.local", "feedlot",
        organization=org.code, apply=True,
    )
    # Override создан только для DEFAULT, не для OTHER.
    overrides = UserModuleAccessOverride.objects.filter(
        membership__user=user_with_membership, module=feedlot_module,
    ).values_list("membership__organization__code", flat=True)
    assert list(overrides) == [org.code]


def test_unknown_email_raises():
    with pytest.raises(CommandError):
        _run("ghost@nowhere.local", "feedlot")


def test_unknown_module_raises(user_with_membership):
    with pytest.raises(CommandError):
        _run("head_feed@test.local", "no-such-module")


def test_no_membership_raises(org):
    """Юзер без активных membership → CommandError."""
    User.objects.create(email="ghost@empty.local", full_name="Ghost")
    with pytest.raises(CommandError):
        _run("ghost@empty.local", "feedlot")
