from django.core.exceptions import ValidationError as DjangoValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.common.viewsets import OrgReadOnlyViewSet, OrgScopedModelViewSet

from .models import (
    FeedBatch,
    ProductionTask,
    ProductionTaskComponent,
    RawMaterialBatch,
    Recipe,
    RecipeComponent,
    RecipeVersion,
)
from .serializers import (
    FeedBatchSerializer,
    ProductionTaskComponentSerializer,
    ProductionTaskSerializer,
    RawMaterialBatchSerializer,
    RecipeComponentSerializer,
    RecipeSerializer,
    RecipeVersionSerializer,
)
from .services.cancel_task import (
    FeedTaskCancelError,
    cancel_production_task,
)
from .services.execute_task import (
    FeedTaskExecuteError,
    execute_production_task,
)


class RecipeViewSet(OrgScopedModelViewSet):
    serializer_class = RecipeSerializer
    queryset = Recipe.objects.all()
    module_code = "feed"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["direction", "is_medicated", "is_active"]
    search_fields = ["code", "name"]
    ordering = ["code"]


class _ChildOfRecipeMixin:
    """
    Для дочерних моделей рецептуры (RecipeVersion, RecipeComponent):
    организация наследуется через FK (recipe__organization), но самой
    organization-колонки в модели нет — поэтому базовый
    OrgScopedModelViewSet.perform_create передал бы её в save() как
    kwarg и упал в TypeError. Возвращаем {} и валидацию делаем
    в сериализаторе/при выборе FK.
    """

    def _save_kwargs_for_create(self, serializer) -> dict:
        kwargs: dict = {}
        model = serializer.Meta.model if hasattr(serializer, "Meta") else None
        if model is not None:
            field_names = {f.name for f in model._meta.get_fields()}
            user = getattr(self.request, "user", None)
            if user and getattr(user, "is_authenticated", False):
                if "author" in field_names:
                    kwargs["author"] = user
                elif "created_by" in field_names:
                    kwargs["created_by"] = user
        return kwargs


class RecipeVersionViewSet(_ChildOfRecipeMixin, OrgScopedModelViewSet):
    serializer_class = RecipeVersionSerializer
    queryset = RecipeVersion.objects.select_related("recipe").prefetch_related(
        "components"
    )
    module_code = "feed"
    organization_field = "recipe__organization"
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["recipe", "status"]
    ordering = ["-version_number"]


class RecipeComponentViewSet(_ChildOfRecipeMixin, OrgScopedModelViewSet):
    serializer_class = RecipeComponentSerializer
    queryset = RecipeComponent.objects.select_related("nomenclature", "vet_drug")
    module_code = "feed"
    organization_field = "recipe_version__recipe__organization"
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["recipe_version"]


class RawMaterialBatchViewSet(OrgScopedModelViewSet):
    serializer_class = RawMaterialBatchSerializer
    queryset = RawMaterialBatch.objects.select_related(
        "nomenclature", "supplier", "warehouse", "unit"
    )
    module_code = "feed"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status", "nomenclature", "supplier", "warehouse"]
    search_fields = ["doc_number", "nomenclature__sku"]
    ordering = ["-received_date"]

    def perform_create(self, serializer):
        """
        Авто-генерация doc_number если не задан + автоустановка module=feed.
        """
        from apps.common.services.numbering import next_doc_number
        from apps.modules.models import Module

        org = getattr(self.request, "organization", None)
        kwargs = self._save_kwargs_for_create(serializer)
        if not serializer.validated_data.get("module"):
            try:
                kwargs["module"] = Module.objects.get(code="feed")
            except Module.DoesNotExist:
                pass
        if org is not None and not serializer.validated_data.get("doc_number"):
            kwargs["doc_number"] = next_doc_number(
                RawMaterialBatch,
                organization=org,
                prefix="СЫР",
                on_date=serializer.validated_data.get("received_date"),
            )
        instance = serializer.save(**kwargs)
        from apps.audit.models import AuditLog
        self._write_audit(AuditLog.Action.CREATE, instance)

    @action(detail=True, methods=["post"], url_path="release_quarantine")
    def release_quarantine(self, request, pk=None):
        """
        POST /api/feed/raw-batches/{id}/release_quarantine/
        Выпустить партию из карантина (status: QUARANTINE → AVAILABLE).

        Lab result опциональный (отдельный сервис ``release_raw_material_quarantine``
        требует его явно). Для UI-шной кнопки достаточно ручного снятия —
        ответственность подтверждения качества лежит на технологе.
        """
        batch = self.get_object()
        if batch.status != RawMaterialBatch.Status.QUARANTINE:
            raise DRFValidationError(
                {"status": (
                    f"Карантин снимается только из QUARANTINE, текущий: "
                    f"{batch.get_status_display()}."
                )}
            )
        batch.status = RawMaterialBatch.Status.AVAILABLE
        batch.save(update_fields=["status", "updated_at"])

        from apps.audit.models import AuditLog
        from apps.audit.services.writer import audit_log
        audit_log(
            organization=batch.organization,
            module=batch.module,
            actor=request.user,
            action=AuditLog.Action.POST,
            entity=batch,
            action_verb=f"raw batch {batch.doc_number} released from quarantine",
        )
        return Response(self.get_serializer(batch).data)

    @action(detail=True, methods=["post"], url_path="reject_quarantine")
    def reject_quarantine(self, request, pk=None):
        """
        POST /api/feed/raw-batches/{id}/reject_quarantine/
        Body: {"reason": "..."}
        Отклонить партию из карантина (status: QUARANTINE → REJECTED).
        """
        batch = self.get_object()
        reason = (request.data.get("reason") or "").strip()
        if batch.status != RawMaterialBatch.Status.QUARANTINE:
            raise DRFValidationError(
                {"status": (
                    f"Отклонить можно только из QUARANTINE, текущий: "
                    f"{batch.get_status_display()}."
                )}
            )
        if not reason:
            raise DRFValidationError({"reason": "Причина обязательна."})

        batch.status = RawMaterialBatch.Status.REJECTED
        batch.rejection_reason = reason
        batch.save(update_fields=["status", "rejection_reason", "updated_at"])

        from apps.audit.models import AuditLog
        from apps.audit.services.writer import audit_log
        audit_log(
            organization=batch.organization,
            module=batch.module,
            actor=request.user,
            action=AuditLog.Action.UNPOST,
            entity=batch,
            action_verb=f"raw batch {batch.doc_number} rejected · {reason}",
        )
        return Response(self.get_serializer(batch).data)


class ProductionTaskViewSet(OrgScopedModelViewSet):
    """
    /api/feed/production-tasks/ — задания на замес.
    POST /api/feed/production-tasks/{id}/execute/ — провести (сервис).
    """

    serializer_class = ProductionTaskSerializer
    queryset = ProductionTask.objects.select_related(
        "recipe_version__recipe", "production_line", "technologist"
    ).prefetch_related("components")
    module_code = "feed"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status", "recipe_version", "production_line", "shift"]
    search_fields = ["doc_number"]
    ordering = ["-scheduled_at"]

    def perform_create(self, serializer):
        """
        После создания задания автоматически копируем компоненты из выбранной
        версии рецепта (с FIFO-подбором партий сырья). Без этого замес
        невозможно провести — execute_task требует наличия компонентов.
        """
        from .services.copy_components import copy_components_from_version

        instance = serializer.save(**self._save_kwargs_for_create(serializer))
        copy_components_from_version(instance)

        from apps.audit.models import AuditLog
        self._write_audit(AuditLog.Action.CREATE, instance)

    @action(detail=True, methods=["post"])
    def execute(self, request, pk=None):
        """
        POST /api/feed/production-tasks/{id}/execute/
        Body: {"output_warehouse": "uuid", "storage_bin": "uuid", "actual_quantity_kg": "1000"}
        """
        from apps.warehouses.models import ProductionBlock, Warehouse

        task = self.get_object()
        wh_id = request.data.get("output_warehouse")
        bin_id = request.data.get("storage_bin")
        actual = request.data.get("actual_quantity_kg")

        if not wh_id or not bin_id:
            raise DRFValidationError(
                {"detail": "output_warehouse и storage_bin обязательны."}
            )

        try:
            wh = Warehouse.objects.get(pk=wh_id)
            bin_block = ProductionBlock.objects.get(pk=bin_id)
        except (Warehouse.DoesNotExist, ProductionBlock.DoesNotExist):
            raise DRFValidationError({"detail": "output_warehouse или storage_bin не найдены."})

        from decimal import Decimal
        actual_dec = Decimal(str(actual)) if actual is not None else None

        try:
            result = execute_production_task(
                task, output_warehouse=wh, storage_bin=bin_block,
                actual_quantity_kg=actual_dec, user=request.user,
            )
        except FeedTaskExecuteError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )

        task.refresh_from_db()
        data = self.get_serializer(task).data
        data["_result"] = {
            "feed_batch": {
                "id": str(result.feed_batch.id),
                "doc_number": result.feed_batch.doc_number,
                "quantity_kg": str(result.feed_batch.quantity_kg),
                "unit_cost_uzs": str(result.feed_batch.unit_cost_uzs),
                "total_cost_uzs": str(result.feed_batch.total_cost_uzs),
                "withdrawal_period_ends": (
                    result.feed_batch.withdrawal_period_ends.isoformat()
                    if result.feed_batch.withdrawal_period_ends
                    else None
                ),
            },
            "journal_entry": {
                "id": str(result.journal_entry.id),
                "doc_number": result.journal_entry.doc_number,
            },
            "stock_movements": [
                {"id": str(sm.id), "doc_number": sm.doc_number, "kind": sm.kind}
                for sm in result.stock_movements
            ],
        }
        return Response(data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """POST /api/feed/production-tasks/{id}/cancel/
        Body: {"reason": str (optional)}
        """
        task = self.get_object()
        try:
            cancel_production_task(
                task, reason=request.data.get("reason", ""), user=request.user,
            )
        except FeedTaskCancelError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        task.refresh_from_db()
        return Response(self.get_serializer(task).data)


class FeedBatchViewSet(OrgReadOnlyViewSet):
    """Read-only: FeedBatch создаётся только через execute_production_task."""

    serializer_class = FeedBatchSerializer
    queryset = FeedBatch.objects.select_related(
        "recipe_version__recipe", "storage_bin", "storage_warehouse", "produced_by_task"
    )
    module_code = "feed"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        "status",
        "quality_passport_status",
        "is_medicated",
        "recipe_version",
    ]
    search_fields = ["doc_number"]
    ordering = ["-produced_at"]

    @action(detail=True, methods=["post"], url_path="approve_passport")
    def approve_passport(self, request, pk=None):
        """
        POST /api/feed/feed-batches/{id}/approve_passport/
        Выпустить паспорт качества (PASSED) → status: QUALITY_CHECK → APPROVED.
        После этого партия становится продаваемой и расходуемой.
        """
        batch = self.get_object()
        if batch.status != FeedBatch.Status.QUALITY_CHECK:
            raise DRFValidationError(
                {"status": (
                    f"Паспорт выпускается только из «На лаб. контроле», "
                    f"текущий статус: {batch.get_status_display()}."
                )}
            )
        batch.status = FeedBatch.Status.APPROVED
        batch.quality_passport_status = FeedBatch.PassportStatus.PASSED
        batch.save(update_fields=[
            "status", "quality_passport_status", "updated_at",
        ])

        from apps.audit.models import AuditLog
        from apps.audit.services.writer import audit_log
        audit_log(
            organization=batch.organization,
            module=batch.module,
            actor=request.user,
            action=AuditLog.Action.POST,
            entity=batch,
            action_verb=f"feed batch {batch.doc_number} passport approved",
        )
        return Response(self.get_serializer(batch).data)

    @action(detail=True, methods=["post"], url_path="reject_passport")
    def reject_passport(self, request, pk=None):
        """
        POST /api/feed/feed-batches/{id}/reject_passport/
        Body: {"reason": "..."}
        Паспорт не пройден (FAILED) → status: QUALITY_CHECK → REJECTED.
        """
        batch = self.get_object()
        reason = (request.data.get("reason") or "").strip()
        if batch.status != FeedBatch.Status.QUALITY_CHECK:
            raise DRFValidationError(
                {"status": (
                    f"Отклонить паспорт можно только из «На лаб. контроле», "
                    f"текущий статус: {batch.get_status_display()}."
                )}
            )
        if not reason:
            raise DRFValidationError({"reason": "Причина отклонения обязательна."})

        batch.status = FeedBatch.Status.REJECTED
        batch.quality_passport_status = FeedBatch.PassportStatus.FAILED
        batch.save(update_fields=[
            "status", "quality_passport_status", "updated_at",
        ])

        from apps.audit.models import AuditLog
        from apps.audit.services.writer import audit_log
        audit_log(
            organization=batch.organization,
            module=batch.module,
            actor=request.user,
            action=AuditLog.Action.UNPOST,
            entity=batch,
            action_verb=f"feed batch {batch.doc_number} passport rejected · {reason}",
        )
        return Response(self.get_serializer(batch).data)
