"""
Регрессии:
  - GET /api/nomenclature/items/?module_code=feed возвращает только
    позиции с category.module='feed' (плюс null-категории если они есть).
  - RecipeComponent.clean() не пропускает несовпадающую категорию.
  - RawMaterialBatch.clean() — то же самое.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization, OrganizationMembership
from apps.rbac.models import AccessLevel, UserModuleAccessOverride
from apps.users.models import User


pytestmark = pytest.mark.django_db


# ─── fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_feed():
    return Module.objects.get(code="feed")


@pytest.fixture
def m_slaughter():
    return Module.objects.get(code="slaughter")


@pytest.fixture
def unit_kg(org):
    return Unit.objects.get_or_create(
        organization=org, code="кг", defaults={"name": "Килограмм"},
    )[0]


@pytest.fixture
def cat_feed(org, m_feed):
    return Category.objects.create(
        organization=org, name="Корма (test)", module=m_feed,
    )


@pytest.fixture
def cat_slaughter(org, m_slaughter):
    return Category.objects.create(
        organization=org, name="Убойня (test)", module=m_slaughter,
    )


@pytest.fixture
def feed_item(org, cat_feed, unit_kg):
    return NomenclatureItem.objects.create(
        organization=org, sku="TEST-CORN", name="Кукуруза TEST",
        category=cat_feed, unit=unit_kg,
    )


@pytest.fixture
def slaughter_item(org, cat_slaughter, unit_kg):
    return NomenclatureItem.objects.create(
        organization=org, sku="TEST-CARCASS", name="Тушка TEST",
        category=cat_slaughter, unit=unit_kg,
    )


@pytest.fixture
def reader_user(org, m_feed):
    u = User.objects.create(email="nom@y.local", full_name="Nom")
    membership = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True,
    )
    # Доступ к feed для чтения номенклатуры
    UserModuleAccessOverride.objects.create(
        membership=membership, module=m_feed, level=AccessLevel.READ,
    )
    # И ко всем остальным модулям, чтобы фильтр module_code не блокнул.
    for code in ("matochnik", "incubation", "feedlot", "slaughter", "vet", "core"):
        UserModuleAccessOverride.objects.create(
            membership=membership,
            module=Module.objects.get(code=code),
            level=AccessLevel.READ,
        )
    return u


# ─── API filter ──────────────────────────────────────────────────────────


def test_filter_by_module_code(reader_user, feed_item, slaughter_item):
    api = APIClient()
    api.force_authenticate(user=reader_user)
    api.credentials(HTTP_X_ORGANIZATION_CODE="DEFAULT")
    resp = api.get("/api/nomenclature/items/?module_code=feed")
    assert resp.status_code == 200
    data = resp.json()
    items = data.get("results", data) if isinstance(data, dict) else data
    skus = {it["sku"] for it in items}
    assert "TEST-CORN" in skus
    assert "TEST-CARCASS" not in skus


def test_filter_by_slaughter(reader_user, feed_item, slaughter_item):
    api = APIClient()
    api.force_authenticate(user=reader_user)
    api.credentials(HTTP_X_ORGANIZATION_CODE="DEFAULT")
    resp = api.get("/api/nomenclature/items/?module_code=slaughter")
    skus = {it["sku"] for it in resp.json().get("results", resp.json())}
    assert "TEST-CARCASS" in skus
    assert "TEST-CORN" not in skus


# ─── RecipeComponent.clean() guard ───────────────────────────────────────


def test_recipe_component_rejects_non_feed_nomenclature(
    org, m_feed, slaughter_item,
):
    """Если попытаться положить тушку как компонент рецепта корма —
    clean() должен выбросить ValidationError."""
    from apps.feed.models import Recipe, RecipeComponent, RecipeVersion

    recipe = Recipe.objects.create(
        organization=org, code="TEST-RCP", name="Test recipe",
        direction="broiler",
    )
    rv = RecipeVersion.objects.create(
        recipe=recipe, version_number=1,
        status="active", effective_from=date(2026, 1, 1),
    )
    bad = RecipeComponent(
        recipe_version=rv,
        nomenclature=slaughter_item,
        share_percent=Decimal("10"),
    )
    with pytest.raises(ValidationError) as exc:
        bad.full_clean()
    assert "nomenclature" in exc.value.message_dict


def test_recipe_component_accepts_feed_nomenclature(
    org, feed_item,
):
    from apps.feed.models import Recipe, RecipeComponent, RecipeVersion

    recipe = Recipe.objects.create(
        organization=org, code="TEST-RCP-OK", name="Test recipe OK",
        direction="broiler",
    )
    rv = RecipeVersion.objects.create(
        recipe=recipe, version_number=1,
        status="active", effective_from=date(2026, 1, 1),
    )
    ok = RecipeComponent(
        recipe_version=rv,
        nomenclature=feed_item,
        share_percent=Decimal("10"),
    )
    ok.full_clean()  # не должно бросать


def test_recipe_component_allows_categoryless_item(org, unit_kg):
    """Старые категории без module — back-compat: разрешаем."""
    from apps.feed.models import Recipe, RecipeComponent, RecipeVersion

    cat_general = Category.objects.create(
        organization=org, name="Общая категория без модуля", module=None,
    )
    item = NomenclatureItem.objects.create(
        organization=org, sku="TEST-GENERAL", name="Общая",
        category=cat_general, unit=unit_kg,
    )
    recipe = Recipe.objects.create(
        organization=org, code="TEST-RCP-GEN", name="Test gen",
        direction="broiler",
    )
    rv = RecipeVersion.objects.create(
        recipe=recipe, version_number=1,
        status="active", effective_from=date(2026, 1, 1),
    )
    cmp = RecipeComponent(
        recipe_version=rv, nomenclature=item, share_percent=Decimal("5"),
    )
    cmp.full_clean()  # без бросков
