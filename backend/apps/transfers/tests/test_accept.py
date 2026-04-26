"""
Тесты accept_transfer: poultry batch + feed dispatch.

Ключевые инварианты:
    1. Poultry: JE через 79.01 (пара), StockMovement пара, BatchChainStep
       закрывается+открывается, Batch.current_module/block/quantity обновляются,
       accumulated_cost_uzs накапливается.
    2. Feed: feed_batch.current_quantity_kg декрементируется.
    3. Medicated feed → withdrawal_period_ends переносится на consumer batches,
       после чего Slaughter.clean() блокирует убой (Phase 5 guard).
    4. FSM: accept из DRAFT → ValidationError.
    5. Атомарность: если JE.save() падает — ничего не сохранилось.
    6. Идемпотентность: повторный accept → ValidationError.
"""
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.accounting.models import GLSubaccount, JournalEntry
from apps.batches.models import Batch, BatchChainStep, BatchCostEntry
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.transfers.models import InterModuleTransfer
from apps.transfers.services.accept import (
    TransferAcceptError,
    accept_transfer,
    submit_transfer,
)
from apps.warehouses.models import ProductionBlock, StockMovement, Warehouse


pytestmark = pytest.mark.django_db


# ─── fixtures ────────────────────────────────────────────────────────────


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
def m_feed():
    return Module.objects.get(code="feed")


@pytest.fixture
def m_feedlot():
    return Module.objects.get(code="feedlot")


@pytest.fixture
def m_slaughter():
    return Module.objects.get(code="slaughter")


@pytest.fixture
def unit_pcs(org):
    return Unit.objects.get_or_create(
        organization=org, code="шт", defaults={"name": "Штука"}
    )[0]


@pytest.fixture
def unit_kg(org):
    return Unit.objects.get_or_create(
        organization=org, code="кг", defaults={"name": "Килограмм"}
    )[0]


@pytest.fixture
def cat_eggs(org):
    sub_1002 = GLSubaccount.objects.get(account__organization=org, code="10.02")
    return Category.objects.get_or_create(
        organization=org,
        name="Яйцо",
        defaults={"default_gl_subaccount": sub_1002},
    )[0]


@pytest.fixture
def cat_feed(org):
    sub = GLSubaccount.objects.get(account__organization=org, code="10.05")
    return Category.objects.get_or_create(
        organization=org,
        name="Корма готовые",
        defaults={"default_gl_subaccount": sub},
    )[0]


@pytest.fixture
def egg(org, cat_eggs, unit_pcs):
    return NomenclatureItem.objects.create(
        organization=org,
        sku="СЫ-Инк-01",
        name="Инкубационное яйцо",
        category=cat_eggs,
        unit=unit_pcs,
    )


@pytest.fixture
def feed_nom(org, cat_feed, unit_kg):
    return NomenclatureItem.objects.create(
        organization=org,
        sku="КМ-БР-СТ",
        name="Старт бройлера",
        category=cat_feed,
        unit=unit_kg,
    )


@pytest.fixture
def matochnik_corpus(org, m_matochnik):
    return ProductionBlock.objects.create(
        organization=org, module=m_matochnik, code="К-01",
        name="Корпус №1", kind=ProductionBlock.Kind.MATOCHNIK,
    )


@pytest.fixture
def matochnik_wh(org, m_matochnik, matochnik_corpus):
    return Warehouse.objects.create(
        organization=org, module=m_matochnik,
        code="СК-М-ЯЙЦО", name="Склад яиц маточника",
        production_block=matochnik_corpus,
    )


@pytest.fixture
def incubation_cabinet(org, m_incubation):
    return ProductionBlock.objects.create(
        organization=org, module=m_incubation, code="ШК-1",
        name="Инкубатор №1", kind=ProductionBlock.Kind.INCUBATION,
    )


@pytest.fixture
def incubation_wh(org, m_incubation, incubation_cabinet):
    return Warehouse.objects.create(
        organization=org, module=m_incubation,
        code="СК-И", name="Склад инкубации",
        production_block=incubation_cabinet,
    )


@pytest.fixture
def egg_batch(org, egg, unit_pcs, m_matochnik, matochnik_corpus):
    return Batch.objects.create(
        organization=org,
        doc_number="П-2401",
        nomenclature=egg,
        unit=unit_pcs,
        origin_module=m_matochnik,
        current_module=m_matochnik,
        current_block=matochnik_corpus,
        current_quantity=Decimal("38900"),
        initial_quantity=Decimal("38900"),
        accumulated_cost_uzs=Decimal("5000000.00"),  # уже накоплено в маточнике
        started_at=date(2026, 3, 5),
    )


@pytest.fixture
def egg_chain_step_in_matochnik(egg_batch, m_matochnik, matochnik_corpus):
    return BatchChainStep.objects.create(
        batch=egg_batch,
        sequence=1,
        module=m_matochnik,
        block=matochnik_corpus,
        entered_at=datetime(2026, 3, 5, tzinfo=timezone.utc),
        quantity_in=Decimal("38900"),
    )


# ─── Poultry batch transfer: М→И ─────────────────────────────────────────


def test_poultry_accept_posts_paired_je_and_sm(
    org,
    m_matochnik,
    m_incubation,
    matochnik_corpus,
    incubation_cabinet,
    matochnik_wh,
    incubation_wh,
    egg,
    unit_pcs,
    egg_batch,
    egg_chain_step_in_matochnik,
):
    transfer = InterModuleTransfer.objects.create(
        organization=org,
        doc_number="",
        transfer_date=datetime(2026, 3, 20, 10, 0, tzinfo=timezone.utc),
        from_module=m_matochnik,
        to_module=m_incubation,
        from_block=matochnik_corpus,
        to_block=incubation_cabinet,
        from_warehouse=matochnik_wh,
        to_warehouse=incubation_wh,
        nomenclature=egg,
        unit=unit_pcs,
        quantity=Decimal("38900"),
        cost_uzs=Decimal("5000000.00"),
        batch=egg_batch,
        state=InterModuleTransfer.State.AWAITING_ACCEPTANCE,
    )

    result = accept_transfer(transfer)

    # State → POSTED
    assert result.transfer.state == InterModuleTransfer.State.POSTED
    assert result.transfer.posted_at is not None
    assert result.transfer.doc_number.startswith("ММ-2026-")

    # JE пара
    assert result.journal_sender.debit_subaccount.code == "79.01"
    assert result.journal_sender.credit_subaccount.code == "10.02"  # Живая птица → но у нас egg
    # Фактически через categor.default_gl_subaccount = 10.02
    assert result.journal_receiver.debit_subaccount.code == "10.02"
    assert result.journal_receiver.credit_subaccount.code == "79.01"
    assert result.journal_sender.module_id == m_matochnik.id
    assert result.journal_receiver.module_id == m_incubation.id
    assert result.journal_sender.amount_uzs == Decimal("5000000.00")

    # SM пара
    assert result.stock_outgoing.kind == StockMovement.Kind.OUTGOING
    assert result.stock_outgoing.warehouse_from_id == matochnik_wh.id
    assert result.stock_incoming.kind == StockMovement.Kind.INCOMING
    assert result.stock_incoming.warehouse_to_id == incubation_wh.id
    assert result.stock_outgoing.amount_uzs == Decimal("5000000.00")


def test_poultry_accept_updates_batch_and_chain(
    org,
    m_matochnik,
    m_incubation,
    matochnik_corpus,
    incubation_cabinet,
    matochnik_wh,
    incubation_wh,
    egg,
    unit_pcs,
    egg_batch,
    egg_chain_step_in_matochnik,
):
    transfer = InterModuleTransfer.objects.create(
        organization=org,
        doc_number="",
        transfer_date=datetime(2026, 3, 20, 10, 0, tzinfo=timezone.utc),
        from_module=m_matochnik,
        to_module=m_incubation,
        from_block=matochnik_corpus,
        to_block=incubation_cabinet,
        from_warehouse=matochnik_wh,
        to_warehouse=incubation_wh,
        nomenclature=egg,
        unit=unit_pcs,
        quantity=Decimal("38900"),
        cost_uzs=Decimal("5000000.00"),
        batch=egg_batch,
        state=InterModuleTransfer.State.AWAITING_ACCEPTANCE,
    )

    accept_transfer(transfer)

    egg_batch.refresh_from_db()
    assert egg_batch.current_module_id == m_incubation.id
    assert egg_batch.current_block_id == incubation_cabinet.id
    assert egg_batch.current_quantity == Decimal("38900")
    # Было 5_000_000, добавили cost_uzs=5_000_000 → 10_000_000 (накопление)
    assert egg_batch.accumulated_cost_uzs == Decimal("10000000.00")

    # Chain step #1 закрыт
    egg_chain_step_in_matochnik.refresh_from_db()
    assert egg_chain_step_in_matochnik.exited_at is not None
    assert egg_chain_step_in_matochnik.quantity_out == Decimal("38900")
    assert egg_chain_step_in_matochnik.accumulated_cost_at_exit == Decimal("5000000.00")

    # Chain step #2 открыт в incubation
    step2 = egg_batch.chain_steps.get(sequence=2)
    assert step2.module_id == m_incubation.id
    assert step2.block_id == incubation_cabinet.id
    assert step2.exited_at is None
    assert step2.quantity_in == Decimal("38900")


def test_poultry_accept_wrong_current_module_raises(
    org,
    m_matochnik,
    m_incubation,
    m_feedlot,
    matochnik_corpus,
    incubation_cabinet,
    matochnik_wh,
    incubation_wh,
    egg,
    unit_pcs,
    egg_batch,
):
    # Partия уже в feedlot, transfer заявлен от matochnik → ошибка
    egg_batch.current_module = m_feedlot
    egg_batch.save()

    transfer = InterModuleTransfer.objects.create(
        organization=org,
        doc_number="",
        transfer_date=datetime(2026, 3, 20, 10, 0, tzinfo=timezone.utc),
        from_module=m_matochnik,
        to_module=m_incubation,
        from_warehouse=matochnik_wh,
        to_warehouse=incubation_wh,
        nomenclature=egg,
        unit=unit_pcs,
        quantity=Decimal("38900"),
        cost_uzs=Decimal("5000000.00"),
        batch=egg_batch,
        state=InterModuleTransfer.State.AWAITING_ACCEPTANCE,
    )
    with pytest.raises(ValidationError):
        accept_transfer(transfer)


# ─── Feed dispatch ───────────────────────────────────────────────────────


@pytest.fixture
def feed_storage_bin(org, m_feed):
    return ProductionBlock.objects.create(
        organization=org, module=m_feed, code="БН-3",
        name="Бункер №3", kind=ProductionBlock.Kind.STORAGE_BIN,
    )


@pytest.fixture
def feed_wh(org, m_feed, feed_storage_bin):
    return Warehouse.objects.create(
        organization=org, module=m_feed,
        code="СК-ГК", name="Склад готового корма",
        production_block=feed_storage_bin,
    )


@pytest.fixture
def feedlot_house(org, m_feedlot):
    return ProductionBlock.objects.create(
        organization=org, module=m_feedlot, code="А-1",
        name="Птичник А-1", kind=ProductionBlock.Kind.FEEDLOT,
    )


@pytest.fixture
def feedlot_wh(org, m_feedlot, feedlot_house):
    return Warehouse.objects.create(
        organization=org, module=m_feedlot,
        code="СК-Ф", name="Склад фабрики",
        production_block=feedlot_house,
    )


@pytest.fixture
def feed_batch_medicated(org, m_feed, feed_storage_bin, feed_wh, feed_nom):
    """Готовая партия корма, медикаментозная, withdrawal_period_ends = today+5."""
    from apps.feed.models import Recipe, RecipeVersion, ProductionTask, FeedBatch
    from apps.users.models import User

    user, _ = User.objects.get_or_create(
        email="tech@y.local", defaults={"full_name": "Tech"}
    )

    recipe = Recipe.objects.create(
        organization=org, code="Р-MED", name="Медикамент. старт",
        direction="broiler", is_medicated=True,
    )
    rv = RecipeVersion.objects.create(
        recipe=recipe, version_number=1, status="active",
        effective_from=date(2026, 1, 1),
    )
    # Нужна линия для task
    line = ProductionBlock.objects.create(
        organization=org, module=m_feed, code="СМ-1",
        name="Линия 1", kind=ProductionBlock.Kind.MIXER_LINE,
    )
    task = ProductionTask.objects.create(
        organization=org, module=m_feed, doc_number="ЗП-001",
        recipe_version=rv, production_line=line, shift="day",
        scheduled_at=datetime.now(timezone.utc),
        planned_quantity_kg=Decimal("1000"),
        actual_quantity_kg=Decimal("1000"),
        status="done", is_medicated=True, withdrawal_period_days=5,
        technologist=user, completed_at=datetime.now(timezone.utc),
    )
    return FeedBatch.objects.create(
        organization=org, module=m_feed, doc_number="К-MED-001",
        produced_by_task=task, recipe_version=rv,
        produced_at=datetime.now(timezone.utc),
        quantity_kg=Decimal("1000"),
        current_quantity_kg=Decimal("1000"),
        unit_cost_uzs=Decimal("5000.00"),
        total_cost_uzs=Decimal("5000000.00"),
        storage_bin=feed_storage_bin,
        storage_warehouse=feed_wh,
        status="approved",
        is_medicated=True,
        withdrawal_period_days=5,
        withdrawal_period_ends=date.today() + timedelta(days=5),
        quality_passport_status="passed",
    )


def test_feed_dispatch_decrements_feed_batch(
    org, m_feed, m_feedlot, feed_storage_bin, feedlot_house,
    feed_wh, feedlot_wh, feed_nom, unit_kg, feed_batch_medicated,
):
    assert feed_batch_medicated.current_quantity_kg == Decimal("1000")

    transfer = InterModuleTransfer.objects.create(
        organization=org, doc_number="",
        transfer_date=datetime.now(timezone.utc),
        from_module=m_feed, to_module=m_feedlot,
        from_block=feed_storage_bin, to_block=feedlot_house,
        from_warehouse=feed_wh, to_warehouse=feedlot_wh,
        nomenclature=feed_nom, unit=unit_kg,
        quantity=Decimal("300"), cost_uzs=Decimal("1500000.00"),
        feed_batch=feed_batch_medicated,
        state=InterModuleTransfer.State.AWAITING_ACCEPTANCE,
    )

    accept_transfer(transfer)

    feed_batch_medicated.refresh_from_db()
    assert feed_batch_medicated.current_quantity_kg == Decimal("700.000")


def test_feed_dispatch_propagates_withdrawal_to_batch(
    org, m_feed, m_feedlot, feed_storage_bin, feedlot_house,
    feed_wh, feedlot_wh, feed_nom, unit_kg, feed_batch_medicated, unit_pcs,
):
    """
    Медикаментозный корм приходит в feedlot → withdrawal_period_ends
    переносится на активные Batch → slaughter-guard блокирует убой.
    """
    from apps.nomenclature.models import Category, NomenclatureItem

    cat_chick = Category.objects.get_or_create(
        organization=org, name="Птица живая"
    )[0]
    chick_sku = NomenclatureItem.objects.create(
        organization=org, sku="ЖП-Сут-01", name="Цыпленок",
        category=cat_chick, unit=unit_pcs,
    )
    feedlot_batch = Batch.objects.create(
        organization=org, doc_number="П-FL-001", nomenclature=chick_sku,
        unit=unit_pcs, origin_module=m_feedlot, current_module=m_feedlot,
        current_block=feedlot_house,
        current_quantity=Decimal("10000"), initial_quantity=Decimal("10000"),
        started_at=date.today(),
    )
    assert feedlot_batch.withdrawal_period_ends is None

    transfer = InterModuleTransfer.objects.create(
        organization=org, doc_number="",
        transfer_date=datetime.now(timezone.utc),
        from_module=m_feed, to_module=m_feedlot,
        from_block=feed_storage_bin, to_block=feedlot_house,
        from_warehouse=feed_wh, to_warehouse=feedlot_wh,
        nomenclature=feed_nom, unit=unit_kg,
        quantity=Decimal("300"), cost_uzs=Decimal("1500000.00"),
        feed_batch=feed_batch_medicated,
        state=InterModuleTransfer.State.AWAITING_ACCEPTANCE,
    )
    result = accept_transfer(transfer)

    feedlot_batch.refresh_from_db()
    assert feedlot_batch.withdrawal_period_ends == feed_batch_medicated.withdrawal_period_ends
    assert feedlot_batch in result.affected_batches


# ─── FSM guards ──────────────────────────────────────────────────────────


def test_cannot_accept_draft(
    org, m_matochnik, m_incubation, egg, unit_pcs, egg_batch,
    matochnik_wh, incubation_wh,
):
    transfer = InterModuleTransfer.objects.create(
        organization=org, doc_number="",
        transfer_date=datetime.now(timezone.utc),
        from_module=m_matochnik, to_module=m_incubation,
        from_warehouse=matochnik_wh, to_warehouse=incubation_wh,
        nomenclature=egg, unit=unit_pcs,
        quantity=Decimal("100"), cost_uzs=Decimal("1000"),
        batch=egg_batch,
        state=InterModuleTransfer.State.DRAFT,
    )
    with pytest.raises(ValidationError):
        accept_transfer(transfer)


def test_double_accept_fails(
    org, m_matochnik, m_incubation, matochnik_corpus, incubation_cabinet,
    matochnik_wh, incubation_wh, egg, unit_pcs, egg_batch,
    egg_chain_step_in_matochnik,
):
    transfer = InterModuleTransfer.objects.create(
        organization=org, doc_number="",
        transfer_date=datetime.now(timezone.utc),
        from_module=m_matochnik, to_module=m_incubation,
        from_block=matochnik_corpus, to_block=incubation_cabinet,
        from_warehouse=matochnik_wh, to_warehouse=incubation_wh,
        nomenclature=egg, unit=unit_pcs,
        quantity=Decimal("38900"), cost_uzs=Decimal("1000"),
        batch=egg_batch,
        state=InterModuleTransfer.State.AWAITING_ACCEPTANCE,
    )
    accept_transfer(transfer)
    with pytest.raises(ValidationError):
        accept_transfer(transfer)


def test_submit_transitions_draft_to_awaiting(
    org, m_matochnik, m_incubation, egg, unit_pcs, egg_batch,
    matochnik_wh, incubation_wh,
):
    transfer = InterModuleTransfer.objects.create(
        organization=org, doc_number="",
        transfer_date=datetime.now(timezone.utc),
        from_module=m_matochnik, to_module=m_incubation,
        from_warehouse=matochnik_wh, to_warehouse=incubation_wh,
        nomenclature=egg, unit=unit_pcs,
        quantity=Decimal("38900"), cost_uzs=Decimal("1000"),
        batch=egg_batch,
    )
    assert transfer.state == InterModuleTransfer.State.DRAFT
    submit_transfer(transfer)
    transfer.refresh_from_db()
    assert transfer.state == InterModuleTransfer.State.AWAITING_ACCEPTANCE


def test_accept_is_atomic_on_je_failure(
    org, m_matochnik, m_incubation, matochnik_corpus, incubation_cabinet,
    matochnik_wh, incubation_wh, egg, unit_pcs, egg_batch,
    egg_chain_step_in_matochnik, monkeypatch,
):
    transfer = InterModuleTransfer.objects.create(
        organization=org, doc_number="",
        transfer_date=datetime.now(timezone.utc),
        from_module=m_matochnik, to_module=m_incubation,
        from_block=matochnik_corpus, to_block=incubation_cabinet,
        from_warehouse=matochnik_wh, to_warehouse=incubation_wh,
        nomenclature=egg, unit=unit_pcs,
        quantity=Decimal("38900"), cost_uzs=Decimal("5000000.00"),
        batch=egg_batch,
        state=InterModuleTransfer.State.AWAITING_ACCEPTANCE,
    )

    original_save = JournalEntry.save

    def broken(self, *a, **kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(JournalEntry, "save", broken)

    with pytest.raises(RuntimeError):
        accept_transfer(transfer)

    # Откат: transfer остался awaiting, batch не тронут
    transfer.refresh_from_db()
    egg_batch.refresh_from_db()
    assert transfer.state == InterModuleTransfer.State.AWAITING_ACCEPTANCE
    assert egg_batch.current_module_id == m_matochnik.id
    assert egg_batch.accumulated_cost_uzs == Decimal("5000000.00")
    assert not StockMovement.objects.filter(source_object_id=transfer.id).exists()
