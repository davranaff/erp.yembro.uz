"""
Тесты apply_vet_treatment.

Ключевые инварианты:
    1. stock_batch.current_quantity декрементируется.
    2. stock_batch → DEPLETED когда доходит до 0.
    3. StockMovement OUTGOING создан со склада vet.
    4. JournalEntry: Dr 20.XX (target module) / Cr 10.03.
    5. BatchCostEntry(VET) для target_batch.
    6. Batch.withdrawal_period_ends обновляется (treatment_date + days).
    7. Batch.withdrawal_period_ends НЕ уменьшается (max правило).
    8. После обновления Slaughter.clean() блокирует убой (интеграция Phase 5).
    9. Повторный apply → ValidationError.
    10. Атомарность.
"""
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.accounting.models import GLSubaccount, JournalEntry
from apps.batches.models import Batch, BatchCostEntry
from apps.counterparties.models import Counterparty
from apps.matochnik.models import BreedingHerd
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.slaughter.models import SlaughterShift
from apps.users.models import User
from apps.vet.models import VetDrug, VetStockBatch, VetTreatmentLog
from apps.vet.services.apply_treatment import (
    VetTreatmentApplyError,
    apply_vet_treatment,
)
from apps.warehouses.models import ProductionBlock, StockMovement, Warehouse


pytestmark = pytest.mark.django_db


# ─── fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_vet():
    return Module.objects.get(code="vet")


@pytest.fixture
def m_matochnik():
    return Module.objects.get(code="matochnik")


@pytest.fixture
def m_feedlot():
    return Module.objects.get(code="feedlot")


@pytest.fixture
def m_slaughter():
    return Module.objects.get(code="slaughter")


@pytest.fixture
def user():
    return User.objects.create(email="vet@y.local", full_name="Vet Tech")


@pytest.fixture
def unit_dose(org):
    return Unit.objects.get_or_create(
        organization=org, code="доз", defaults={"name": "Доза"}
    )[0]


@pytest.fixture
def unit_pcs(org):
    return Unit.objects.get_or_create(
        organization=org, code="шт", defaults={"name": "Штука"}
    )[0]


@pytest.fixture
def cat_vet(org):
    sub = GLSubaccount.objects.get(account__organization=org, code="10.03")
    return Category.objects.get_or_create(
        organization=org, name="Ветпрепараты",
        defaults={"default_gl_subaccount": sub},
    )[0]


@pytest.fixture
def cat_chick(org, unit_pcs):
    return Category.objects.get_or_create(
        organization=org, name="Птица живая"
    )[0]


@pytest.fixture
def nc_drug(org, cat_vet, unit_dose):
    return NomenclatureItem.objects.create(
        organization=org, sku="ВЕТ-В-01",
        name="Вакцина Ньюкасл",
        category=cat_vet, unit=unit_dose,
    )


@pytest.fixture
def chick_nom(org, cat_chick, unit_pcs):
    return NomenclatureItem.objects.create(
        organization=org, sku="ЖП-Сут-01", name="Цыпленок",
        category=cat_chick, unit=unit_pcs,
    )


@pytest.fixture
def drug(org, m_vet, nc_drug):
    return VetDrug.objects.create(
        organization=org, module=m_vet, nomenclature=nc_drug,
        drug_type="vaccine", administration_route="spray",
        default_withdrawal_days=0,
    )


@pytest.fixture
def supplier(org):
    return Counterparty.objects.create(
        organization=org, code="К-V-01", kind="supplier", name="Ветпоставка"
    )


@pytest.fixture
def vet_warehouse(org, m_vet):
    return Warehouse.objects.create(
        organization=org, module=m_vet, code="СК-ВЕТ",
        name="Склад ветаптеки",
    )


@pytest.fixture
def vet_lot(org, m_vet, drug, vet_warehouse, supplier, unit_dose):
    return VetStockBatch.objects.create(
        organization=org, module=m_vet, doc_number="ВП-L-001",
        drug=drug, lot_number="L-2403",
        warehouse=vet_warehouse, supplier=supplier,
        received_date=date.today(),
        expiration_date=date.today() + timedelta(days=365),
        quantity=Decimal("1000"), current_quantity=Decimal("1000"),
        unit=unit_dose, price_per_unit_uzs=Decimal("1800.00"),
        status=VetStockBatch.Status.AVAILABLE,
    )


@pytest.fixture
def feedlot_house(org, m_feedlot):
    return ProductionBlock.objects.create(
        organization=org, module=m_feedlot, code="А-1",
        name="Птичник А-1", kind=ProductionBlock.Kind.FEEDLOT,
    )


@pytest.fixture
def poultry_batch(org, m_feedlot, feedlot_house, chick_nom, unit_pcs):
    return Batch.objects.create(
        organization=org, doc_number="П-FL-001",
        nomenclature=chick_nom, unit=unit_pcs,
        origin_module=m_feedlot, current_module=m_feedlot,
        current_block=feedlot_house,
        current_quantity=Decimal("10000"),
        initial_quantity=Decimal("10000"),
        started_at=date.today(),
    )


def _build_treatment(
    *,
    org,
    m_vet,
    drug,
    vet_lot,
    target_batch=None,
    target_herd=None,
    target_block,
    dose_quantity=Decimal("5000"),
    withdrawal_period_days=0,
    treatment_date=None,
    user,
    unit_dose,
    doc_number="ВП-ЖЛ-001",
):
    return VetTreatmentLog.objects.create(
        organization=org, module=m_vet,
        doc_number=doc_number,
        treatment_date=treatment_date or date.today(),
        target_block=target_block,
        target_batch=target_batch,
        target_herd=target_herd,
        drug=drug,
        stock_batch=vet_lot,
        dose_quantity=dose_quantity,
        unit=unit_dose,
        heads_treated=10000,
        withdrawal_period_days=withdrawal_period_days,
        veterinarian=user,
        indication="routine",
    )


# ─── Core flow ───────────────────────────────────────────────────────────


def test_apply_decrements_stock_batch(
    org, m_vet, drug, vet_lot, poultry_batch, feedlot_house, user, unit_dose,
):
    t = _build_treatment(
        org=org, m_vet=m_vet, drug=drug, vet_lot=vet_lot,
        target_batch=poultry_batch, target_block=feedlot_house,
        dose_quantity=Decimal("400"), withdrawal_period_days=0,
        user=user, unit_dose=unit_dose,
    )
    apply_vet_treatment(t, user=user)
    vet_lot.refresh_from_db()
    assert vet_lot.current_quantity == Decimal("600.000")
    assert vet_lot.status == VetStockBatch.Status.AVAILABLE


def test_apply_marks_depleted_when_exhausted(
    org, m_vet, drug, vet_lot, poultry_batch, feedlot_house, user, unit_dose,
):
    t = _build_treatment(
        org=org, m_vet=m_vet, drug=drug, vet_lot=vet_lot,
        target_batch=poultry_batch, target_block=feedlot_house,
        dose_quantity=Decimal("1000"), withdrawal_period_days=0,
        user=user, unit_dose=unit_dose,
    )
    apply_vet_treatment(t, user=user)
    vet_lot.refresh_from_db()
    assert vet_lot.current_quantity == Decimal("0.000")
    assert vet_lot.status == VetStockBatch.Status.DEPLETED


def test_apply_creates_stock_movement(
    org, m_vet, drug, vet_lot, poultry_batch, feedlot_house, user, unit_dose,
    vet_warehouse,
):
    t = _build_treatment(
        org=org, m_vet=m_vet, drug=drug, vet_lot=vet_lot,
        target_batch=poultry_batch, target_block=feedlot_house,
        dose_quantity=Decimal("100"), user=user, unit_dose=unit_dose,
    )
    result = apply_vet_treatment(t, user=user)

    sm = result.stock_movement
    assert sm.kind == StockMovement.Kind.OUTGOING
    assert sm.warehouse_from_id == vet_warehouse.id
    assert sm.module_id == m_vet.id
    assert sm.quantity == Decimal("100")
    # 100 * 1800 = 180_000
    assert sm.amount_uzs == Decimal("180000.00")


def test_apply_creates_journal_20_to_10_03(
    org, m_vet, drug, vet_lot, poultry_batch, feedlot_house, user, unit_dose,
    m_feedlot,
):
    t = _build_treatment(
        org=org, m_vet=m_vet, drug=drug, vet_lot=vet_lot,
        target_batch=poultry_batch, target_block=feedlot_house,
        dose_quantity=Decimal("100"), user=user, unit_dose=unit_dose,
    )
    result = apply_vet_treatment(t, user=user)

    je = result.journal_entry
    # target_block.module = feedlot → Dr 20.02 / Cr 10.03
    assert je.debit_subaccount.code == "20.02"
    assert je.credit_subaccount.code == "10.03"
    assert je.module_id == m_feedlot.id
    assert je.amount_uzs == Decimal("180000.00")


def test_apply_creates_batch_cost_entry(
    org, m_vet, drug, vet_lot, poultry_batch, feedlot_house, user, unit_dose,
):
    initial_cost = poultry_batch.accumulated_cost_uzs
    t = _build_treatment(
        org=org, m_vet=m_vet, drug=drug, vet_lot=vet_lot,
        target_batch=poultry_batch, target_block=feedlot_house,
        dose_quantity=Decimal("100"), user=user, unit_dose=unit_dose,
    )
    result = apply_vet_treatment(t, user=user)

    assert result.batch_cost_entry is not None
    assert result.batch_cost_entry.category == BatchCostEntry.Category.VET
    assert result.batch_cost_entry.amount_uzs == Decimal("180000.00")

    poultry_batch.refresh_from_db()
    assert poultry_batch.accumulated_cost_uzs == initial_cost + Decimal("180000.00")


# ─── Withdrawal period (ядро безопасности!) ──────────────────────────────


def test_apply_sets_withdrawal_period_on_batch(
    org, m_vet, drug, vet_lot, poultry_batch, feedlot_house, user, unit_dose,
):
    assert poultry_batch.withdrawal_period_ends is None
    t = _build_treatment(
        org=org, m_vet=m_vet, drug=drug, vet_lot=vet_lot,
        target_batch=poultry_batch, target_block=feedlot_house,
        dose_quantity=Decimal("100"),
        withdrawal_period_days=5,
        treatment_date=date(2026, 4, 20),
        user=user, unit_dose=unit_dose,
    )
    result = apply_vet_treatment(t, user=user)

    poultry_batch.refresh_from_db()
    assert poultry_batch.withdrawal_period_ends == date(2026, 4, 25)
    assert result.new_withdrawal_end == date(2026, 4, 25)
    assert result.previous_withdrawal_end is None


def test_apply_never_shrinks_withdrawal_period(
    org, m_vet, drug, vet_lot, poultry_batch, feedlot_house, user, unit_dose,
):
    # Первое применение с 10-дневным выведением
    t1 = _build_treatment(
        org=org, m_vet=m_vet, drug=drug, vet_lot=vet_lot,
        target_batch=poultry_batch, target_block=feedlot_house,
        dose_quantity=Decimal("100"),
        withdrawal_period_days=10,
        treatment_date=date(2026, 4, 20),
        user=user, unit_dose=unit_dose,
        doc_number="ВП-Ж-01",
    )
    apply_vet_treatment(t1, user=user)
    poultry_batch.refresh_from_db()
    assert poultry_batch.withdrawal_period_ends == date(2026, 4, 30)

    # Второе применение с короткой каренцией — новая дата раньше → не меняем
    t2 = _build_treatment(
        org=org, m_vet=m_vet, drug=drug, vet_lot=vet_lot,
        target_batch=poultry_batch, target_block=feedlot_house,
        dose_quantity=Decimal("100"),
        withdrawal_period_days=3,
        treatment_date=date(2026, 4, 21),
        user=user, unit_dose=unit_dose,
        doc_number="ВП-Ж-02",
    )
    apply_vet_treatment(t2, user=user)
    poultry_batch.refresh_from_db()
    # max(30.04, 24.04) = 30.04
    assert poultry_batch.withdrawal_period_ends == date(2026, 4, 30)


def test_apply_blocks_slaughter_via_phase5_guard(
    org, m_vet, drug, vet_lot, poultry_batch, feedlot_house, user, unit_dose,
    m_slaughter,
):
    """
    Интеграция: после apply → Batch.withdrawal_period_ends установлен →
    попытка создать SlaughterShift блокируется через Phase 5 clean().
    """
    line = ProductionBlock.objects.create(
        organization=org, module=m_slaughter, code="ЛН-1",
        name="Линия", kind=ProductionBlock.Kind.SLAUGHTER_LINE,
    )

    t = _build_treatment(
        org=org, m_vet=m_vet, drug=drug, vet_lot=vet_lot,
        target_batch=poultry_batch, target_block=feedlot_house,
        dose_quantity=Decimal("100"),
        withdrawal_period_days=7,
        treatment_date=date.today(),
        user=user, unit_dose=unit_dose,
    )
    apply_vet_treatment(t, user=user)
    poultry_batch.refresh_from_db()

    # Симулируем приём партии в убойню (после accept_transfer):
    # current_module = slaughter — иначе SlaughterShift.clean() упадёт раньше.
    poultry_batch.current_module = m_slaughter
    poultry_batch.current_block = line
    poultry_batch.save(update_fields=["current_module", "current_block"])

    shift = SlaughterShift(
        organization=org, module=m_slaughter,
        line_block=line, source_batch=poultry_batch,
        doc_number="УБ-CHECK",
        shift_date=date.today(),  # В окне каренции!
        start_time=datetime.now(timezone.utc),
        live_heads_received=1000,
        live_weight_kg_total=Decimal("2500"),
        foreman=user,
    )
    with pytest.raises(ValidationError) as exc_info:
        shift.full_clean()
    # Ошибка должна быть именно про shift_date (Phase-5 guard)
    err = exc_info.value.message_dict if hasattr(exc_info.value, "message_dict") else {}
    assert "shift_date" in err


# ─── Guards ──────────────────────────────────────────────────────────────


def test_apply_twice_raises(
    org, m_vet, drug, vet_lot, poultry_batch, feedlot_house, user, unit_dose,
):
    t = _build_treatment(
        org=org, m_vet=m_vet, drug=drug, vet_lot=vet_lot,
        target_batch=poultry_batch, target_block=feedlot_house,
        dose_quantity=Decimal("100"), user=user, unit_dose=unit_dose,
    )
    apply_vet_treatment(t, user=user)
    with pytest.raises(ValidationError):
        apply_vet_treatment(t, user=user)


def test_apply_on_quarantine_lot_raises(
    org, m_vet, drug, vet_lot, poultry_batch, feedlot_house, user, unit_dose,
):
    vet_lot.status = VetStockBatch.Status.QUARANTINE
    vet_lot.save()
    t = _build_treatment(
        org=org, m_vet=m_vet, drug=drug, vet_lot=vet_lot,
        target_batch=poultry_batch, target_block=feedlot_house,
        dose_quantity=Decimal("100"), user=user, unit_dose=unit_dose,
    )
    with pytest.raises(ValidationError):
        apply_vet_treatment(t, user=user)


def test_apply_over_dose_raises(
    org, m_vet, drug, vet_lot, poultry_batch, feedlot_house, user, unit_dose,
):
    t = _build_treatment(
        org=org, m_vet=m_vet, drug=drug, vet_lot=vet_lot,
        target_batch=poultry_batch, target_block=feedlot_house,
        dose_quantity=Decimal("99999"),  # > 1000
        user=user, unit_dose=unit_dose,
    )
    with pytest.raises(ValidationError):
        apply_vet_treatment(t, user=user)


def test_apply_is_atomic_on_je_failure(
    org, m_vet, drug, vet_lot, poultry_batch, feedlot_house, user, unit_dose,
    monkeypatch,
):
    t = _build_treatment(
        org=org, m_vet=m_vet, drug=drug, vet_lot=vet_lot,
        target_batch=poultry_batch, target_block=feedlot_house,
        dose_quantity=Decimal("100"),
        withdrawal_period_days=5,
        user=user, unit_dose=unit_dose,
    )

    def broken(self, *a, **kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(JournalEntry, "save", broken)

    with pytest.raises(RuntimeError):
        apply_vet_treatment(t, user=user)

    vet_lot.refresh_from_db()
    poultry_batch.refresh_from_db()
    assert vet_lot.current_quantity == Decimal("1000.000")
    assert vet_lot.status == VetStockBatch.Status.AVAILABLE
    assert poultry_batch.withdrawal_period_ends is None
    assert not StockMovement.objects.filter(source_object_id=t.id).exists()
