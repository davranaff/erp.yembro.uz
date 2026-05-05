"""
API-тесты: при confirm sale админам нужных модулей уходит TG-уведомление.

Проверяем что notify_admins_task вызван с правильными (text, org_id, module_code):
- всегда есть один вызов с module_code='sales' (общая сводка)
- если в позициях есть feed_batch / feed_bag_lot → вызов с 'feed'
- если есть vet_stock_batch / vet_accessory → вызов с 'vet'
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from apps.feed.models import FeedBatch
from apps.feed.services.execute_task import execute_production_task
from apps.feed.services.package_feed_batch import package_feed_batch
from apps.modules.models import Module
from apps.organizations.models import OrganizationMembership
from apps.rbac.models import AccessLevel, UserModuleAccessOverride
from apps.sales.models import SaleItem, SaleOrder
from apps.users.models import User
from apps.warehouses.models import Warehouse


pytestmark = pytest.mark.django_db


# Фикстуры из feed-замеса (org / m_feed / task / nomenclature / etc.)
from apps.feed.tests.test_execute_task import (  # noqa: F401
    org,
    m_feed,
    user,
    unit_kg,
    cat_raw,
    corn,
    soy,
    supplier,
    mixer_line,
    storage_bin,
    raw_warehouse,
    ready_warehouse,
    corn_batch,
    soy_batch,
    recipe,
    recipe_version,
    broiler_feed_nom,
    task,
)


@pytest.fixture
def m_sales():
    return Module.objects.get(code="sales")


@pytest.fixture
def admin_user(org, m_sales):
    u = User.objects.create(email="notif@y.local", full_name="Notif Admin")
    u.set_password("x"); u.save()
    m = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True,
    )
    UserModuleAccessOverride.objects.create(
        membership=m, module=m_sales, level=AccessLevel.ADMIN,
    )
    return u


@pytest.fixture
def client(admin_user):
    api = APIClient()
    api.force_authenticate(user=admin_user)
    api.credentials(HTTP_X_ORGANIZATION_CODE="DEFAULT")
    return api


@pytest.fixture
def buyer(org):
    from apps.counterparties.models import Counterparty
    return Counterparty.objects.create(
        organization=org, code="К-NTF", kind="buyer", name="Покупатель",
    )


@pytest.fixture
def warehouse(org, m_sales):
    return Warehouse.objects.create(
        organization=org, module=m_sales, code="СК-NTF", name="Sales WH",
    )


@pytest.fixture
def bag_warehouse(org, m_feed):
    return Warehouse.objects.create(
        organization=org, module=m_feed, code="СК-МШ-NTF", name="Bag WH",
    )


@pytest.fixture
def approved_feed_batch(task, ready_warehouse, storage_bin, broiler_feed_nom):
    res = execute_production_task(
        task, output_warehouse=ready_warehouse, storage_bin=storage_bin,
    )
    fb = res.feed_batch
    fb.status = FeedBatch.Status.APPROVED
    fb.save(update_fields=["status"])
    return fb


def _make_draft(org, m_sales, buyer, warehouse):
    return SaleOrder.objects.create(
        organization=org, module=m_sales, doc_number="",
        date=date(2026, 5, 5), customer=buyer, warehouse=warehouse,
    )


def test_confirm_feed_sale_notifies_sales_and_feed_admins(
    client, org, m_sales, buyer, warehouse, approved_feed_batch, broiler_feed_nom,
):
    order = _make_draft(org, m_sales, buyer, warehouse)
    SaleItem.objects.create(
        order=order, nomenclature=broiler_feed_nom,
        feed_batch=approved_feed_batch,
        quantity=Decimal("100"), unit_price_uzs=Decimal("25000"),
    )

    with patch("apps.tgbot.tasks.notify_admins_task.delay") as mock_notify:
        resp = client.post(f"/api/sales/orders/{order.id}/confirm/")
    assert resp.status_code == 200, resp.content

    calls = mock_notify.call_args_list
    module_codes = [c.args[2] for c in calls]
    # sales (сводно) + feed (детально по своим item'ам). admin может тоже
    # быть (через orchestrator), но проверяем минимум.
    assert "sales" in module_codes
    assert "feed" in module_codes
    # Текст для feed на узбекском после Phase A: «Yem-xashak sotildi»
    feed_text = next(c.args[0] for c in calls if c.args[2] == "feed")
    assert "Yem-xashak sotildi" in feed_text
    assert approved_feed_batch.doc_number in feed_text


def test_confirm_bag_lot_sale_notifies_feed_admin_with_bag_count(
    client, org, m_sales, buyer, bag_warehouse, approved_feed_batch, broiler_feed_nom,
):
    bag_lot = package_feed_batch(
        approved_feed_batch, bag_count=20,
        bag_weight_kg=Decimal("50"), storage_warehouse=bag_warehouse,
    ).bag_lot
    order = _make_draft(org, m_sales, buyer, bag_warehouse)
    SaleItem.objects.create(
        order=order, nomenclature=broiler_feed_nom,
        feed_bag_lot=bag_lot,
        quantity=Decimal("5"), unit_price_uzs=Decimal("1200000"),
    )

    with patch("apps.tgbot.tasks.notify_admins_task.delay") as mock_notify:
        resp = client.post(f"/api/sales/orders/{order.id}/confirm/")
    assert resp.status_code == 200, resp.content

    calls = mock_notify.call_args_list
    feed_call = next((c for c in calls if c.args[2] == "feed"), None)
    assert feed_call is not None, "feed module not notified"
    text = feed_call.args[0]
    assert bag_lot.doc_number in text
    assert "5 qop" in text  # узбекский: «5 qop × 50 kg»
