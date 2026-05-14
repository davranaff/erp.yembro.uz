import pytest
from apps.modules.models import Module
from apps.organizations.models import Organization, OrganizationMembership
from apps.rbac.models import AccessLevel, Role, RolePermission, UserModuleAccessOverride
from apps.users.models import User
from apps.common.permissions import get_user_readable_module_codes


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def membership(org):
    u = User.objects.create(email="rbac_perm_test@y.local", full_name="T")
    return OrganizationMembership.objects.create(user=u, organization=org, is_active=True)


def test_readable_includes_r_and_rw_and_admin(org, membership):
    """get_user_readable_module_codes returns codes with level r, rw, or admin."""
    role = Role.objects.create(organization=org, code="TEST_R_ROLE", name="Test R")
    m_slaughter = Module.objects.get(code="slaughter")
    m_feedlot = Module.objects.get(code="feedlot")
    m_purchases = Module.objects.get(code="purchases")
    RolePermission.objects.create(role=role, module=m_slaughter, level=AccessLevel.ADMIN)
    RolePermission.objects.create(role=role, module=m_feedlot, level=AccessLevel.READ)
    RolePermission.objects.create(role=role, module=m_purchases, level=AccessLevel.NONE)
    from apps.rbac.models import UserRole
    UserRole.objects.create(membership=membership, role=role)

    result = get_user_readable_module_codes(membership)

    assert "slaughter" in result   # admin >= r
    assert "feedlot" in result     # r >= r
    assert "purchases" not in result  # none < r


def test_readable_override_beats_role(org, membership):
    """UserModuleAccessOverride wins over role: override=none blocks a role's rw."""
    role = Role.objects.create(organization=org, code="TEST_OVR_ROLE", name="Ovr")
    m_sales = Module.objects.get(code="sales")
    RolePermission.objects.create(role=role, module=m_sales, level=AccessLevel.READ_WRITE)
    from apps.rbac.models import UserRole
    UserRole.objects.create(membership=membership, role=role)
    UserModuleAccessOverride.objects.create(
        membership=membership, module=m_sales, level=AccessLevel.NONE
    )

    result = get_user_readable_module_codes(membership)

    assert "sales" not in result


def test_readable_empty_when_no_roles(membership):
    result = get_user_readable_module_codes(membership)
    assert result == set()
