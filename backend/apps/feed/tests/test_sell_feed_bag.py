"""
Тесты сервиса ``sell_feed_bag_lot`` — розничная продажа мешков с public-сканера.

Симметрия с apps/vet/tests/test_public_and_sell.py.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.counterparties.models import Counterparty
from apps.feed.models import FeedBagLot, FeedBatch
from apps.feed.services.sell_feed_bag import (
    FeedBagSellError,
    sell_feed_bag_lot,
)
from apps.vet.models import SellerDeviceToken
from apps.warehouses.models import Warehouse

# Pull packaging fixtures (chain: org → recipe → batch → bag_lot).
from apps.feed.tests.test_package_feed_batch import (  # noqa: F401
    approved_feed_batch,
    bag_warehouse,
)
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


pytestmark = pytest.mark.django_db


@pytest.fixture
def bag_lot(approved_feed_batch, bag_warehouse, user):
    """20 мешков × 50 кг с unique barcode для скан-теста."""
    from apps.feed.services.package_feed_batch import package_feed_batch

    res = package_feed_batch(
        approved_feed_batch,
        bag_count=20, bag_weight_kg=Decimal("50"),
        storage_warehouse=bag_warehouse, user=user,
    )
    bl = res.bag_lot
    # Гарантируем barcode (package_feed_batch уже его генерит, но fixture
    # должен быть детерминированным).
    if not bl.barcode:
        bl.barcode = "FEED-BROILER-TST1"
        bl.save(update_fields=["barcode"])
    return bl


@pytest.fixture
def seller_token(org, user):
    return SellerDeviceToken.objects.create(
        user=user, organization=org,
        token="feed-seller-token-xyz", label="Магазин корма",
    )


# ── service-level ─────────────────────────────────────────────────────────


def test_sell_feed_bag_lot_decrements_bags(org, bag_lot, user):
    initial = bag_lot.bags_remaining
    res = sell_feed_bag_lot(
        bag_lot=bag_lot, quantity=Decimal("3"),
        seller_user=user, organization=org,
        unit_price_uzs=Decimal("60000"),
    )
    assert res.bag_lot.bags_remaining == initial - 3
    assert res.sale_order.amount_uzs == Decimal("180000")
    assert res.bag_lot.status == FeedBagLot.Status.ACTIVE


def test_sell_full_quantity_marks_depleted(org, bag_lot, user):
    qty = bag_lot.bags_remaining
    res = sell_feed_bag_lot(
        bag_lot=bag_lot, quantity=Decimal(qty),
        seller_user=user, organization=org,
        unit_price_uzs=Decimal("60000"),
    )
    assert res.bag_lot.bags_remaining == 0
    assert res.bag_lot.status == FeedBagLot.Status.DEPLETED


def test_sell_rejects_more_than_available(org, bag_lot, user):
    with pytest.raises(FeedBagSellError, match="Доступно"):
        sell_feed_bag_lot(
            bag_lot=bag_lot, quantity=Decimal(bag_lot.bags_remaining + 1),
            seller_user=user, organization=org,
            unit_price_uzs=Decimal("60000"),
        )


def test_sell_rejects_fractional_bags(org, bag_lot, user):
    with pytest.raises(FeedBagSellError, match="целым числом"):
        sell_feed_bag_lot(
            bag_lot=bag_lot, quantity=Decimal("2.5"),
            seller_user=user, organization=org,
            unit_price_uzs=Decimal("60000"),
        )


def test_sell_rejects_recalled(org, bag_lot, user):
    bag_lot.status = FeedBagLot.Status.RECALLED
    bag_lot.save(update_fields=["status"])
    with pytest.raises(FeedBagSellError, match="Отозвана|недоступна"):
        sell_feed_bag_lot(
            bag_lot=bag_lot, quantity=Decimal("1"),
            seller_user=user, organization=org,
            unit_price_uzs=Decimal("60000"),
        )


def test_sell_requires_unit_price(org, bag_lot, user):
    with pytest.raises(FeedBagSellError, match="Укажите цену"):
        sell_feed_bag_lot(
            bag_lot=bag_lot, quantity=Decimal("1"),
            seller_user=user, organization=org,
            unit_price_uzs=None,
        )


# ── public endpoint ───────────────────────────────────────────────────────


def test_public_scan_returns_feed_bag_lot(bag_lot):
    client = APIClient()
    resp = client.get(f"/api/vet/public/scan/{bag_lot.barcode}/")
    assert resp.status_code == 200
    data = resp.data
    assert data["source_kind"] == "feed_bag_lot"
    assert data["barcode"] == bag_lot.barcode


def test_public_sell_feed_bag_via_seller_token(bag_lot, seller_token):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {seller_token.token}")
    resp = client.post(
        "/api/vet/public/sell/",
        {
            "barcode": bag_lot.barcode,
            "quantity": "2",
            "unit_price_uzs": "55000",
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    data = resp.data
    assert data["source_kind"] == "feed_bag_lot"
    assert Decimal(data["total_uzs"]) == Decimal("110000")
    assert int(data["remaining_qty"]) == bag_lot.bags_remaining - 2


def test_public_sell_feed_bag_without_price_returns_400(bag_lot, seller_token):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {seller_token.token}")
    resp = client.post(
        "/api/vet/public/sell/",
        {"barcode": bag_lot.barcode, "quantity": "1"},
        format="json",
    )
    assert resp.status_code == 400
    assert "Укажите цену" in str(resp.content, "utf-8")
