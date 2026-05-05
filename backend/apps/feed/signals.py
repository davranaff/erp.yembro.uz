"""
Авто-создание профилей усушки при появлении новой партии.

Логика: когда в систему попадает первая партия сырья определённой номенклатуры
(или первая партия готового корма по рецепту) и для неё ещё нет ни одного
профиля — создаём дефолтный, чтобы пользователю не нужно было ничего
настраивать вручную. Дальше ночной cron сам начнёт списывать.

Дефолты взяты из spec §B (типовые значения для зерновых / готового корма).
Они консервативные — если у хозяйства реальная усушка больше или меньше,
пользователь увидит расхождение в инвентаризации и подкрутит профиль.

Уважаем явный выбор пользователя:
  - если профиль был создан и потом soft-deleted (is_active=False) —
    повторно автосоздавать НЕ нужно. Юзер сознательно отказался от усушки.
  - повторное создание возможно только если профиль удалили жёстко
    (через админку), что приравнивается к «начать заново».

Отключается флагом settings.FEED_AUTO_CREATE_SHRINKAGE_PROFILE = False.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


# Дефолты для сырья (spec §B — усреднённые для зерновых)
DEFAULT_INGREDIENT_PROFILE = {
    "period_days": 7,
    "percent_per_period": Decimal("0.500"),
    "max_total_percent": Decimal("4.000"),
    "starts_after_days": 3,
    "stop_after_days": None,  # без ограничения
}

# Дефолты для готового корма (более консервативные — гранулы устойчивее зерна)
DEFAULT_FEED_TYPE_PROFILE = {
    "period_days": 7,
    "percent_per_period": Decimal("0.300"),
    "max_total_percent": Decimal("2.000"),
    "starts_after_days": 2,
    "stop_after_days": None,
}

DEFAULT_NOTE = (
    "Создан автоматически при первой приёмке. "
    "Подкорректируйте под условия хранения вашего склада, если нужно."
)


def _autocreate_enabled() -> bool:
    return getattr(settings, "FEED_AUTO_CREATE_SHRINKAGE_PROFILE", True)


@receiver(post_save, sender="feed.RawMaterialBatch")
def auto_create_profile_on_raw_batch(sender, instance, created, **kwargs):
    """При первой партии новой номенклатуры — создаём дефолтный профиль усушки."""
    if not created or not _autocreate_enabled():
        return

    from .models import FeedShrinkageProfile

    if instance.nomenclature_id is None or instance.organization_id is None:
        return

    # Любой профиль (active/inactive) для этой пары → не трогаем
    exists = FeedShrinkageProfile.objects.filter(
        organization_id=instance.organization_id,
        target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
        nomenclature_id=instance.nomenclature_id,
    ).exists()
    if exists:
        return

    try:
        FeedShrinkageProfile.objects.create(
            organization_id=instance.organization_id,
            target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
            nomenclature_id=instance.nomenclature_id,
            warehouse=None,  # на все склады орги
            is_active=True,
            note=DEFAULT_NOTE,
            **DEFAULT_INGREDIENT_PROFILE,
        )
        logger.info(
            "Auto-created shrinkage profile for ingredient %s (org=%s)",
            instance.nomenclature_id, instance.organization_id,
        )
    except Exception:  # noqa: BLE001
        # Сигнал не должен ломать создание партии. Ошибки логируем.
        logger.exception("auto_create_profile_on_raw_batch failed")


@receiver(post_save, sender="feed.FeedBatch")
def auto_create_profile_on_feed_batch(sender, instance, created, **kwargs):
    """При первой партии готового корма по этому рецепту — создаём профиль."""
    if not created or not _autocreate_enabled():
        return

    from .models import FeedShrinkageProfile

    if instance.organization_id is None or instance.recipe_version_id is None:
        return

    recipe_id = instance.recipe_version.recipe_id

    exists = FeedShrinkageProfile.objects.filter(
        organization_id=instance.organization_id,
        target_type=FeedShrinkageProfile.TargetType.FEED_TYPE,
        recipe_id=recipe_id,
    ).exists()
    if exists:
        return

    try:
        FeedShrinkageProfile.objects.create(
            organization_id=instance.organization_id,
            target_type=FeedShrinkageProfile.TargetType.FEED_TYPE,
            recipe_id=recipe_id,
            warehouse=None,
            is_active=True,
            note=DEFAULT_NOTE,
            **DEFAULT_FEED_TYPE_PROFILE,
        )
        logger.info(
            "Auto-created shrinkage profile for recipe %s (org=%s)",
            recipe_id, instance.organization_id,
        )
    except Exception:  # noqa: BLE001
        logger.exception("auto_create_profile_on_feed_batch failed")


@receiver(post_save, sender="feed.Recipe")
def auto_create_nomenclature_for_recipe(sender, instance, created, **kwargs):
    """
    При создании рецептуры автоматически заводим NomenclatureItem с
    sku == recipe.code, чтобы:
      - execute_task мог оприходовать готовый корм как INCOMING StockMovement
      - продажа FeedBagLot могла найти позицию для item.nomenclature

    Без этого пользователь должен создавать «зеркальную» позицию руками
    в /nomenclature, и системные сценарии падают если он забыл.

    Категория — «Корма · сырьё и готовые» (создаём если нет, привязываем к
    модулю feed). Единица — kg (создаём если нет).
    """
    if not created:
        return

    from apps.modules.models import Module
    from apps.nomenclature.models import Category, NomenclatureItem, Unit

    if instance.organization_id is None:
        return

    org_id = instance.organization_id

    if NomenclatureItem.objects.filter(
        organization_id=org_id, sku=instance.code,
    ).exists():
        return

    try:
        feed_module = Module.objects.get(code="feed")
        unit, _ = Unit.objects.get_or_create(
            organization_id=org_id, code="kg",
            defaults={"name": "Килограмм"},
        )
        category, _ = Category.objects.get_or_create(
            organization_id=org_id, name="Корма · сырьё и готовые",
            defaults={"module": feed_module},
        )
        NomenclatureItem.objects.create(
            organization_id=org_id,
            sku=instance.code,
            name=f"Готовый комбикорм · {instance.name}",
            category=category,
            unit=unit,
            is_active=True,
            notes="Автосоздана из рецептуры " + instance.code,
        )
        logger.info(
            "Auto-created NomenclatureItem for recipe %s (org=%s)",
            instance.code, org_id,
        )
    except Exception:  # noqa: BLE001
        # Сигнал не должен ломать создание рецепта.
        logger.exception("auto_create_nomenclature_for_recipe failed")
