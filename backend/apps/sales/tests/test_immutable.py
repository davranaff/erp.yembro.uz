"""
Регрессионный тест: после confirm/cancel SaleOrder становится иммутабельным
(нельзя UPDATE/DELETE через ViewSet).

Проверяется через ImmutableStatusMixin (apps.common.lifecycle).
"""
from datetime import date
from decimal import Decimal

import pytest
from rest_framework.exceptions import PermissionDenied

from apps.modules.models import Module
from apps.organizations.models import Organization
from apps.sales.models import SaleOrder
from apps.sales.views import SaleOrderViewSet
from apps.users.models import User
from apps.warehouses.models import Warehouse


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_sales():
    return Module.objects.get(code="sales")


@pytest.fixture
def user():
    return User.objects.create(email="immut-sales@y.local", full_name="X")


@pytest.fixture
def warehouse(org, m_sales):
    return Warehouse.objects.create(
        organization=org, module=m_sales, code="ИММ-СК-1", name="Sales WH",
    )


@pytest.fixture
def customer(org):
    from apps.counterparties.models import Counterparty

    return Counterparty.objects.create(
        organization=org, code="CUST-IMM-1", kind="buyer", name="X",
    )


@pytest.fixture
def order(org, m_sales, warehouse, customer, user):
    return SaleOrder.objects.create(
        organization=org, module=m_sales,
        doc_number="П-IMM-001", date=date.today(),
        customer=customer, warehouse=warehouse,
        status=SaleOrder.Status.DRAFT,
    )


def _check_immutable(viewset_class, instance):
    vs = viewset_class()

    class FakeSerializer:
        instance = None
    fs = FakeSerializer()
    fs.instance = instance

    with pytest.raises(PermissionDenied):
        vs.perform_update(fs)


def test_draft_can_be_updated(order):
    """DRAFT — _check_mutable не падает."""
    vs = SaleOrderViewSet()
    vs._check_mutable(order)  # не должен бросить


def test_confirmed_blocks_update(order):
    order.status = SaleOrder.Status.CONFIRMED
    order.save()
    _check_immutable(SaleOrderViewSet, order)


def test_cancelled_blocks_update(order):
    order.status = SaleOrder.Status.CANCELLED
    order.save()
    _check_immutable(SaleOrderViewSet, order)


def test_confirmed_blocks_destroy(order):
    order.status = SaleOrder.Status.CONFIRMED
    order.save()
    vs = SaleOrderViewSet()
    with pytest.raises(PermissionDenied):
        vs.perform_destroy(order)
