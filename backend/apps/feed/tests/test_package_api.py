"""
API-тесты для FeedBatch.package action и FeedBagLotViewSet (list/retrieve).
"""
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.feed.models import FeedBagLot, FeedBatch
from apps.feed.services.execute_task import execute_production_task
from apps.organizations.models import OrganizationMembership
from apps.rbac.models import AccessLevel, UserModuleAccessOverride
from apps.users.models import User
from apps.warehouses.models import Warehouse


pytestmark = pytest.mark.django_db


# Подтянем фикстуры из test_execute_task — те же org / m_feed / task / etc.
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
def admin_user(org, m_feed):
    u = User.objects.create(email="pkg-api@y.local", full_name="Pkg Admin")
    u.set_password("x")
    u.save()
    m = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True,
    )
    UserModuleAccessOverride.objects.create(
        membership=m, module=m_feed, level=AccessLevel.ADMIN,
    )
    return u


@pytest.fixture
def client(admin_user):
    api = APIClient()
    api.force_authenticate(user=admin_user)
    api.credentials(HTTP_X_ORGANIZATION_CODE="DEFAULT")
    return api


@pytest.fixture
def bag_warehouse(org, m_feed):
    return Warehouse.objects.create(
        organization=org, module=m_feed,
        code="СК-МШ-API", name="Склад мешков (API)",
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


def test_package_action_creates_bag_lot(
    client, approved_feed_batch, bag_warehouse,
):
    url = f"/api/feed/feed-batches/{approved_feed_batch.id}/package/"
    resp = client.post(url, {
        "bag_count": 10,
        "bag_weight_kg": "50",
        "storage_warehouse": str(bag_warehouse.id),
    }, format="json")
    assert resp.status_code == 200, resp.content
    data = resp.json()
    bl_data = data["_result"]["bag_lot"]
    assert bl_data["bags_initial"] == 10
    assert bl_data["bags_remaining"] == 10
    assert bl_data["recipe_code"] == "Р-БР-СТ"
    # Резолвится через recipe.code → NomenclatureItem.sku=Р-БР-СТ
    assert bl_data["nomenclature_sku"] == "Р-БР-СТ"

    # Партия создана в БД
    assert FeedBagLot.objects.filter(id=bl_data["id"]).exists()


def test_package_action_validates_bag_count_required(
    client, approved_feed_batch, bag_warehouse,
):
    url = f"/api/feed/feed-batches/{approved_feed_batch.id}/package/"
    resp = client.post(url, {
        "bag_weight_kg": "50",
        "storage_warehouse": str(bag_warehouse.id),
    }, format="json")
    assert resp.status_code == 400


def test_package_action_validates_warehouse_exists(
    client, approved_feed_batch,
):
    url = f"/api/feed/feed-batches/{approved_feed_batch.id}/package/"
    resp = client.post(url, {
        "bag_count": 5,
        "bag_weight_kg": "50",
        "storage_warehouse": "00000000-0000-0000-0000-000000000000",
    }, format="json")
    assert resp.status_code == 400


def test_package_action_rejects_non_approved(
    client, approved_feed_batch, bag_warehouse,
):
    approved_feed_batch.status = FeedBatch.Status.QUALITY_CHECK
    approved_feed_batch.save()
    url = f"/api/feed/feed-batches/{approved_feed_batch.id}/package/"
    resp = client.post(url, {
        "bag_count": 5,
        "bag_weight_kg": "50",
        "storage_warehouse": str(bag_warehouse.id),
    }, format="json")
    assert resp.status_code == 400


def test_feed_bag_lots_list(client, approved_feed_batch, bag_warehouse):
    """После фасовки в /api/feed/feed-bag-lots/ есть запись."""
    pkg_url = f"/api/feed/feed-batches/{approved_feed_batch.id}/package/"
    client.post(pkg_url, {
        "bag_count": 5, "bag_weight_kg": "50",
        "storage_warehouse": str(bag_warehouse.id),
    }, format="json")

    list_resp = client.get("/api/feed/feed-bag-lots/")
    assert list_resp.status_code == 200
    body = list_resp.json()
    items = body["results"] if isinstance(body, dict) else body
    assert len(items) >= 1
    assert items[0]["bags_initial"] == 5


def test_feed_bag_lots_filter_by_status(client, approved_feed_batch, bag_warehouse):
    pkg_url = f"/api/feed/feed-batches/{approved_feed_batch.id}/package/"
    client.post(pkg_url, {
        "bag_count": 5, "bag_weight_kg": "50",
        "storage_warehouse": str(bag_warehouse.id),
    }, format="json")
    resp = client.get("/api/feed/feed-bag-lots/?status=active")
    assert resp.status_code == 200
    body = resp.json()
    items = body["results"] if isinstance(body, dict) else body
    assert all(it["status"] == "active" for it in items)
