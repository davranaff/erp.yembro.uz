"""
End-to-end тесты wizard'а `/aralash` (замес).

Проверяем:
  - happy path с auto-pick склада/бункера (по 1 элементу) → execute_production_task
  - ввод actual qty
  - кнопка «= План» → актуал = планируемый
  - cancel чистит сессию
  - отсутствие PLANNED задач → wizard не запускается
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.accounting.models import GLSubaccount
from apps.counterparties.models import Counterparty
from apps.feed.models import (
    FeedBatch, ProductionTask, ProductionTaskComponent,
    RawMaterialBatch, Recipe, RecipeVersion,
)
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.tgbot.dispatcher import dispatch_callback, dispatch_message
from apps.tgbot.models import TgWizardSession
from apps.warehouses.models import ProductionBlock, Warehouse


pytestmark = pytest.mark.django_db


# ─── Fixtures (минимально для замеса) ───────────────────────────────────


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_feed():
    return Module.objects.get(code="feed")


@pytest.fixture
def unit_kg(org):
    return Unit.objects.get_or_create(
        organization=org, code="кг", defaults={"name": "Килограмм"}
    )[0]


@pytest.fixture
def cat_raw(org, m_feed):
    sub = GLSubaccount.objects.get(account__organization=org, code="10.01")
    return Category.objects.get_or_create(
        organization=org, name="Корма сырьё (mix)",
        defaults={"default_gl_subaccount": sub, "module": m_feed},
    )[0]


@pytest.fixture
def corn(org, cat_raw, unit_kg):
    return NomenclatureItem.objects.create(
        organization=org, sku="С-КУК-MIX", name="Кукуруза MIX",
        category=cat_raw, unit=unit_kg,
    )


@pytest.fixture
def supplier(org):
    return Counterparty.objects.create(
        organization=org, code="К-S-MIX", kind="supplier", name="Поставщик MIX",
    )


@pytest.fixture
def raw_warehouse(org, m_feed):
    return Warehouse.objects.create(
        organization=org, module=m_feed, code="СК-СР-MIX", name="Склад сырья MIX",
    )


@pytest.fixture
def ready_warehouse(org, m_feed):
    return Warehouse.objects.create(
        organization=org, module=m_feed, code="СК-ГК-MIX", name="Склад готового MIX",
    )


@pytest.fixture
def storage_bin(org, m_feed):
    return ProductionBlock.objects.create(
        organization=org, module=m_feed, code="БН-MIX", name="Бункер MIX",
        kind=ProductionBlock.Kind.STORAGE_BIN,
    )


@pytest.fixture
def mixer_line(org, m_feed):
    return ProductionBlock.objects.create(
        organization=org, module=m_feed, code="СМ-MIX", name="Смеситель MIX",
        kind=ProductionBlock.Kind.MIXER_LINE,
    )


@pytest.fixture
def corn_batch(org, m_feed, corn, supplier, raw_warehouse, unit_kg):
    return RawMaterialBatch.objects.create(
        organization=org, module=m_feed, doc_number="П-К-MIX",
        nomenclature=corn, supplier=supplier, warehouse=raw_warehouse,
        received_date=date(2026, 4, 1),
        quantity=Decimal("5000"), current_quantity=Decimal("5000"),
        unit=unit_kg, price_per_unit_uzs=Decimal("18000.00"),
        status=RawMaterialBatch.Status.AVAILABLE,
    )


@pytest.fixture
def recipe(org):
    """Рецепт + сигналы создадут NomenclatureItem(sku=recipe.code)."""
    return Recipe.objects.create(
        organization=org, code="Р-MIX", name="Старт-MIX", direction="broiler",
    )


@pytest.fixture
def recipe_version(recipe):
    return RecipeVersion.objects.create(
        recipe=recipe, version_number=1,
        status="active", effective_from=date(2026, 1, 1),
    )


@pytest.fixture
def planned_task(
    org, m_feed, recipe_version, mixer_line, corn, corn_batch, tg_link,
):
    """PLANNED task с одним компонентом (corn)."""
    t = ProductionTask.objects.create(
        organization=org, module=m_feed, doc_number="ЗП-MIX-001",
        recipe_version=recipe_version, production_line=mixer_line,
        shift="day",
        scheduled_at=datetime.now(timezone.utc),
        planned_quantity_kg=Decimal("1000"),
        status=ProductionTask.Status.PLANNED,
        technologist=tg_link.user,
    )
    ProductionTaskComponent.objects.create(
        task=t, nomenclature=corn, source_batch=corn_batch,
        planned_quantity=Decimal("1000"),
        planned_price_per_unit_uzs=Decimal("18000"),
        sort_order=1,
    )
    return t


@pytest.fixture
def admin_link(db, tg_link):
    """Доступ к feed:rw."""
    from apps.organizations.models import OrganizationMembership
    from apps.rbac.models import AccessLevel, UserModuleAccessOverride
    membership = OrganizationMembership.objects.get(
        user=tg_link.user, organization=tg_link.organization,
    )
    UserModuleAccessOverride.objects.update_or_create(
        membership=membership, module=Module.objects.get(code="feed"),
        defaults={"level": AccessLevel.READ_WRITE},
    )
    return tg_link


def _msg(chat_id, text):
    return {"chat": {"id": chat_id}, "text": text, "from": {"id": chat_id}}


def _cbq(chat_id, data):
    return {
        "id": "cb-mix-1",
        "data": data,
        "message": {"chat": {"id": chat_id}, "message_id": 77},
        "from": {"id": chat_id},
    }


# ─── Tests ──────────────────────────────────────────────────────────────


def _walk_to_actual_state(chat_id, planned_task, ready_warehouse, storage_bin):
    """Helper: пройти первые шаги wizard'а до state=mix:actual.

    Под капотом feed-модуля у нас > 1 склада (raw + ready), поэтому
    auto-pick не срабатывает — нужно явно нажать кнопку wh, потом bin.
    """
    dispatch_message(_msg(chat_id, "/aralash"))
    dispatch_callback(_cbq(chat_id, f"wiz:mix:task:{planned_task.id}"))
    session = TgWizardSession.objects.get(chat_id=chat_id)
    if session.state == "mix:actual":
        # Auto-pick случился (1 wh + 1 bin) — нечего нажимать.
        return session
    # Ручной выбор: wh → bin
    dispatch_callback(_cbq(chat_id, f"wiz:mix:wh:{ready_warehouse.id}"))
    dispatch_callback(_cbq(chat_id, f"wiz:mix:bin:{storage_bin.id}"))
    session.refresh_from_db()
    return session


def test_full_mix_executes_production_task(
    fake_send, admin_link, planned_task, ready_warehouse, storage_bin,
    corn_batch,
):
    """Полный цикл: выбор задания → склад → бункер → «= План» → execute."""
    chat_id = admin_link.chat_id

    session = _walk_to_actual_state(chat_id, planned_task, ready_warehouse, storage_bin)
    assert session.state == "mix:actual"
    assert session.payload["warehouse_id"] == str(ready_warehouse.id)
    assert session.payload["bin_id"] == str(storage_bin.id)

    # Кнопка «= План»
    dispatch_callback(_cbq(chat_id, "wiz:mix:actual:planned"))
    session.refresh_from_db()
    assert session.state == "mix:confirm"
    assert Decimal(session.payload["actual_qty"]) == Decimal("1000")

    # Confirm
    dispatch_callback(_cbq(chat_id, "wiz:mix:do"))
    assert not TgWizardSession.objects.filter(chat_id=chat_id).exists()

    planned_task.refresh_from_db()
    assert planned_task.status == ProductionTask.Status.DONE
    assert FeedBatch.objects.filter(produced_by_task=planned_task).exists()


def test_mix_actual_qty_text_input(
    fake_send, admin_link, planned_task, ready_warehouse, storage_bin,
    corn_batch,
):
    chat_id = admin_link.chat_id
    session = _walk_to_actual_state(chat_id, planned_task, ready_warehouse, storage_bin)
    assert session.state == "mix:actual"

    # Вводим actual=900 текстом
    dispatch_message(_msg(chat_id, "900"))
    session.refresh_from_db()
    assert session.state == "mix:confirm"
    assert Decimal(session.payload["actual_qty"]) == Decimal("900")

    dispatch_callback(_cbq(chat_id, "wiz:mix:do"))
    fb = FeedBatch.objects.get(produced_by_task=planned_task)
    assert fb.quantity_kg == Decimal("900.000")


def test_mix_no_planned_tasks_aborts(fake_send, admin_link):
    """Если нет PLANNED задач → /aralash сразу прерывается."""
    dispatch_message(_msg(admin_link.chat_id, "/aralash"))
    assert not TgWizardSession.objects.filter(chat_id=admin_link.chat_id).exists()
    assert any("Нет заданий" in t for _, t, _ in fake_send.calls)


def test_mix_cancel_clears_session(
    fake_send, admin_link, planned_task,
):
    chat_id = admin_link.chat_id
    dispatch_message(_msg(chat_id, "/aralash"))
    assert TgWizardSession.objects.filter(chat_id=chat_id).exists()
    dispatch_callback(_cbq(chat_id, "wiz:mix:cancel"))
    assert not TgWizardSession.objects.filter(chat_id=chat_id).exists()


def test_mix_invalid_actual_keeps_state(
    fake_send, admin_link, planned_task, ready_warehouse, storage_bin,
    corn_batch,
):
    chat_id = admin_link.chat_id
    session = _walk_to_actual_state(chat_id, planned_task, ready_warehouse, storage_bin)
    assert session.state == "mix:actual"

    # Невалидное число — сессия должна остаться в actual
    dispatch_message(_msg(chat_id, "не_число"))
    session.refresh_from_db()
    assert session.state == "mix:actual"
