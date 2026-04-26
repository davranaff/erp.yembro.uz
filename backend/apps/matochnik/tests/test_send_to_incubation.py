"""
Тесты send_eggs_to_incubation.

Сценарии:
    1. Happy path: batch matochnik → transfer создан, проведён, batch.current_module=incubation.
    2. Повторный вызов после первого отправления → ValidationError.
    3. Partial depleted batch (current=0) → ошибка.
    4. Не из маточника (другой origin) → ошибка.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.batches.models import Batch, BatchChainStep
from apps.matochnik.services.send_to_incubation import (
    SendToIncubationError,
    send_eggs_to_incubation,
)
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.transfers.models import InterModuleTransfer
from apps.warehouses.models import ProductionBlock, Warehouse


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_matochnik():
    return Module.objects.get(code="matochnik")


@pytest.fixture
def m_incubation():
    return Module.objects.get(code="incubation")


@pytest.fixture
def unit_kg(org):
    return Unit.objects.get_or_create(
        organization=org, code="кг", defaults={"name": "Килограмм"}
    )[0]


@pytest.fixture
def egg_nomenclature(org, unit_kg):
    cat = Category.objects.get_or_create(
        organization=org, name="Яйца",
    )[0]
    return NomenclatureItem.objects.create(
        organization=org, sku="ЯЙЦ-STI-01", name="Инкуб. яйцо",
        category=cat, unit=unit_kg,
    )


@pytest.fixture
def block(org, m_matochnik):
    return ProductionBlock.objects.create(
        organization=org, module=m_matochnik, code="КС-STI",
        name="Корпус", kind=ProductionBlock.Kind.MATOCHNIK,
    )


@pytest.fixture
def matochnik_warehouse(org, m_matochnik):
    return Warehouse.objects.create(
        organization=org, module=m_matochnik, code="СК-МА",
        name="Склад маточника",
    )


@pytest.fixture
def incubation_warehouse(org, m_incubation):
    return Warehouse.objects.create(
        organization=org, module=m_incubation, code="СК-ИН",
        name="Склад инкубации",
    )


@pytest.fixture(autouse=True)
def _warehouses(matochnik_warehouse, incubation_warehouse):
    # Подтягиваем оба warehouse на все тесты автоматически.
    return None


@pytest.fixture
def batch(org, m_matochnik, egg_nomenclature, unit_kg, block):
    return Batch.objects.create(
        organization=org, doc_number="П-STI-01",
        nomenclature=egg_nomenclature, unit=unit_kg,
        origin_module=m_matochnik, current_module=m_matochnik,
        current_block=block,
        current_quantity=Decimal("500"),
        initial_quantity=Decimal("500"),
        accumulated_cost_uzs=Decimal("1000000"),
        state=Batch.State.ACTIVE,
        started_at=date(2026, 4, 1),
    )


def test_happy_path_creates_transfer_and_moves_batch(batch, m_incubation):
    result = send_eggs_to_incubation(batch)
    batch.refresh_from_db()
    assert batch.current_module_id == m_incubation.id
    assert result.transfer.state == InterModuleTransfer.State.POSTED
    # Есть BatchChainStep для incubation
    steps = BatchChainStep.objects.filter(batch=batch).order_by("sequence")
    assert steps.count() >= 1
    last = steps.last()
    assert last.module_id == m_incubation.id


def test_second_call_after_move_raises(batch, m_incubation):
    send_eggs_to_incubation(batch)
    with pytest.raises(ValidationError):
        send_eggs_to_incubation(batch)


def test_empty_batch_raises(org, m_matochnik, egg_nomenclature, unit_kg, block):
    empty = Batch.objects.create(
        organization=org, doc_number="П-STI-02",
        nomenclature=egg_nomenclature, unit=unit_kg,
        origin_module=m_matochnik, current_module=m_matochnik,
        current_block=block,
        current_quantity=Decimal("0"),
        initial_quantity=Decimal("500"),
        accumulated_cost_uzs=Decimal("0"),
        state=Batch.State.ACTIVE,
        started_at=date(2026, 4, 1),
    )
    with pytest.raises(ValidationError):
        send_eggs_to_incubation(empty)


def test_non_matochnik_origin_raises(
    org, m_incubation, egg_nomenclature, unit_kg
):
    block_i = ProductionBlock.objects.create(
        organization=org, module=m_incubation, code="ИНК-BL",
        name="Шкаф", kind=ProductionBlock.Kind.INCUBATION,
    )
    alien = Batch.objects.create(
        organization=org, doc_number="П-STI-03",
        nomenclature=egg_nomenclature, unit=unit_kg,
        origin_module=m_incubation, current_module=m_incubation,
        current_block=block_i,
        current_quantity=Decimal("100"),
        initial_quantity=Decimal("100"),
        accumulated_cost_uzs=Decimal("0"),
        state=Batch.State.ACTIVE,
        started_at=date(2026, 4, 1),
    )
    with pytest.raises(ValidationError):
        send_eggs_to_incubation(alien)
