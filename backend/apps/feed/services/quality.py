"""
Сервисы контроля качества:

    - release_raw_material_quarantine(batch, lab_result) —
      LabResult PASSED → RawMaterialBatch.status: QUARANTINE → AVAILABLE.
      При FAILED → status: REJECTED (+ rejection_reason).

    - release_feed_passport(feed_batch, lab_result) —
      LabResult PASSED для FeedBatch → passport_status=PASSED,
      status QUALITY_CHECK → APPROVED.
      При FAILED → passport_status=FAILED, status=REJECTED.

Оба сервиса atomic; идемпотентность через статус (повторный call на
уже финализированном batch → ValidationError).
"""
from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction

from ..models import FeedBatch, LabResult, RawMaterialBatch


class FeedQualityServiceError(ValidationError):
    pass


@transaction.atomic
def release_raw_material_quarantine(
    batch: RawMaterialBatch, *, lab_result: LabResult, user=None
) -> RawMaterialBatch:
    """
    Применить результат лаб-анализа к партии сырья.
    PASSED → AVAILABLE; FAILED → REJECTED.
    """
    batch = RawMaterialBatch.objects.select_for_update().get(pk=batch.pk)

    if batch.status != RawMaterialBatch.Status.QUARANTINE:
        raise FeedQualityServiceError(
            {
                "status": (
                    f"Партия {batch.doc_number} уже в статусе "
                    f"{batch.get_status_display()}, а не на карантине."
                )
            }
        )

    # Проверим что lab_result ссылается на этот batch
    ct = ContentType.objects.get_for_model(RawMaterialBatch)
    if (
        lab_result.subject_content_type_id != ct.id
        or lab_result.subject_object_id != batch.id
    ):
        raise FeedQualityServiceError(
            {"lab_result": "Результат анализа относится к другой партии."}
        )

    if lab_result.status == LabResult.Status.PENDING:
        raise FeedQualityServiceError(
            {"lab_result": "Анализ ещё в работе (PENDING)."}
        )

    if lab_result.status == LabResult.Status.PASSED:
        batch.status = RawMaterialBatch.Status.AVAILABLE
    elif lab_result.status == LabResult.Status.FAILED:
        batch.status = RawMaterialBatch.Status.REJECTED
        if not batch.rejection_reason:
            batch.rejection_reason = lab_result.notes or "Отклонено лабораторией."
    batch.save(update_fields=["status", "rejection_reason", "updated_at"])
    return batch


@transaction.atomic
def release_feed_passport(
    feed_batch: FeedBatch, *, lab_result: LabResult, user=None
) -> FeedBatch:
    """
    Применить лаб-результат к партии готового корма.
    PASSED → passport_status=PASSED + status=APPROVED;
    FAILED → passport_status=FAILED + status=REJECTED.
    """
    feed_batch = FeedBatch.objects.select_for_update().get(pk=feed_batch.pk)

    if feed_batch.status not in (
        FeedBatch.Status.QUALITY_CHECK,
        FeedBatch.Status.APPROVED,  # допустим повторное подтверждение
    ):
        raise FeedQualityServiceError(
            {
                "status": (
                    f"Партия корма {feed_batch.doc_number} в статусе "
                    f"{feed_batch.get_status_display()} — нельзя выдать паспорт."
                )
            }
        )

    ct = ContentType.objects.get_for_model(FeedBatch)
    if (
        lab_result.subject_content_type_id != ct.id
        or lab_result.subject_object_id != feed_batch.id
    ):
        raise FeedQualityServiceError(
            {"lab_result": "Результат анализа относится к другой партии."}
        )

    if lab_result.status == LabResult.Status.PENDING:
        raise FeedQualityServiceError(
            {"lab_result": "Анализ ещё в работе."}
        )

    if lab_result.status == LabResult.Status.PASSED:
        feed_batch.quality_passport_status = FeedBatch.PassportStatus.PASSED
        feed_batch.status = FeedBatch.Status.APPROVED
    else:  # FAILED
        feed_batch.quality_passport_status = FeedBatch.PassportStatus.FAILED
        feed_batch.status = FeedBatch.Status.REJECTED

    feed_batch.save(
        update_fields=["quality_passport_status", "status", "updated_at"]
    )
    return feed_batch
