"""
Авто-перевод статусов вет-лотов по сроку годности.

Запускается Celery beat ежедневно в 03:00 Asia/Tashkent. Можно вызвать
вручную через management command или прямо из shell для тестов.

Логика (в одной транзакции):
  1. AVAILABLE/EXPIRING_SOON с expiration_date < today → EXPIRED
  2. AVAILABLE с expiration_date <= today + EXPIRING_THRESHOLD_DAYS → EXPIRING_SOON

QUARANTINE / RECALLED / DEPLETED не трогаем.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from django.db import transaction

from ..models import VetStockBatch


@dataclass
class AutoStatusResult:
    expired: int
    expiring: int

    def as_dict(self) -> dict:
        return {"expired": self.expired, "expiring": self.expiring}


@transaction.atomic
def auto_update_vet_stock_status() -> AutoStatusResult:
    today = date.today()
    threshold = today + timedelta(days=VetStockBatch.EXPIRING_THRESHOLD_DAYS)
    Status = VetStockBatch.Status

    # 1. Истёкшие → EXPIRED
    expired = (
        VetStockBatch.objects
        .filter(
            status__in=[Status.AVAILABLE, Status.EXPIRING_SOON],
            expiration_date__lt=today,
        )
        .update(status=Status.EXPIRED)
    )

    # 2. Скоро истекают → EXPIRING_SOON
    expiring = (
        VetStockBatch.objects
        .filter(
            status=Status.AVAILABLE,
            expiration_date__gte=today,
            expiration_date__lte=threshold,
        )
        .update(status=Status.EXPIRING_SOON)
    )

    return AutoStatusResult(expired=expired, expiring=expiring)
