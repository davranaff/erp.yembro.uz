"""
API-тесты для:
  - POST /api/vet/treatments/{id}/acknowledge/  (soft-ack менеджером модуля-цели)
  - POST /api/vet/treatments/{id}/cancel/       (расширенный RBAC + 24h окно)
  - GET  /api/vet/treatments/incoming/          (inbox модуля-цели)

Покрывают:
  - target_module.r+ может acknowledge
  - posters без r к target_module → 403
  - inbox показывает только проведённые, не подтверждённые, не отменённые
  - cancel: vet rw → всегда; target_module rw → только в окно 24ч
  - cancel: target_module rw после окна → 403
  - cancel: target_module r (только) → 403
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounting.models import GLSubaccount
from apps.batches.models import Batch
from apps.counterparties.models import Counterparty
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization, OrganizationMembership
from apps.rbac.models import AccessLevel, UserModuleAccessOverride
from apps.users.models import User
from apps.vet.models import VetDrug, VetStockBatch, VetTreatmentLog
from apps.vet.services.apply_treatment import apply_vet_treatment
from apps.warehouses.models import ProductionBlock, Warehouse


pytestmark = pytest.mark.django_db


# ─── fixtures ────────────────────────────────────────────────────────────


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
        organization=org, name="Ветпрепараты ACK",
        defaults={"default_gl_subaccount": sub},
    )[0]


@pytest.fixture
def cat_chick(org):
    return Category.objects.get_or_create(
        organization=org, name="Птица ACK"
    )[0]


@pytest.fixture
def nc_drug(org, cat_vet, unit_dose):
    return NomenclatureItem.objects.create(
        organization=org, sku="ВЕТ-ACK-01", name="Препарат ACK",
        category=cat_vet, unit=unit_dose,
    )


@pytest.fixture
def chick_nom(org, cat_chick, unit_pcs):
    return NomenclatureItem.objects.create(
        organization=org, sku="ЖП-ACK-01", name="Цыпленок ACK",
        category=cat_chick, unit=unit_pcs,
    )


@pytest.fixture
def drug(org, m_vet, nc_drug):
    return VetDrug.objects.create(
        organization=org, module=m_vet, nomenclature=nc_drug,
        drug_type="vaccine", administration_route="spray",
    )


@pytest.fixture
def supplier(org):
    return Counterparty.objects.create(
        organization=org, code="К-ACK-V", kind="supplier", name="Ветпоставка ACK"
    )


@pytest.fixture
def vet_warehouse(org, m_vet):
    return Warehouse.objects.create(
        organization=org, module=m_vet, code="СК-ВЕТ-ACK",
        name="Склад ветаптеки ACK",
    )


@pytest.fixture
def vet_lot(org, m_vet, drug, vet_warehouse, supplier, unit_dose):
    return VetStockBatch.objects.create(
        organization=org, module=m_vet, doc_number="ВП-L-ACK",
        drug=drug, lot_number="L-ACK",
        warehouse=vet_warehouse, supplier=supplier,
        received_date=date.today(),
        expiration_date=date.today() + timedelta(days=365),
        quantity=Decimal("1000"), current_quantity=Decimal("1000"),
        unit=unit_dose, price_per_unit_uzs=Decimal("1000.00"),
        status=VetStockBatch.Status.AVAILABLE,
    )


@pytest.fixture
def feedlot_house(org, m_feedlot):
    return ProductionBlock.objects.create(
        organization=org, module=m_feedlot, code="A-ACK",
        name="Птичник ACK", kind=ProductionBlock.Kind.FEEDLOT,
    )


@pytest.fixture
def poultry_batch(org, m_feedlot, feedlot_house, chick_nom, unit_pcs):
    return Batch.objects.create(
        organization=org, doc_number="П-ACK-001",
        nomenclature=chick_nom, unit=unit_pcs,
        origin_module=m_feedlot, current_module=m_feedlot,
        current_block=feedlot_house,
        current_quantity=Decimal("10000"),
        initial_quantity=Decimal("10000"),
        started_at=date.today(),
    )


@pytest.fixture
def vet_user():
    return User.objects.create(email="vet-ack@y.local", full_name="Vet ACK")


@pytest.fixture
def applied_treatment(
    org, m_vet, drug, vet_lot, poultry_batch, feedlot_house, vet_user, unit_dose,
):
    """Создаёт treatment + проводит его через apply_vet_treatment.
    Гарантия: JE существует, попадает в incoming."""
    t = VetTreatmentLog.objects.create(
        organization=org, module=m_vet, doc_number="ВП-ЖЛ-ACK",
        treatment_date=date.today(),
        target_block=feedlot_house, target_batch=poultry_batch,
        drug=drug, stock_batch=vet_lot,
        dose_quantity=Decimal("100"), unit=unit_dose,
        heads_treated=10000, withdrawal_period_days=7,
        veterinarian=vet_user, indication="therapy",
    )
    apply_vet_treatment(t, user=vet_user)
    return VetTreatmentLog.objects.get(pk=t.pk)


def _make_user(email, *, org, modules):
    u = User.objects.create(email=email, full_name=email)
    membership = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True,
    )
    for module, level in modules.items():
        UserModuleAccessOverride.objects.create(
            membership=membership, module=module, level=level,
        )
    return u


def _client(user):
    api = APIClient()
    api.force_authenticate(user=user)
    api.credentials(HTTP_X_ORGANIZATION_CODE="DEFAULT")
    return api


# ─── incoming / acknowledge ─────────────────────────────────────────────


def test_incoming_lists_applied_unacknowledged(
    org, m_feedlot, applied_treatment,
):
    u = _make_user("ack-r@y.local", org=org, modules={m_feedlot: AccessLevel.READ})
    api = _client(u)
    resp = api.get("/api/vet/treatments/incoming/?to_module=feedlot")
    assert resp.status_code == 200, resp.content
    docs = [t["doc_number"] for t in resp.json()]
    assert "ВП-ЖЛ-ACK" in docs


def test_incoming_403_without_target_module_access(
    org, m_vet, applied_treatment,
):
    """vet rw, но БЕЗ feedlot — нельзя видеть feedlot inbox."""
    u = _make_user("ack-novet@y.local", org=org, modules={m_vet: AccessLevel.READ_WRITE})
    api = _client(u)
    resp = api.get("/api/vet/treatments/incoming/?to_module=feedlot")
    assert resp.status_code == 403


def test_incoming_hides_acknowledged(
    org, m_feedlot, applied_treatment,
):
    u = _make_user("ack-rw@y.local", org=org, modules={m_feedlot: AccessLevel.READ_WRITE})
    api = _client(u)
    # Сначала ack
    resp = api.post(f"/api/vet/treatments/{applied_treatment.id}/acknowledge/")
    assert resp.status_code == 200, resp.content
    assert resp.json()["acknowledged_at"] is not None

    # Теперь в inbox его нет
    resp = api.get("/api/vet/treatments/incoming/?to_module=feedlot")
    assert resp.status_code == 200
    docs = [t["doc_number"] for t in resp.json()]
    assert "ВП-ЖЛ-ACK" not in docs


def test_acknowledge_403_without_target_module_access(
    org, m_vet, applied_treatment,
):
    u = _make_user("ack-vet@y.local", org=org, modules={m_vet: AccessLevel.READ_WRITE})
    api = _client(u)
    resp = api.post(f"/api/vet/treatments/{applied_treatment.id}/acknowledge/")
    assert resp.status_code == 403


# ─── cancel: расширенный RBAC ────────────────────────────────────────────


def test_cancel_allowed_for_vet_rw_anytime(
    org, m_vet, applied_treatment,
):
    u = _make_user("cancel-vet@y.local", org=org, modules={m_vet: AccessLevel.READ_WRITE})
    api = _client(u)
    resp = api.post(
        f"/api/vet/treatments/{applied_treatment.id}/cancel/",
        {"reason": "опечатка в дозе"},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    assert resp.json()["cancelled_at"] is not None


def test_cancel_allowed_for_target_module_rw_within_window(
    org, m_feedlot, applied_treatment,
):
    """Менеджер feedlot (без vet) может реджектнуть в окно 24ч."""
    u = _make_user(
        "cancel-fl@y.local", org=org, modules={m_feedlot: AccessLevel.READ_WRITE},
    )
    api = _client(u)
    resp = api.post(
        f"/api/vet/treatments/{applied_treatment.id}/cancel/",
        {"reason": "не та партия"},
        format="json",
    )
    assert resp.status_code == 200, resp.content


def test_cancel_403_for_target_module_rw_after_window(
    org, m_feedlot, applied_treatment,
):
    """Менеджер feedlot после 24ч — нельзя."""
    # Сместим created_at назад во времени
    VetTreatmentLog.objects.filter(pk=applied_treatment.pk).update(
        created_at=timezone.now() - timedelta(hours=25),
    )
    u = _make_user(
        "cancel-fl-late@y.local", org=org,
        modules={m_feedlot: AccessLevel.READ_WRITE},
    )
    api = _client(u)
    resp = api.post(
        f"/api/vet/treatments/{applied_treatment.id}/cancel/",
        {"reason": "поздняя реакция"},
        format="json",
    )
    assert resp.status_code == 403


def test_cancel_403_for_target_module_read_only(
    org, m_feedlot, applied_treatment,
):
    """r-уровня недостаточно — нужен rw."""
    u = _make_user(
        "cancel-fl-r@y.local", org=org, modules={m_feedlot: AccessLevel.READ},
    )
    api = _client(u)
    resp = api.post(
        f"/api/vet/treatments/{applied_treatment.id}/cancel/",
        {"reason": "тест r-доступа"},
        format="json",
    )
    assert resp.status_code == 403


def test_cancel_vet_rw_after_window_still_works(
    org, m_vet, applied_treatment,
):
    """Окно действует только для target_module-rw, vet-rw — без ограничения."""
    VetTreatmentLog.objects.filter(pk=applied_treatment.pk).update(
        created_at=timezone.now() - timedelta(days=5),
    )
    u = _make_user(
        "vet-late@y.local", org=org, modules={m_vet: AccessLevel.READ_WRITE},
    )
    api = _client(u)
    resp = api.post(
        f"/api/vet/treatments/{applied_treatment.id}/cancel/",
        {"reason": "позднее обнаружение брака"},
        format="json",
    )
    assert resp.status_code == 200, resp.content
