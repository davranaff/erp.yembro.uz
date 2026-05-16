"""
Тесты row-level module-scope: пользователь с UserScopeAssignment по
конкретному модулю видит только записи этого модуля, даже если у него
admin-доступ.
"""
from __future__ import annotations

import pytest

from apps.common.scope import apply_scope, get_user_scope
from apps.modules.models import Module
from apps.organizations.models import Organization, OrganizationMembership
from apps.rbac.models import (
    AccessLevel,
    UserModuleAccessOverride,
    UserScopeAssignment,
)
from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def feed_module():
    return Module.objects.get(code="feed")


@pytest.fixture
def vet_module():
    return Module.objects.get(code="vet")


@pytest.fixture
def admin_user(org):
    """Пользователь с admin-override на ledger — без assignments видит всё."""
    u = User.objects.create_user(
        email="scope-admin@test.local", password="x", full_name="Admin",
    )
    m = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True,
    )
    ledger = Module.objects.get(code="ledger")
    UserModuleAccessOverride.objects.create(
        membership=m, module=ledger, level=AccessLevel.ADMIN,
    )
    return u


def test_no_assignments_admin_is_unlimited(admin_user, org):
    scope = get_user_scope(admin_user, org)
    assert scope.is_unlimited
    assert scope.is_org_admin


def test_no_assignments_regular_user_sees_only_rbac_modules(org, feed_module):
    """Без UserScopeAssignment юзер ограничен своими RBAC-модулями.

    Раньше был 'default open' — теперь allowed_module_ids берётся из ролей/overrides.
    Юзер без ролей видит nothing; юзер с override на feed видит только feed.
    """
    u = User.objects.create_user(email="scope-reg@test.local", password="x")
    m = OrganizationMembership.objects.create(user=u, organization=org, is_active=True)

    # Без ролей — пустой allowed_module_ids, is_unlimited=False.
    scope = get_user_scope(u, org)
    assert not scope.is_unlimited
    assert scope.allowed_module_ids == frozenset()

    # Добавляем override на feed → теперь только feed в scope.
    UserModuleAccessOverride.objects.create(
        membership=m, module=feed_module, level=AccessLevel.READ,
    )
    scope2 = get_user_scope(u, org)
    assert not scope2.is_unlimited
    assert scope2.allowed_module_ids == frozenset({str(feed_module.id)})


def test_module_assignment_restricts_even_admin(admin_user, org, feed_module):
    """Admin с UserScopeAssignment(module=feed) видит только feed-модуль."""
    UserScopeAssignment.objects.create(
        organization=org, user=admin_user,
        scope_type=UserScopeAssignment.ScopeType.MODULE,
        scope_id=feed_module.id,
    )
    scope = get_user_scope(admin_user, org)
    assert not scope.is_unlimited
    assert scope.allowed_module_ids == frozenset({str(feed_module.id)})
    # Другие измерения остаются без ограничений.
    assert scope.allowed_warehouse_ids is None
    assert scope.allowed_block_ids is None


def test_apply_scope_module_id_filter(admin_user, org, feed_module, vet_module):
    """apply_scope фильтрует queryset по module_id согласно scope."""
    from apps.warehouses.models import Warehouse

    Warehouse.objects.create(
        organization=org, module=feed_module, code="W-FEED-1", name="Feed-1",
    )
    Warehouse.objects.create(
        organization=org, module=vet_module, code="W-VET-1", name="Vet-1",
    )

    UserScopeAssignment.objects.create(
        organization=org, user=admin_user,
        scope_type=UserScopeAssignment.ScopeType.MODULE,
        scope_id=feed_module.id,
    )
    scope = get_user_scope(admin_user, org)

    # Фильтр только по складам, созданным в этом тесте — в seed уже есть
    # warehouse'ы с module=feed (`DEF-СК-К`), они тоже пройдут scope-фильтр,
    # но это не нарушает корректности — проверяем что vet-склад отвалился.
    qs = Warehouse.objects.filter(organization=org, code__in=["W-FEED-1", "W-VET-1"])
    filtered = apply_scope(qs, scope, scope_fields=("module_id",))
    codes = set(filtered.values_list("code", flat=True))
    assert codes == {"W-FEED-1"}
