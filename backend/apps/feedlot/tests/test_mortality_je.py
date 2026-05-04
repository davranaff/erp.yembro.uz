"""
Тест: apply_mortality создаёт JE Дт 91.02 / Кт 20.02 на (dead × unit_cost).
"""
from datetime import date
from decimal import Decimal

import pytest

from apps.accounting.models import GLAccount, GLSubaccount, JournalEntry
from apps.batches.models import Batch
from apps.feedlot.models import FeedlotBatch
from apps.feedlot.services.mortality import apply_mortality
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
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
def user():
    return User.objects.create(email="mje@y.local", full_name="MJE")


@pytest.fixture
def unit_pcs(org):
    return Unit.objects.get_or_create(
        organization=org, code="голM", defaults={"name": "Г"}
    )[0]


@pytest.fixture
def cat(org):
    return Category.objects.get_or_create(organization=org, name="Птица M")[0]


@pytest.fixture
def nom(org, cat, unit_pcs):
    return NomenclatureItem.objects.create(
        organization=org, sku="ЦБ-M", name="Бройлер M",
        category=cat, unit=unit_pcs,
    )


@pytest.fixture
def house(org, m_feedlot):
    return ProductionBlock.objects.create(
        organization=org, module=m_feedlot, code="ПТ-M-1",
        name="Птичник M1", kind=ProductionBlock.Kind.FEEDLOT,
    )


@pytest.fixture
def chick_batch(org, m_feedlot, house, nom, unit_pcs):
    """1000 голов, 5_000_000 сум cost → unit_cost = 5000."""
    return Batch.objects.create(
        organization=org, doc_number="П-M-ЦБ-01",
        nomenclature=nom, unit=unit_pcs,
        origin_module=m_feedlot, current_module=m_feedlot,
        current_block=house,
        current_quantity=Decimal("1000"),
        initial_quantity=Decimal("1000"),
        accumulated_cost_uzs=Decimal("5000000"),
        started_at=date(2026, 4, 1),
    )


@pytest.fixture
def feedlot_batch(org, m_feedlot, house, chick_batch, user):
    return FeedlotBatch.objects.create(
        organization=org, module=m_feedlot,
        house_block=house, batch=chick_batch,
        doc_number="ФЛ-M-001", placed_date=date(2026, 4, 1),
        target_weight_kg=Decimal("2.500"),
        initial_heads=1000, current_heads=1000,
        status=FeedlotBatch.Status.GROWING,
        technologist=user,
    )


@pytest.fixture
def coa(org):
    """План счетов 91.02 + 20.02."""
    acc91, _ = GLAccount.objects.get_or_create(
        organization=org, code="91",
        defaults={"name": "Прочие", "type": "expense"},
    )
    acc20, _ = GLAccount.objects.get_or_create(
        organization=org, code="20",
        defaults={"name": "Производство", "type": "asset"},
    )
    GLSubaccount.objects.get_or_create(
        account=acc91, code="91.02",
        defaults={"name": "Прочие расходы"},
    )
    GLSubaccount.objects.get_or_create(
        account=acc20, code="20.02",
        defaults={"name": "Откорм НЗП"},
    )


def test_mortality_creates_writeoff_je(feedlot_batch, coa, user):
    """
    1000 голов, cost 5_000_000 → unit_cost 5000/гол.
    Падёж 10 голов → loss 50 000 сум, JE 91.02 / 20.02.
    Batch.accumulated_cost уменьшается на 50 000.
    """
    batch_cost_before = feedlot_batch.batch.accumulated_cost_uzs

    result = apply_mortality(
        feedlot_batch,
        date=date(2026, 4, 5),
        day_of_age=4,
        dead_count=10,
        cause="Стресс",
        user=user,
    )

    # JE создан
    assert result.journal_entry is not None
    assert result.journal_entry.debit_subaccount.code == "91.02"
    assert result.journal_entry.credit_subaccount.code == "20.02"
    assert result.loss_amount_uzs == Decimal("50000.00")
    assert result.journal_entry.amount_uzs == Decimal("50000.00")

    # Batch.cost уменьшился
    feedlot_batch.batch.refresh_from_db()
    assert feedlot_batch.batch.accumulated_cost_uzs == (
        batch_cost_before - Decimal("50000")
    )

    # Поголовье уменьшилось
    feedlot_batch.refresh_from_db()
    assert feedlot_batch.current_heads == 990


def test_mortality_zero_cost_no_je(feedlot_batch, coa, user):
    """Если у batch нет cost — loss=0, JE не создаётся."""
    feedlot_batch.batch.accumulated_cost_uzs = Decimal("0")
    feedlot_batch.batch.save(update_fields=["accumulated_cost_uzs"])

    result = apply_mortality(
        feedlot_batch,
        date=date(2026, 4, 5),
        day_of_age=4,
        dead_count=10,
        user=user,
    )
    assert result.journal_entry is None
    assert result.loss_amount_uzs == Decimal("0")
