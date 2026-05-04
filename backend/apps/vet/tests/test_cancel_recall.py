"""
Тесты cancel_vet_treatment и recall_vet_stock_batch (с реверсом лечений).
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.batches.models import Batch
from apps.counterparties.models import Counterparty
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.users.models import User
from apps.vet.models import (
    VetDrug,
    VetStockBatch,
    VetTreatmentLog,
)
from apps.vet.services.apply_treatment import apply_vet_treatment
from apps.vet.services.cancel import (
    VetTreatmentCancelError,
    cancel_vet_treatment,
)
from apps.vet.services.recall import VetRecallError, recall_vet_stock_batch
from apps.warehouses.models import ProductionBlock, Warehouse


pytestmark = pytest.mark.django_db


# ─── Фикстуры ──────────────────────────────────────────────────────


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_vet():
    return Module.objects.get(code="vet")


@pytest.fixture
def m_feedlot():
    return Module.objects.get(code="feedlot")


@pytest.fixture
def user():
    return User.objects.create(email="cv@y.local", full_name="CV")


@pytest.fixture
def unit_dose(org):
    return Unit.objects.get_or_create(
        organization=org, code="доз", defaults={"name": "доза"}
    )[0]


@pytest.fixture
def unit_pcs(org):
    return Unit.objects.get_or_create(
        organization=org, code="шт", defaults={"name": "шт"}
    )[0]


@pytest.fixture
def cat(org):
    return Category.objects.get_or_create(organization=org, name="Ветпрепараты-CR")[0]


@pytest.fixture
def cat_live(org):
    return Category.objects.get_or_create(organization=org, name="Птица-CR")[0]


@pytest.fixture
def nom_drug(org, cat, unit_dose):
    return NomenclatureItem.objects.create(
        organization=org, sku="ВП-CR-01", name="Препарат CR",
        category=cat, unit=unit_dose,
    )


@pytest.fixture
def nom_chick(org, cat_live, unit_pcs):
    return NomenclatureItem.objects.create(
        organization=org, sku="ЖП-CR-01", name="Цыплёнок CR",
        category=cat_live, unit=unit_pcs,
    )


@pytest.fixture
def drug(org, m_vet, nom_drug):
    return VetDrug.objects.create(
        organization=org, module=m_vet, nomenclature=nom_drug,
        drug_type="antibiotic", administration_route="injection",
        default_withdrawal_days=7,
    )


@pytest.fixture
def vet_warehouse(org, m_vet):
    return Warehouse.objects.create(
        organization=org, module=m_vet, code="СК-ВП-CR", name="СкВП CR",
    )


@pytest.fixture
def supplier(org):
    return Counterparty.objects.create(
        organization=org, code="К-CR-01", kind="supplier", name="Поставщик CR",
    )


@pytest.fixture
def feedlot_block(org, m_feedlot):
    return ProductionBlock.objects.create(
        organization=org, module=m_feedlot, code="ПТ-CR",
        name="Птичник CR", kind=ProductionBlock.Kind.FEEDLOT,
    )


@pytest.fixture
def vet_lot(org, m_vet, drug, vet_warehouse, supplier, unit_dose):
    return VetStockBatch.objects.create(
        organization=org, module=m_vet,
        doc_number="ВП-CR-LOT", drug=drug, lot_number="L-CR-001",
        warehouse=vet_warehouse, supplier=supplier,
        received_date=date.today(),
        expiration_date=date.today() + timedelta(days=180),
        quantity=Decimal("1000"), current_quantity=Decimal("1000"),
        unit=unit_dose, price_per_unit_uzs=Decimal("500"),
        status=VetStockBatch.Status.AVAILABLE,
        barcode="VET-CR-TEST-AAAA",
    )


@pytest.fixture
def poultry_batch(org, m_feedlot, feedlot_block, nom_chick, unit_pcs):
    return Batch.objects.create(
        organization=org, doc_number="ПР-CR-BATCH",
        nomenclature=nom_chick, unit=unit_pcs,
        origin_module=m_feedlot, current_module=m_feedlot,
        current_block=feedlot_block,
        current_quantity=Decimal("1000"),
        initial_quantity=Decimal("1000"),
        accumulated_cost_uzs=Decimal("500000"),
        started_at=date.today(),
    )


_treatment_counter = {"n": 0}


def _build_treatment(*, org, m_vet, drug, vet_lot, poultry_batch, feedlot_block,
                     user, unit_dose, dose=Decimal("100"), withdrawal=7):
    _treatment_counter["n"] += 1
    return VetTreatmentLog.objects.create(
        organization=org, module=m_vet,
        doc_number=f"ВЛ-CR-{_treatment_counter['n']:04d}",
        treatment_date=date.today(),
        target_block=feedlot_block,
        target_batch=poultry_batch,
        drug=drug, stock_batch=vet_lot,
        dose_quantity=dose, unit=unit_dose,
        heads_treated=1000, withdrawal_period_days=withdrawal,
        veterinarian=user, indication="prophylaxis",
    )


# ─── Тесты cancel ─────────────────────────────────────────────────


def test_cancel_creates_reversal_je_and_returns_stock(
    org, m_vet, drug, vet_lot, poultry_batch, feedlot_block, user, unit_dose,
):
    t = _build_treatment(
        org=org, m_vet=m_vet, drug=drug, vet_lot=vet_lot,
        poultry_batch=poultry_batch, feedlot_block=feedlot_block,
        user=user, unit_dose=unit_dose,
    )
    apply_vet_treatment(t, user=user)

    vet_lot.refresh_from_db()
    qty_after_apply = vet_lot.current_quantity
    assert qty_after_apply == Decimal("900")

    poultry_batch.refresh_from_db()
    assert poultry_batch.withdrawal_period_ends is not None

    # Cancel
    result = cancel_vet_treatment(t, reason="ошибка ввода дозы", user=user)

    t.refresh_from_db()
    vet_lot.refresh_from_db()
    poultry_batch.refresh_from_db()

    # 1. Cancelled fields
    assert t.cancelled_at is not None
    assert t.cancel_reason == "ошибка ввода дозы"
    # 2. Stock returned
    assert vet_lot.current_quantity == Decimal("1000")
    # 3. Reversal JE
    assert result.reversal_je is not None
    assert result.reversal_je.amount_uzs == Decimal("50000.00")
    # 4. withdrawal сброшен (нет других активных лечений)
    assert poultry_batch.withdrawal_period_ends is None


def test_cancel_without_reason_raises(
    org, m_vet, drug, vet_lot, poultry_batch, feedlot_block, user, unit_dose,
):
    t = _build_treatment(
        org=org, m_vet=m_vet, drug=drug, vet_lot=vet_lot,
        poultry_batch=poultry_batch, feedlot_block=feedlot_block,
        user=user, unit_dose=unit_dose,
    )
    apply_vet_treatment(t, user=user)
    with pytest.raises(VetTreatmentCancelError):
        cancel_vet_treatment(t, reason="ok", user=user)  # < 3 симв.


def test_cancel_twice_raises(
    org, m_vet, drug, vet_lot, poultry_batch, feedlot_block, user, unit_dose,
):
    t = _build_treatment(
        org=org, m_vet=m_vet, drug=drug, vet_lot=vet_lot,
        poultry_batch=poultry_batch, feedlot_block=feedlot_block,
        user=user, unit_dose=unit_dose,
    )
    apply_vet_treatment(t, user=user)
    cancel_vet_treatment(t, reason="ошибка", user=user)
    with pytest.raises(VetTreatmentCancelError):
        cancel_vet_treatment(t, reason="ещё раз", user=user)


def test_cancel_recalculates_withdrawal_with_other_treatments(
    org, m_vet, drug, vet_lot, poultry_batch, feedlot_block, user, unit_dose,
):
    """Если есть второе активное лечение — withdrawal пересчитывается на него."""
    # T1: withdrawal=7, treatment_date=today
    t1 = _build_treatment(
        org=org, m_vet=m_vet, drug=drug, vet_lot=vet_lot,
        poultry_batch=poultry_batch, feedlot_block=feedlot_block,
        user=user, unit_dose=unit_dose, withdrawal=7,
    )
    apply_vet_treatment(t1, user=user)

    # T2: withdrawal=3, treatment_date=today (т.е. позже истекает чем сейчас → 3 дня)
    t2 = _build_treatment(
        org=org, m_vet=m_vet, drug=drug, vet_lot=vet_lot,
        poultry_batch=poultry_batch, feedlot_block=feedlot_block,
        user=user, unit_dose=unit_dose, withdrawal=3, dose=Decimal("50"),
    )
    apply_vet_treatment(t2, user=user)
    poultry_batch.refresh_from_db()
    assert poultry_batch.withdrawal_period_ends == date.today() + timedelta(days=7)

    # Отменяем T1 (большее окно) → withdrawal должен схлопнуться до T2 = +3
    cancel_vet_treatment(t1, reason="отмена T1", user=user)
    poultry_batch.refresh_from_db()
    assert poultry_batch.withdrawal_period_ends == date.today() + timedelta(days=3)


# ─── Тесты recall ─────────────────────────────────────────────────


def test_recall_cancels_all_treatments(
    org, m_vet, drug, vet_lot, poultry_batch, feedlot_block, user, unit_dose,
):
    t = _build_treatment(
        org=org, m_vet=m_vet, drug=drug, vet_lot=vet_lot,
        poultry_batch=poultry_batch, feedlot_block=feedlot_block,
        user=user, unit_dose=unit_dose,
    )
    apply_vet_treatment(t, user=user)

    poultry_batch.refresh_from_db()
    assert poultry_batch.withdrawal_period_ends is not None

    result = recall_vet_stock_batch(
        vet_lot, reason="брак производителя", user=user,
    )

    vet_lot.refresh_from_db()
    t.refresh_from_db()
    poultry_batch.refresh_from_db()

    assert vet_lot.status == VetStockBatch.Status.RECALLED
    assert vet_lot.recalled_at is not None
    assert vet_lot.recall_reason == "брак производителя"
    assert vet_lot.current_quantity == 0
    assert t.cancelled_at is not None
    assert "recall" in t.cancel_reason.lower()
    # withdrawal на партии сброшен
    assert poultry_batch.withdrawal_period_ends is None
    # cancelled_treatments в результате
    assert len(result.cancelled_treatments) == 1


def test_recall_already_recalled_raises(org, m_vet, drug, vet_lot, user):
    vet_lot.status = VetStockBatch.Status.RECALLED
    vet_lot.save()
    with pytest.raises(VetRecallError):
        recall_vet_stock_batch(vet_lot, reason="попытка повтора", user=user)


def test_recall_short_reason_raises(org, m_vet, drug, vet_lot, user):
    with pytest.raises(VetRecallError):
        recall_vet_stock_batch(vet_lot, reason="X", user=user)
