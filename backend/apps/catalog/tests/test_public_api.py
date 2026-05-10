"""
Smoke-тесты публичного API каталога.
"""
from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.catalog.models import Brand, Category, Direction, Product, ProductSpec


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def brand(db) -> Brand:
    b = Brand.objects.create(code="yembro", is_active=True)
    b.name_ru = "Yembro"; b.name_uz = "Yembro"; b.name_en = "Yembro"
    b.slug_ru = "yembro"; b.slug_uz = "yembro"; b.slug_en = "yembro"
    b.save()
    return b


@pytest.fixture
def category(db) -> Category:
    c = Category.objects.create(code="broiler", is_active=True, direction=Direction.BROILER)
    c.name_ru = "Бройлер"; c.name_uz = "Broyler"; c.name_en = "Broiler"
    c.slug_ru = "broiler"; c.slug_uz = "broyler"; c.slug_en = "broiler"
    c.save()
    return c


@pytest.fixture
def product(db, brand, category) -> Product:
    p = Product.objects.create(
        code="starter", brand=brand, category=category,
        is_active=True, direction=Direction.BROILER, sort_order=0,
    )
    p.name_ru = "Стартер"; p.name_uz = "Starter"; p.name_en = "Starter"
    p.slug_ru = "starter"; p.slug_uz = "starter"; p.slug_en = "starter"
    p.short_description_ru = "Корм 0–14 дней"
    p.short_description_uz = "0–14 kun yemi"
    p.short_description_en = "Days 0–14 feed"
    p.save()
    ProductSpec.objects.create(product=p, protein_pct=23, me_kcal_per_kg=3050)
    return p


def test_brands_list_anonymous(client, brand):
    r = client.get("/api/catalog/v1/brands/")
    assert r.status_code == 200
    data = r.json()
    items = data.get("results", data)
    assert any(b["code"] == "yembro" for b in items)


def test_lang_uz_returns_uzbek_name(client, brand):
    r = client.get("/api/catalog/v1/brands/yembro/?lang=uz")
    assert r.status_code == 200
    assert r.json()["name"] == "Yembro"


def test_products_list_filters_by_direction(client, product):
    r = client.get("/api/catalog/v1/products/?direction=broiler")
    assert r.status_code == 200
    items = r.json().get("results", r.json())
    assert any(p["code"] == "starter" for p in items)


def test_product_detail_includes_spec_and_breadcrumbs(client, product):
    r = client.get("/api/catalog/v1/products/starter/?lang=ru")
    assert r.status_code == 200
    body = r.json()
    assert body["spec"]["protein_pct"] == "23.00"
    assert any(b["code"] == "broiler" for b in body["breadcrumbs"])


def test_sitemap_returns_all_kinds(client, brand, category, product):
    r = client.get("/api/catalog/v1/sitemap/")
    assert r.status_code == 200
    kinds = {it["kind"] for it in r.json()["items"]}
    assert {"brand", "category", "product"}.issubset(kinds)


def test_contact_post_validates_email_or_phone(client, db):
    r = client.post("/api/catalog/v1/contact/", {
        "name": "Иван", "contact": "garbage", "company": "X",
    }, format="json")
    assert r.status_code == 400


def test_contact_post_accepts_valid_payload(client, db):
    r = client.post("/api/catalog/v1/contact/", {
        "name": "Иван", "contact": "+998901234567",
        "company": "Ферма", "message": "Заявка", "source_lang": "ru",
    }, format="json")
    assert r.status_code == 201
    assert r.json() == {"ok": True}


def test_contact_post_honeypot_silently_dropped(client, db):
    r = client.post("/api/catalog/v1/contact/", {
        "name": "Иван", "contact": "+998901234567", "website": "spam-bot",
    }, format="json")
    assert r.status_code == 201
    from apps.catalog.models import ContactRequest
    assert ContactRequest.objects.count() == 0
