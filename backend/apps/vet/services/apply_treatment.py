"""
Сервис `apply_vet_treatment` — применение препарата/вакцины.

Atomic-транзакция:
    1. Guards:
       - TreatmentLog.full_clean() — XOR target_batch/target_herd, stock_batch.drug == drug,
         dose_quantity <= stock_batch.current_quantity.
       - stock_batch.status = AVAILABLE.
       - withdrawal_period_days >= 0.
    2. Декремент `stock_batch.current_quantity` через F() (safe при race).
       Если становится 0 → status=DEPLETED.
    3. StockMovement OUTGOING со склада ветаптеки (в модуле vet).
       Списание по себестоимости лота: amount = dose_quantity * price_per_unit_uzs.
    4. JournalEntry: Dr 20.XX (Затраты модуля-цели, обычно 20.02 Фабрика / 20.01 Маточник)
       / Cr 10.03 (Ветпрепараты на складе).
       module=target_module (куда применили). counterparty=NULL.
    5. BatchCostEntry(category=VET, amount=cost) — если target_batch задан.
    6. **Обновление `Batch.withdrawal_period_ends`** (если target_batch и withdrawal_period_days > 0):
       new_end = treatment_date + withdrawal_period_days
       batch.withdrawal_period_ends = max(current, new_end)
       — это автоматически заблокирует убой через Slaughter.clean() (Phase 5 guard).

Повторный вызов на уже созданной записи — запрещён (сервис работает
с DRAFT-записью, превращает в POSTED). В модели VetTreatmentLog нет
поля status, поэтому идемпотентность реализуется через FK journal_entry:
если он уже привязан — повторный apply раз кинет ValidationError.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.accounting.models import GLSubaccount, JournalEntry
from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log
from apps.batches.models import Batch, BatchCostEntry
from apps.common.services.numbering import next_doc_number
from apps.warehouses.models import StockMovement

from ..models import VetStockBatch, VetTreatmentLog


# GL policy: Dr 20.XX (cost of target module) / Cr 10.03 (vet storage)
VET_MATERIALS_SUBACCOUNT = "10.03"

# Map: Module.kind → код субсчёта 20-серии для затрат
COST_SUBACCOUNT_BY_MODULE_KIND = {
    "matochnik": "20.01",
    "feedlot": "20.02",
    "incubation": "20.03",
    "slaughter": "20.04",
}


class VetTreatmentApplyError(ValidationError):
    pass


@dataclass
class VetTreatmentApplyResult:
    treatment: VetTreatmentLog
    stock_movement: StockMovement
    journal_entry: JournalEntry
    batch_cost_entry: Optional[BatchCostEntry]
    previous_withdrawal_end: Optional[object]  # date | None
    new_withdrawal_end: Optional[object]       # date | None


def _get_subaccount(org, code: str) -> GLSubaccount:
    try:
        return GLSubaccount.objects.select_related("account").get(
            account__organization=org, code=code
        )
    except GLSubaccount.DoesNotExist as exc:
        raise VetTreatmentApplyError(
            {"__all__": f"Субсчёт {code} не найден в организации {org.code}."}
        ) from exc


def _resolve_target_module(treatment: VetTreatmentLog):
    """
    Модуль-цель (куда применяется препарат). Это НЕ treatment.module (=vet),
    а модуль блока где находится партия/стадо.
    """
    if treatment.target_block_id:
        return treatment.target_block.module
    if treatment.target_batch_id and treatment.target_batch.current_module_id:
        return treatment.target_batch.current_module
    if treatment.target_herd_id:
        return treatment.target_herd.module
    return treatment.module  # fallback


def _resolve_cost_subaccount(org, target_module) -> GLSubaccount:
    """
    Субсчёт 20.XX для списания затрат в модуле-цели.
    Для неизвестных модулей — 20.04 (по умолчанию производство).
    """
    code = COST_SUBACCOUNT_BY_MODULE_KIND.get(target_module.kind)
    if not code:
        raise VetTreatmentApplyError(
            {
                "__all__": (
                    f"Нет настройки субсчёта затрат для модуля "
                    f"{target_module.code} (kind={target_module.kind})."
                )
            }
        )
    return _get_subaccount(org, code)


@transaction.atomic
def apply_vet_treatment(
    treatment: VetTreatmentLog, *, user=None
) -> VetTreatmentApplyResult:
    """
    Применить препарат по записи TreatmentLog.

    В MVP сервис работает с уже созданной VetTreatmentLog, превращает
    её в «проведённую» (с journal_entry) + двигает складские остатки
    и каренцию.

    Повторный вызов (если treatment уже имеет JournalEntry с source=этот) —
    ValidationError.
    """
    # 1. Row-lock без select_related
    treatment = VetTreatmentLog.objects.select_for_update().get(pk=treatment.pk)
    treatment = VetTreatmentLog.objects.select_related(
        "organization",
        "module",
        "target_block",
        "target_block__module",
        "target_batch",
        "target_batch__current_module",
        "target_herd",
        "target_herd__module",
        "drug",
        "drug__nomenclature",
        "stock_batch",
        "stock_batch__warehouse",
        "unit",
    ).get(pk=treatment.pk)

    # 2. Идемпотентность: если уже есть JournalEntry с source=этот — второй раз нельзя.
    ct = ContentType.objects.get_for_model(VetTreatmentLog)
    existing_je = JournalEntry.objects.filter(
        source_content_type=ct, source_object_id=treatment.id
    ).first()
    if existing_je:
        raise VetTreatmentApplyError(
            {"__all__": "Лечение уже проведено (JournalEntry существует)."}
        )

    # 3. Full-clean — XOR target, cross-org, stock_batch.drug == drug, etc.
    treatment.full_clean(exclude=None)

    stock_batch = treatment.stock_batch
    if stock_batch.status != VetStockBatch.Status.AVAILABLE:
        raise VetTreatmentApplyError(
            {
                "stock_batch": (
                    f"Лот {stock_batch.doc_number} в статусе "
                    f"{stock_batch.get_status_display()} — не доступен для списания."
                )
            }
        )

    org = treatment.organization

    # 4. Декремент лота через F() — race-safe
    VetStockBatch.objects.filter(pk=stock_batch.pk).update(
        current_quantity=F("current_quantity") - treatment.dose_quantity
    )
    stock_batch.refresh_from_db(fields=["current_quantity"])
    if stock_batch.current_quantity <= 0:
        stock_batch.status = VetStockBatch.Status.DEPLETED
        stock_batch.save(update_fields=["status", "updated_at"])

    # 5. Стоимость списания
    cost = (treatment.dose_quantity * stock_batch.price_per_unit_uzs).quantize(
        Decimal("0.01")
    )

    # 6. StockMovement OUTGOING из vet-склада
    sm_number = next_doc_number(
        StockMovement,
        organization=org,
        prefix="СД",
        on_date=treatment.treatment_date,
    )
    sm_qty = treatment.dose_quantity.quantize(Decimal("0.001"))
    sm = StockMovement(
        organization=org,
        module=treatment.module,  # vet module
        doc_number=sm_number,
        kind=StockMovement.Kind.OUTGOING,
        date=timezone.now(),
        nomenclature=treatment.drug.nomenclature,
        quantity=sm_qty,
        unit_price_uzs=stock_batch.price_per_unit_uzs,
        amount_uzs=cost,
        warehouse_from=stock_batch.warehouse,
        warehouse_to=None,
        batch=treatment.target_batch,  # опц. FK на poultry batch
        source_content_type=ct,
        source_object_id=treatment.id,
        created_by=user,
    )
    sm.full_clean(exclude=None)
    sm.save()

    # 7. JournalEntry: Dr 20.XX (target module) / Cr 10.03 (vet materials)
    target_module = _resolve_target_module(treatment)
    debit_sub = _resolve_cost_subaccount(org, target_module)
    credit_sub = _get_subaccount(org, VET_MATERIALS_SUBACCOUNT)

    je_number = next_doc_number(
        JournalEntry,
        organization=org,
        prefix="ПР",
        on_date=treatment.treatment_date,
    )
    je = JournalEntry(
        organization=org,
        module=target_module,
        doc_number=je_number,
        entry_date=treatment.treatment_date,
        description=(
            f"Вет. применение {treatment.doc_number or ''} · "
            f"{treatment.drug.nomenclature.sku} · "
            f"{treatment.dose_quantity} {treatment.unit.code}"
        ).strip(),
        debit_subaccount=debit_sub,
        credit_subaccount=credit_sub,
        amount_uzs=cost,
        source_content_type=ct,
        source_object_id=treatment.id,
        batch=treatment.target_batch,
        created_by=user,
    )
    je.full_clean(exclude=None)
    je.save()

    # 8. BatchCostEntry (если есть target_batch)
    batch_cost_entry = None
    if treatment.target_batch_id and cost > 0:
        batch_cost_entry = BatchCostEntry.objects.create(
            batch=treatment.target_batch,
            category=BatchCostEntry.Category.VET,
            amount_uzs=cost,
            description=(
                f"Вет. применение {treatment.drug.nomenclature.sku} · "
                f"{treatment.dose_quantity} {treatment.unit.code}"
            ),
            occurred_at=timezone.now(),
            module=target_module,
            source_content_type=ct,
            source_object_id=treatment.id,
            created_by=user,
        )
        # Обновить Batch.accumulated_cost_uzs
        Batch.objects.filter(pk=treatment.target_batch_id).update(
            accumulated_cost_uzs=F("accumulated_cost_uzs") + cost
        )

    # 9. Обновление withdrawal_period_ends на batch
    previous_end = None
    new_end = None
    if treatment.target_batch_id and treatment.withdrawal_period_days > 0:
        batch = Batch.objects.select_for_update().get(pk=treatment.target_batch_id)
        previous_end = batch.withdrawal_period_ends
        candidate = treatment.treatment_date + timedelta(
            days=treatment.withdrawal_period_days
        )
        new_end = (
            candidate
            if previous_end is None or candidate > previous_end
            else previous_end
        )
        if new_end != previous_end:
            batch.withdrawal_period_ends = new_end
            batch.save(update_fields=["withdrawal_period_ends", "updated_at"])

    audit_log(
        organization=treatment.organization,
        module=treatment.module,
        actor=user,
        action=AuditLog.Action.POST,
        entity=treatment,
        action_verb=(
            f"applied vet treatment {treatment.doc_number or ''} · "
            f"{treatment.drug.nomenclature.sku}"
        ).strip(),
    )

    return VetTreatmentApplyResult(
        treatment=treatment,
        stock_movement=sm,
        journal_entry=je,
        batch_cost_entry=batch_cost_entry,
        previous_withdrawal_end=previous_end,
        new_withdrawal_end=new_end,
    )
