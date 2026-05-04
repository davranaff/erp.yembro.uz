"""
Signals для apps/matochnik.

Единственный сигнал сейчас: post_save BreedingMortality → декремент
current_heads стада. Это убирает необходимость "дважды вводить одно и то же"
(журнал падежа + отдельное снятие). Запись падежа — самодостаточная операция.

Edge case: если запись падежа создаётся через `depopulate_herd(mark_as_mortality=True)`,
сервис должен полагаться на этот сигнал (не уменьшать current_heads сам при
create). Для update (merge за день) сервис уменьшает current_heads вручную,
потому что сигнал не срабатывает на update.
"""
from django.db import transaction
from django.db.models import F
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import BreedingHerd, BreedingMortality


@receiver(post_save, sender=BreedingMortality)
def decrement_herd_on_mortality_create(sender, instance, created, **kwargs):
    """
    При создании (не update) записи падежа — уменьшить current_heads
    стада на dead_count. Если опустилось до 0 → status=DEPOPULATED.
    """
    if not created:
        # Update dead_count в существующей записи — здесь мы не знаем
        # delta, поэтому его должен обработать вызывающий сервис.
        return
    if not instance.dead_count:
        return

    with transaction.atomic():
        # current_heads — PositiveIntegerField, поэтому нельзя уйти в минус.
        # Загружаем текущее значение, прижимаем к нулю если dead > heads.
        herd = BreedingHerd.objects.select_for_update().get(pk=instance.herd_id)
        effective = max(0, herd.current_heads - instance.dead_count)
        herd.current_heads = effective
        if effective == 0 and herd.status != BreedingHerd.Status.DEPOPULATED:
            herd.status = BreedingHerd.Status.DEPOPULATED
            herd.save(update_fields=["current_heads", "status", "updated_at"])
        else:
            herd.save(update_fields=["current_heads", "updated_at"])
