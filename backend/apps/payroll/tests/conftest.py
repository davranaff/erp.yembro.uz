from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.accounting.models import GLAccount, GLSubaccount
from apps.currency.models import Currency
from apps.organizations.models import Organization, OrganizationMembership
from apps.payroll.models import CompensationPlan
from apps.users.models import User


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def uzs():
    return Currency.objects.get(code="UZS")


@pytest.fixture
def cash_subaccount(org):
    """Касса 50.01."""
    return GLSubaccount.objects.get(account__organization=org, code="50.01")


@pytest.fixture
def hr_user(org):
    user = User.objects.create(
        email="hr@yembro.test",
        full_name="HR Иван",
        is_active=True,
    )
    OrganizationMembership.objects.create(
        user=user, organization=org, is_active=True,
        position_title="HR",
    )
    return user


@pytest.fixture
def employee_monthly(org, uzs):
    user = User.objects.create(
        email="director@yembro.test",
        full_name="Директор Семён",
        is_active=True,
    )
    membership = OrganizationMembership.objects.create(
        user=user, organization=org, is_active=True,
        position_title="Директор",
    )
    CompensationPlan.objects.create(
        organization=org, employee=membership,
        compensation_type=CompensationPlan.Type.MONTHLY_SALARY,
        currency=uzs,
    )
    return membership


@pytest.fixture
def employee_per_shift(org, uzs):
    user = User.objects.create(
        email="worker@yembro.test",
        full_name="Рабочий Пётр",
        is_active=True,
    )
    membership = OrganizationMembership.objects.create(
        user=user, organization=org, is_active=True,
        position_title="Рабочий убоя",
    )
    CompensationPlan.objects.create(
        organization=org, employee=membership,
        compensation_type=CompensationPlan.Type.PER_SHIFT,
        currency=uzs,
    )
    return membership
