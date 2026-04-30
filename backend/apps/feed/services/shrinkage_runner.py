"""
Периодическое списание усушки сырья и готового корма (spec §5).

Алгоритм (компаундный):
  1. Для каждой активной партии находим профиль (warehouse-specific приоритетен).
  2. Считаем сколько полных периодов прошло с last_applied_on (или с
     received_date/produced_at, если state ещё не создан + grace).
  3. За каждый период списываем percent_per_period от ТЕКУЩЕГО остатка
     (compound). Потери накапливаются в state.accumulated_loss; если упёрлись
     в max_total_percent — последняя дельта урезается и state замораживается.
  4. Одно срабатывание = один StockMovement(kind=SHRINKAGE) на партию (сумма
     дельт за все периоды), reference на FeedLotShrinkageState.
  5. RawMaterialBatch.current_quantity / FeedBatch.current_quantity_kg
     уменьшаются на ту же величину — отчёты по остаткам видят усушку
     автоматически.

Идемпотентность: повторный запуск на ту же дату даёт `полных_периодов = 0`
для уже обработанных партий и пропускает их.

Все функции изолированы в transaction.atomic per-lot — одна битая партия не
валит весь цикл.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Optional

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import F

logger = logging.getLogger(__name__)

_KG_QUANT = Decimal("0.001")
_AMT_QUANT = Decimal("0.01")
_HUNDRED = Decimal("100")
_ZERO = Decimal("0")


def _q_kg(v: Decimal) -> Decimal:
    return v.quantize(_KG_QUANT, rounding=ROUND_HALF_UP)


def _q_amt(v: Decimal) -> Decimal:
    return v.quantize(_AMT_QUANT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class LotInfo:
    """Унифицированная обёртка для партии любого типа."""

    lot_type: str  # FeedLotShrinkageState.LotType value
    lot_id: str
    organization_id: str
    nomenclature_id: Optional[str]
    recipe_id: Optional[str]
    warehouse_id: Optional[str]
    arrived_on: date
    initial_quantity: Decimal
    current_quantity: Decimal
    unit_price: Decimal
    module_id: str


@dataclass
class ApplyResult:
    """Что произошло на одной партии."""

    lot_type: str
    lot_id: str
    skipped: bool
    skipped_reason: str = ""
    loss_kg: Decimal = _ZERO
    periods_applied: int = 0
    frozen: bool = False
    state_id: Optional[str] = None
    movement_id: Optional[str] = None


# ─── lot collectors ────────────────────────────────────────────────────────


def _collect_raw_lots(organization_id: str) -> Iterable[LotInfo]:
    from .. import models as feed_models
    from ..models import RawMaterialBatch

    qs = (
        RawMaterialBatch.objects.filter(
            organization_id=organization_id,
            status=RawMaterialBatch.Status.AVAILABLE,
            current_quantity__gt=0,
        )
        .select_related("nomenclature", "warehouse", "module")
    )
    state_lot_type = feed_models.FeedLotShrinkageState.LotType.RAW_ARRIVAL
    for b in qs:
        yield LotInfo(
            lot_type=state_lot_type,
            lot_id=str(b.id),
            organization_id=str(b.organization_id),
            nomenclature_id=str(b.nomenclature_id),
            recipe_id=None,
            warehouse_id=str(b.warehouse_id) if b.warehouse_id else None,
            arrived_on=b.received_date,
            initial_quantity=Decimal(b.quantity),
            current_quantity=Decimal(b.current_quantity),
            unit_price=Decimal(b.price_per_unit_uzs),
            module_id=str(b.module_id),
        )


def _collect_feed_lots(organization_id: str) -> Iterable[LotInfo]:
    from .. import models as feed_models
    from ..models import FeedBatch

    qs = (
        FeedBatch.objects.filter(
            organization_id=organization_id,
            status=FeedBatch.Status.APPROVED,
            current_quantity_kg__gt=0,
        )
        .select_related("recipe_version__recipe", "storage_warehouse", "module")
    )
    state_lot_type = feed_models.FeedLotShrinkageState.LotType.PRODUCTION_BATCH
    for b in qs:
        wh_id = b.storage_warehouse_id
        # Партия готового корма может храниться в bunker, без storage_warehouse —
        # тогда профиль для конкретного склада не подойдёт, останется только общий.
        yield LotInfo(
            lot_type=state_lot_type,
            lot_id=str(b.id),
            organization_id=str(b.organization_id),
            nomenclature_id=None,
            recipe_id=str(b.recipe_version.recipe_id),
            warehouse_id=str(wh_id) if wh_id else None,
            arrived_on=b.produced_at.date(),
            initial_quantity=Decimal(b.quantity_kg),
            current_quantity=Decimal(b.current_quantity_kg),
            unit_price=Decimal(b.unit_cost_uzs),
            module_id=str(b.module_id),
        )


# ─── profile resolver ──────────────────────────────────────────────────────


def _find_profile(lot: LotInfo) -> Optional["FeedShrinkageProfile"]:  # noqa: F821
    """Находит активный профиль для партии. Конкретный склад приоритетнее общего."""
    from ..models import FeedShrinkageProfile

    if lot.lot_type == "raw_arrival":
        target_type = FeedShrinkageProfile.TargetType.INGREDIENT
        scope = FeedShrinkageProfile.objects.filter(
            organization_id=lot.organization_id,
            target_type=target_type,
            nomenclature_id=lot.nomenclature_id,
            is_active=True,
        )
    else:
        target_type = FeedShrinkageProfile.TargetType.FEED_TYPE
        scope = FeedShrinkageProfile.objects.filter(
            organization_id=lot.organization_id,
            target_type=target_type,
            recipe_id=lot.recipe_id,
            is_active=True,
        )

    if lot.warehouse_id:
        specific = scope.filter(warehouse_id=lot.warehouse_id).first()
        if specific:
            return specific
    return scope.filter(warehouse_id__isnull=True).first()


# ─── compound math ─────────────────────────────────────────────────────────


def _compute_loss(
    *,
    current_quantity: Decimal,
    initial_quantity: Decimal,
    accumulated_loss: Decimal,
    pct_per_period: Decimal,
    max_total_pct: Optional[Decimal],
    periods: int,
) -> tuple[Decimal, bool]:
    """
    Компаундный расчёт суммарной потери за `periods` периодов.

    Возвращает (total_loss_kg, hit_max_limit). hit_max_limit=True если
    после применения упёрлись в max_total_percent → state нужно заморозить.
    """
    if periods <= 0 or pct_per_period <= 0 or current_quantity <= 0:
        return _ZERO, False

    factor = pct_per_period / _HUNDRED
    remaining = Decimal(current_quantity)
    loss = _ZERO
    hit_max = False

    if max_total_pct is not None:
        max_loss_total = initial_quantity * max_total_pct / _HUNDRED
        max_loss_remaining = max_loss_total - accumulated_loss
    else:
        max_loss_remaining = None

    for _ in range(periods):
        if remaining <= 0:
            break
        delta = remaining * factor
        if max_loss_remaining is not None:
            if delta >= max_loss_remaining:
                # последний шаг — урезаем до лимита
                delta = max(_ZERO, max_loss_remaining)
                loss += delta
                remaining -= delta
                max_loss_remaining = _ZERO
                hit_max = True
                break
            max_loss_remaining -= delta
        loss += delta
        remaining -= delta

    return _q_kg(loss), hit_max


# ─── main per-lot apply ────────────────────────────────────────────────────


@transaction.atomic
def apply_to_lot(lot: LotInfo, today: date) -> ApplyResult:
    """Применить алгоритм усушки к одной партии. Идемпотентно по дате."""
    from ..models import FeedLotShrinkageState

    profile = _find_profile(lot)
    if profile is None:
        return ApplyResult(
            lot_type=lot.lot_type,
            lot_id=lot.lot_id,
            skipped=True,
            skipped_reason="no_profile",
        )

    state = (
        FeedLotShrinkageState.objects.select_for_update()
        .filter(lot_type=lot.lot_type, lot_id=lot.lot_id)
        .first()
    )

    days_since_start = (today - lot.arrived_on).days
    if days_since_start < int(profile.starts_after_days):
        return ApplyResult(
            lot_type=lot.lot_type, lot_id=lot.lot_id,
            skipped=True, skipped_reason="grace_period",
            state_id=str(state.id) if state else None,
        )

    if state and state.is_frozen:
        return ApplyResult(
            lot_type=lot.lot_type, lot_id=lot.lot_id,
            skipped=True, skipped_reason="frozen",
            state_id=str(state.id),
        )

    # state может не существовать — создадим при первом списании
    accumulated_loss = Decimal(state.accumulated_loss) if state else _ZERO
    initial_quantity = Decimal(state.initial_quantity) if state else lot.initial_quantity
    last_applied_on = state.last_applied_on if state else None

    # «От чего считать дни»
    if last_applied_on is None:
        # Первое срабатывание: дни считаем от arrived_on, но с учётом grace.
        anchor = lot.arrived_on
    else:
        anchor = last_applied_on

    days_since_last = (today - anchor).days
    if days_since_last <= 0:
        return ApplyResult(
            lot_type=lot.lot_type, lot_id=lot.lot_id,
            skipped=True, skipped_reason="already_applied_today",
            state_id=str(state.id) if state else None,
        )

    # Если профиль ограничивает срок — заморозим после
    will_freeze_by_age = (
        profile.stop_after_days is not None
        and days_since_start > int(profile.stop_after_days)
    )

    full_periods = days_since_last // int(profile.period_days)
    if full_periods <= 0:
        return ApplyResult(
            lot_type=lot.lot_type, lot_id=lot.lot_id,
            skipped=True, skipped_reason="not_enough_days",
            state_id=str(state.id) if state else None,
        )

    if lot.current_quantity <= 0:
        # Партия исчерпана — заморозим state, ничего не списываем
        state = _ensure_state(state, lot, profile, initial_quantity)
        state.is_frozen = True
        state.save(update_fields=["is_frozen", "updated_at"])
        return ApplyResult(
            lot_type=lot.lot_type, lot_id=lot.lot_id,
            skipped=True, skipped_reason="lot_depleted",
            frozen=True, state_id=str(state.id),
        )

    loss, hit_max = _compute_loss(
        current_quantity=lot.current_quantity,
        initial_quantity=initial_quantity,
        accumulated_loss=accumulated_loss,
        pct_per_period=Decimal(profile.percent_per_period),
        max_total_pct=(
            Decimal(profile.max_total_percent)
            if profile.max_total_percent is not None
            else None
        ),
        periods=full_periods,
    )

    if loss <= 0:
        # все дельты уже за пределом max — просто замораживаем state и выходим
        state = _ensure_state(state, lot, profile, initial_quantity)
        state.last_applied_on = today
        state.is_frozen = will_freeze_by_age or hit_max
        state.save(update_fields=["last_applied_on", "is_frozen", "updated_at"])
        return ApplyResult(
            lot_type=lot.lot_type, lot_id=lot.lot_id,
            skipped=True, skipped_reason="zero_loss",
            frozen=state.is_frozen, state_id=str(state.id),
        )

    state = _ensure_state(state, lot, profile, initial_quantity)
    new_accumulated = _q_kg(accumulated_loss + loss)
    state.accumulated_loss = new_accumulated
    state.last_applied_on = today
    state.is_frozen = will_freeze_by_age or hit_max
    state.save(update_fields=["accumulated_loss", "last_applied_on", "is_frozen", "updated_at"])

    movement = _create_shrinkage_movement(lot, state, loss, today, full_periods, profile)
    _decrement_lot_current_quantity(lot, loss)

    return ApplyResult(
        lot_type=lot.lot_type,
        lot_id=lot.lot_id,
        skipped=False,
        loss_kg=loss,
        periods_applied=full_periods,
        frozen=state.is_frozen,
        state_id=str(state.id),
        movement_id=str(movement.id) if movement else None,
    )


def _ensure_state(state, lot: LotInfo, profile, initial_quantity: Decimal):
    from ..models import FeedLotShrinkageState

    if state is not None:
        return state
    return FeedLotShrinkageState.objects.create(
        organization_id=lot.organization_id,
        lot_type=lot.lot_type,
        lot_id=lot.lot_id,
        profile=profile,
        initial_quantity=initial_quantity,
        accumulated_loss=_ZERO,
        last_applied_on=None,
        is_frozen=False,
    )


def _create_shrinkage_movement(lot: LotInfo, state, loss: Decimal, today: date, periods: int, profile):
    """Создаёт StockMovement(kind=SHRINKAGE) с reference на state."""
    from datetime import datetime, time

    from apps.common.services.numbering import next_doc_number
    from apps.warehouses.models import StockMovement

    from ..models import FeedLotShrinkageState

    if lot.warehouse_id is None:
        # Партия без склада (например feed batch в storage_bin без warehouse) —
        # создать движение нельзя (warehouse_from обязателен). Усушку посчитали,
        # но движение пропускаем; remaining обновится напрямую через
        # _decrement_lot_current_quantity. Логируем для аудита.
        logger.warning(
            "shrinkage: no warehouse for lot %s/%s — movement skipped, only state updated",
            lot.lot_type, lot.lot_id,
        )
        return None

    nomenclature_id = lot.nomenclature_id
    if nomenclature_id is None:
        # FeedBatch не имеет прямой nomenclature — берём из recipe components не
        # имеет смысла (готовый корм — отдельный артикул). На текущем этапе
        # пропускаем создание движения для готового корма без nomenclature.
        # TODO: после внедрения nomenclature на FeedBatch — снять.
        logger.warning(
            "shrinkage: no nomenclature for lot %s/%s — movement skipped, only state updated",
            lot.lot_type, lot.lot_id,
        )
        return None

    org_id = lot.organization_id
    organization = _resolve_organization(org_id)

    doc_number = next_doc_number(
        StockMovement,
        organization=organization,
        prefix="УСШ",
        on_date=today,
    )

    state_ct = ContentType.objects.get_for_model(FeedLotShrinkageState)
    amount = _q_amt(loss * lot.unit_price)
    move = StockMovement.objects.create(
        organization_id=org_id,
        module_id=lot.module_id,
        doc_number=doc_number,
        kind=StockMovement.Kind.SHRINKAGE,
        date=datetime.combine(today, time(2, 0)),  # 02:00 — время cron-цикла
        nomenclature_id=nomenclature_id,
        quantity=loss,
        unit_price_uzs=_q_amt(lot.unit_price),
        amount_uzs=amount,
        warehouse_from_id=lot.warehouse_id,
        warehouse_to=None,
        source_content_type=state_ct,
        source_object_id=state.id,
    )
    return move


def _decrement_lot_current_quantity(lot: LotInfo, loss: Decimal) -> None:
    from ..models import FeedBatch, RawMaterialBatch

    if lot.lot_type == "raw_arrival":
        RawMaterialBatch.objects.filter(pk=lot.lot_id).update(
            current_quantity=F("current_quantity") - loss,
            updated_at=_now(),
        )
    else:
        FeedBatch.objects.filter(pk=lot.lot_id).update(
            current_quantity_kg=F("current_quantity_kg") - loss,
            updated_at=_now(),
        )


def _resolve_organization(org_id):
    from apps.organizations.models import Organization

    return Organization.objects.get(pk=org_id)


def _now():
    from django.utils.timezone import now
    return now()


# ─── high-level entry points ───────────────────────────────────────────────


def apply_for_organization(organization, today: Optional[date] = None) -> list[ApplyResult]:
    """Прогоняет алгоритм по всем активным партиям организации."""
    today = today or date.today()
    results: list[ApplyResult] = []
    for lot in _iter_org_lots(str(organization.id)):
        try:
            res = apply_to_lot(lot, today)
        except Exception:  # noqa: BLE001
            logger.exception(
                "shrinkage failed for lot %s/%s", lot.lot_type, lot.lot_id
            )
            continue
        results.append(res)
    return results


def apply_for_specific_lot(*, lot_type: str, lot_id: str, today: Optional[date] = None) -> ApplyResult:
    """Ручной триггер на конкретную партию (POST /shrinkage/apply)."""
    today = today or date.today()
    lot = _build_lot_info(lot_type, lot_id)
    return apply_to_lot(lot, today)


def _iter_org_lots(organization_id: str):
    yield from _collect_raw_lots(organization_id)
    yield from _collect_feed_lots(organization_id)


def _build_lot_info(lot_type: str, lot_id: str) -> LotInfo:
    from ..models import FeedBatch, FeedLotShrinkageState, RawMaterialBatch

    if lot_type == FeedLotShrinkageState.LotType.RAW_ARRIVAL:
        b = RawMaterialBatch.objects.select_related(
            "nomenclature", "warehouse", "module"
        ).get(pk=lot_id)
        return LotInfo(
            lot_type=lot_type,
            lot_id=str(b.id),
            organization_id=str(b.organization_id),
            nomenclature_id=str(b.nomenclature_id),
            recipe_id=None,
            warehouse_id=str(b.warehouse_id) if b.warehouse_id else None,
            arrived_on=b.received_date,
            initial_quantity=Decimal(b.quantity),
            current_quantity=Decimal(b.current_quantity),
            unit_price=Decimal(b.price_per_unit_uzs),
            module_id=str(b.module_id),
        )
    elif lot_type == FeedLotShrinkageState.LotType.PRODUCTION_BATCH:
        b = FeedBatch.objects.select_related(
            "recipe_version__recipe", "storage_warehouse", "module"
        ).get(pk=lot_id)
        return LotInfo(
            lot_type=lot_type,
            lot_id=str(b.id),
            organization_id=str(b.organization_id),
            nomenclature_id=None,
            recipe_id=str(b.recipe_version.recipe_id),
            warehouse_id=str(b.storage_warehouse_id) if b.storage_warehouse_id else None,
            arrived_on=b.produced_at.date(),
            initial_quantity=Decimal(b.quantity_kg),
            current_quantity=Decimal(b.current_quantity_kg),
            unit_price=Decimal(b.unit_cost_uzs),
            module_id=str(b.module_id),
        )
    else:
        raise ValueError(f"Unknown lot_type: {lot_type}")


# ─── reset (admin op) ──────────────────────────────────────────────────────


@transaction.atomic
def reset_lot_shrinkage(state) -> dict:
    """Откатывает все StockMovement(kind=shrinkage) для этой партии и
    сбрасывает state.

    После этого следующий цикл алгоритма пересчитает усушку с нуля от
    arrived_on. Используется когда админ изменил профиль и хочет
    переиграть историю.

    Возвращает {"reverted_movements": N, "restored_kg": Decimal}.
    """
    from apps.warehouses.models import StockMovement

    from ..models import FeedBatch, FeedLotShrinkageState, RawMaterialBatch

    state_ct = ContentType.objects.get_for_model(FeedLotShrinkageState)
    movements = list(
        StockMovement.objects.filter(
            kind=StockMovement.Kind.SHRINKAGE,
            source_content_type=state_ct,
            source_object_id=state.id,
        )
    )
    restored = sum((Decimal(m.quantity) for m in movements), _ZERO)

    # Возвращаем количество в партию
    if state.lot_type == FeedLotShrinkageState.LotType.RAW_ARRIVAL:
        RawMaterialBatch.objects.filter(pk=state.lot_id).update(
            current_quantity=F("current_quantity") + restored,
            updated_at=_now(),
        )
    else:
        FeedBatch.objects.filter(pk=state.lot_id).update(
            current_quantity_kg=F("current_quantity_kg") + restored,
            updated_at=_now(),
        )

    # Удаляем движения (force — это служебная админская операция)
    n_deleted = len(movements)
    for m in movements:
        m.delete()

    state.accumulated_loss = _ZERO
    state.last_applied_on = None
    state.is_frozen = False
    state.save(update_fields=[
        "accumulated_loss", "last_applied_on", "is_frozen", "updated_at",
    ])

    logger.info(
        "shrinkage reset: state=%s reverted=%s restored_kg=%s",
        state.id, n_deleted, restored,
    )
    return {"reverted_movements": n_deleted, "restored_kg": restored}
