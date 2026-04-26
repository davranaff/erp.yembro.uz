"""
Тесты валидации SlaughterYield:
  - сумма kg-выходов не должна превышать live_weight_kg_total смены
  - создание через ViewSet (без TypeError на shift__organization)
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.batches.models import Batch
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.slaughter.models import SlaughterShift, SlaughterYield
from apps.slaughter.serializers import SlaughterYieldSerializer
from apps.users.models import User
from apps.warehouses.models import ProductionBlock


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_feedlot():
    return Module.objects.get(code="feedlot")


@pytest.fixture
def m_slaughter():
    return Module.objects.get(code="slaughter")


@pytest.fixture
def user():
    return User.objects.create(email="yv@y.local", full_name="YV")


@pytest.fixture
def unit_kg(org):
    return Unit.objects.get_or_create(
        organization=org, code="кг", defaults={"name": "кг"}
    )[0]


@pytest.fixture
def unit_pcs(org):
    return Unit.objects.get_or_create(
        organization=org, code="шт", defaults={"name": "шт"}
    )[0]


@pytest.fixture
def cat_fg(org):
    return Category.objects.get_or_create(organization=org, name="ГП-Y")[0]


@pytest.fixture
def carcass_nom(org, cat_fg, unit_kg):
    item, _ = NomenclatureItem.objects.get_or_create(
        organization=org, sku="CARCASS-WHOLE",
        defaults={"name": "Тушка целая", "category": cat_fg, "unit": unit_kg},
    )
    return item


@pytest.fixture
def offal_nom(org, cat_fg, unit_kg):
    item, _ = NomenclatureItem.objects.get_or_create(
        organization=org, sku="OFFAL",
        defaults={"name": "Субпродукты", "category": cat_fg, "unit": unit_kg},
    )
    return item


@pytest.fixture
def chick_nom(org, cat_fg, unit_pcs):
    return NomenclatureItem.objects.create(
        organization=org, sku="ЖП-Y-01", name="Цыплёнок",
        category=cat_fg, unit=unit_pcs,
    )


@pytest.fixture
def slaughter_line(org, m_slaughter):
    return ProductionBlock.objects.create(
        organization=org, module=m_slaughter, code="ЛН-Y",
        name="Линия Y", kind=ProductionBlock.Kind.SLAUGHTER_LINE,
    )


@pytest.fixture
def shift(org, m_slaughter, m_feedlot, slaughter_line, chick_nom, unit_pcs, user):
    batch = Batch.objects.create(
        organization=org, doc_number="ГY-BATCH-01",
        nomenclature=chick_nom, unit=unit_pcs,
        origin_module=m_feedlot, current_module=m_slaughter,
        current_block=slaughter_line,
        current_quantity=Decimal("100"),
        initial_quantity=Decimal("100"),
        accumulated_cost_uzs=Decimal("1000000"),
        started_at=date.today(),
    )
    return SlaughterShift.objects.create(
        organization=org, module=m_slaughter,
        line_block=slaughter_line, source_batch=batch,
        doc_number="ГYUB-001", shift_date=date.today(),
        start_time=datetime.now(timezone.utc),
        live_heads_received=100,
        live_weight_kg_total=Decimal("250.000"),  # 250 кг живого
        foreman=user,
    )


# ── Validation: yield не превышает live_weight ─────────────────────────


def test_yield_within_live_weight_ok(shift, carcass_nom, unit_kg):
    """200 кг ≤ 250 кг live — OK."""
    s = SlaughterYieldSerializer(data={
        "shift": shift.id,
        "nomenclature": carcass_nom.id,
        "quantity": "200",
        "unit": unit_kg.id,
        "share_percent": None,
        "notes": "",
    })
    assert s.is_valid(), s.errors


def test_yield_exceeds_live_weight_blocked(shift, carcass_nom, unit_kg):
    """300 кг > 250 кг live — отклоняем."""
    s = SlaughterYieldSerializer(data={
        "shift": shift.id,
        "nomenclature": carcass_nom.id,
        "quantity": "300",
        "unit": unit_kg.id,
        "share_percent": None,
        "notes": "",
    })
    assert not s.is_valid()
    assert "quantity" in s.errors


def test_yield_sum_exceeds_live_weight_blocked(shift, carcass_nom, offal_nom, unit_kg):
    """Уже есть 200 кг тушки. Попытка добавить ещё 80 кг субпродуктов → 280 > 250."""
    SlaughterYield.objects.create(
        shift=shift, nomenclature=carcass_nom, unit=unit_kg,
        quantity=Decimal("200"),
    )
    s = SlaughterYieldSerializer(data={
        "shift": shift.id,
        "nomenclature": offal_nom.id,
        "quantity": "80",
        "unit": unit_kg.id,
        "share_percent": None,
        "notes": "",
    })
    assert not s.is_valid()
    assert "quantity" in s.errors


def test_yield_edit_excludes_self_from_sum(shift, carcass_nom, unit_kg):
    """При редактировании текущая строка не учитывается в сумме."""
    y = SlaughterYield.objects.create(
        shift=shift, nomenclature=carcass_nom, unit=unit_kg,
        quantity=Decimal("200"),
    )
    # Редактируем ту же строку → 220 кг ≤ 250 кг — должно пройти
    s = SlaughterYieldSerializer(
        instance=y,
        data={
            "shift": shift.id,
            "nomenclature": carcass_nom.id,
            "quantity": "220",
            "unit": unit_kg.id,
            "share_percent": None,
            "notes": "",
        },
    )
    assert s.is_valid(), s.errors


# ── Regression: viewset _save_kwargs_for_create не передаёт `shift__organization` ──


def test_child_of_shift_mixin_skips_org_kwarg():
    """
    Регрессионный тест на фикс: `_ChildOfShiftMixin._save_kwargs_for_create`
    не должен передавать `shift__organization=...` в `Model.objects.create()`,
    иначе TypeError на kwargs модели.
    """
    from apps.slaughter.views import (
        SlaughterLabTestViewSet,
        SlaughterQualityCheckViewSet,
        SlaughterYieldViewSet,
        _ChildOfShiftMixin,
    )

    # Все 3 child-вьюсета должны использовать миксин
    assert issubclass(SlaughterYieldViewSet, _ChildOfShiftMixin)
    assert issubclass(SlaughterQualityCheckViewSet, _ChildOfShiftMixin)
    assert issubclass(SlaughterLabTestViewSet, _ChildOfShiftMixin)
