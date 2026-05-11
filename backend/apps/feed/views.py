from django.core.exceptions import ValidationError as DjangoValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.csv_export import CSVRenderer
from apps.common.permissions import HasModulePermission
from apps.common.viewsets import (
    OrganizationContextMixin,
    OrgReadOnlyViewSet,
    OrgScopedModelViewSet,
)

from .models import (
    FeedBagLot,
    FeedBatch,
    FeedLotShrinkageState,
    FeedShrinkageProfile,
    ProductionTask,
    ProductionTaskComponent,
    RawMaterialBatch,
    Recipe,
    RecipeComponent,
    RecipeVersion,
)
from .serializers import (
    FeedBagLotSerializer,
    FeedBatchSerializer,
    FeedLotShrinkageStateSerializer,
    FeedShrinkageProfileSerializer,
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
from .services.package_feed_batch import (
    FeedPackageError,
    package_feed_batch,
)


class RecipeViewSet(OrgScopedModelViewSet):
    serializer_class = RecipeSerializer
    queryset = Recipe.objects.all()
    module_code = "feed"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["direction", "is_medicated", "is_active"]
    search_fields = ["code", "name"]
    ordering = ["code"]

    def destroy(self, request, *args, **kwargs):
        """
        DELETE рецепта.

        Default Django: на Recipe ссылаются `RecipeVersion`, `FeedShrinkageProfile`,
        `FeedConsumptionPlan` с `on_delete=PROTECT`, а на сами версии — ещё
        `ProductionTask`/`FeedBatch`/`FeedBagLot` PROTECT. Поэтому `Recipe.delete()`
        кидал `ProtectedError`, который у DRF превращается в нелочённый 500.

        Стратегия:
          1. В атомарной транзакции — каскадно убираем безопасные связки
             (профили усушки, планы потребления) и сами версии (RecipeComponent
             у версий — CASCADE).
          2. Если на версиях висят задания/партии/мешки — `RecipeVersion.delete()`
             поднимет `ProtectedError`. Транзакция откатится; вместо 500 вернём
             409 с понятным сообщением — оператор может скрыть рецепт через
             `PATCH is_active=False`.
        """
        from django.db import transaction
        from django.db.models.deletion import ProtectedError

        instance = self.get_object()
        try:
            with transaction.atomic():
                instance.feed_shrinkage_profiles.all().delete()
                instance.consumption_plans.all().delete()
                # CASCADE: RecipeComponent.recipe_version
                instance.versions.all().delete()
                instance.delete()
        except ProtectedError:
            from rest_framework import status as http_status
            return Response(
                {
                    "detail": (
                        "Невозможно удалить рецепт: на него ссылаются задания "
                        "на замес, партии готового корма или мешки. Чтобы скрыть "
                        "рецепт из активных, снимите флаг «Активен» (is_active)."
                    ),
                },
                status=http_status.HTTP_409_CONFLICT,
            )
        return Response(status=204)


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
        Создание партии сырья. Инвариант «склад — источник истины»:
        на складе уже должен быть приход по этому SKU (через /stock → +приход
        или PO.confirm). Партия — это lot-метаданные (Дюваль, влажность,
        карантин) поверх существующего остатка.

        Если оператор уже сделал /stock → +приход, удобнее использовать
        action `/promote` через StockMovementViewSet — он перепривязывает
        существующий movement к новой партии без двойного INCOMING.
        Этот endpoint оставлен для backward-compat и для случаев когда
        партия создаётся через API.

        Авто-генерация doc_number + module=feed.
        """
        from apps.common.services.numbering import next_doc_number
        from apps.modules.models import Module
        from apps.warehouses.services.balance import compute_warehouse_balance_for_sku
        from rest_framework.exceptions import ValidationError as DRFValidationError

        org = getattr(self.request, "organization", None)
        nomenclature = serializer.validated_data.get("nomenclature")
        warehouse = serializer.validated_data.get("warehouse")
        qty = serializer.validated_data.get("quantity")

        # Warehouse-first guard: на складе должен быть приход >= qty партии.
        # Без backing inventory партия становится «фантомной» — журнал склада
        # рассинхронизируется с lot-учётом (двойной счёт при будущем PO.confirm).
        if warehouse and nomenclature and qty is not None:
            on_hand = compute_warehouse_balance_for_sku(warehouse, nomenclature)
            from decimal import Decimal
            need = Decimal(str(qty))
            if on_hand < need:
                raise DRFValidationError({
                    "warehouse": (
                        f"На складе «{warehouse.code}» остаток по SKU "
                        f"«{nomenclature.sku}» = {on_hand}, нужно ≥ {need}. "
                        f"Сначала оприходуйте через /stock → «+ Приход» "
                        f"(будет создан автозакуп) или через /purchases, "
                        f"потом создавайте партию здесь. "
                        f"Если приход уже есть — используйте «Превратить в "
                        f"партию» на самой записи в /stock."
                    ),
                })

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
        # Партия НЕ создаёт свой StockMovement INCOMING — backing уже есть
        # на складе (проверка выше). Это симметрия с vet:
        # /stock → +приход + auto-PO → потом vet/feed lot-метаданные.
        # Если пользователь хотел promote существующего movement — он делает
        # это через StockMovementViewSet.promote_to_raw_batch (re-link source).
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

    @action(detail=True, methods=["post"], url_path="refresh-components")
    def refresh_components(self, request, pk=None):
        """
        POST /api/feed/production-tasks/{id}/refresh-components/

        Перешолвить партии сырья для компонентов с source_batch IS NULL —
        на случай если партии пришли уже после создания задания.
        Работает только для PLANNED-заданий.
        """
        from .services.copy_components import refresh_unassigned_task_components

        task = self.get_object()
        updated = refresh_unassigned_task_components(task)
        task.refresh_from_db()
        return Response({
            "updated_count": len(updated),
            "task": self.get_serializer(task).data,
        })

    @action(detail=True, methods=["post"])
    def execute(self, request, pk=None):
        """
        POST /api/feed/production-tasks/{id}/execute/
        Body: {"output_warehouse": "uuid", "storage_bin": "uuid", "actual_quantity_kg": "1000"}
        """
        from apps.warehouses.models import ProductionBlock, Warehouse

        from .services.copy_components import refresh_unassigned_task_components

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

        # Авто-pодхват свежих партий — если за время «висело» задание
        # пришло сырьё, попытаемся резолвить его прямо сейчас, чтобы execute
        # не упал на «нет партии».
        refresh_unassigned_task_components(task)
        task.refresh_from_db()

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

    @action(detail=True, methods=["post"], url_path="package")
    def package(self, request, pk=None):
        """
        POST /api/feed/feed-batches/{id}/package/
        Body: {
          "bag_count": 80,
          "bag_weight_kg": "50",
          "storage_warehouse": "<uuid>",
          "storage_bin": "<uuid>" (опционально),
          "packaging_nomenclature": "<uuid>" (опц., авто KORM-XALTA-25/50 по весу),
          "packaging_warehouse": "<uuid>" (опц., default = storage_warehouse),
          "notes": "..."  (опционально)
        }

        Расфасовать (часть) партии в N мешков. Партия должна быть APPROVED.
        Можно вызывать несколько раз — каждая фасовка создаёт свой FeedBagLot.
        Если резолвится SKU пустых мешков — автоматически списывает их
        OUTGOING StockMovement-ом со склада упаковки.
        """
        from decimal import Decimal

        from apps.nomenclature.models import NomenclatureItem
        from apps.warehouses.models import ProductionBlock, Warehouse

        batch = self.get_object()
        bag_count = request.data.get("bag_count")
        bag_weight = request.data.get("bag_weight_kg")
        wh_id = request.data.get("storage_warehouse")
        bin_id = request.data.get("storage_bin")
        pack_nom_id = request.data.get("packaging_nomenclature")
        pack_wh_id = request.data.get("packaging_warehouse")
        notes = request.data.get("notes", "") or ""

        if bag_count is None or wh_id is None or bag_weight is None:
            raise DRFValidationError({
                "detail": (
                    "bag_count, bag_weight_kg и storage_warehouse обязательны."
                ),
            })

        try:
            bag_count_int = int(bag_count)
        except (TypeError, ValueError):
            raise DRFValidationError({"bag_count": "Должно быть целое число."})

        try:
            bag_weight_dec = Decimal(str(bag_weight))
        except Exception:
            raise DRFValidationError({"bag_weight_kg": "Некорректное число."})

        try:
            wh = Warehouse.objects.get(pk=wh_id)
        except Warehouse.DoesNotExist:
            raise DRFValidationError(
                {"storage_warehouse": "Склад не найден."}
            )
        bin_block = None
        if bin_id:
            try:
                bin_block = ProductionBlock.objects.get(pk=bin_id)
            except ProductionBlock.DoesNotExist:
                raise DRFValidationError({"storage_bin": "Бункер не найден."})

        pack_nom = None
        if pack_nom_id:
            try:
                pack_nom = NomenclatureItem.objects.get(pk=pack_nom_id)
            except NomenclatureItem.DoesNotExist:
                raise DRFValidationError(
                    {"packaging_nomenclature": "SKU не найден."}
                )
        pack_wh = None
        if pack_wh_id:
            try:
                pack_wh = Warehouse.objects.get(pk=pack_wh_id)
            except Warehouse.DoesNotExist:
                raise DRFValidationError(
                    {"packaging_warehouse": "Склад мешков не найден."}
                )

        try:
            result = package_feed_batch(
                batch,
                bag_count=bag_count_int,
                bag_weight_kg=bag_weight_dec,
                storage_warehouse=wh,
                storage_bin=bin_block,
                packaging_nomenclature=pack_nom,
                packaging_warehouse=pack_wh,
                notes=notes,
                user=request.user,
            )
        except FeedPackageError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )

        batch.refresh_from_db()
        data = self.get_serializer(batch).data
        data["_result"] = {
            "bag_lot": FeedBagLotSerializer(
                result.bag_lot, context=self.get_serializer_context(),
            ).data,
            "stock_movements": [
                {"id": str(sm.id), "doc_number": sm.doc_number, "kind": sm.kind}
                for sm in result.stock_movements
            ],
        }
        return Response(data)


class FeedBagLotViewSet(OrgReadOnlyViewSet):
    """Read-only: FeedBagLot создаётся через FeedBatch.package action.

    Список доступен админам и операторам склада мешков; cost-поля скрыты
    для пользователей без `feed.r` (через FinancialFieldsMixin).
    """

    serializer_class = FeedBagLotSerializer
    queryset = FeedBagLot.objects.select_related(
        "source_feed_batch",
        "recipe_version__recipe",
        "storage_warehouse",
        "storage_bin",
    )
    module_code = "feed"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        "status",
        "is_medicated",
        "source_feed_batch",
        "recipe_version",
        "storage_warehouse",
    ]
    search_fields = ["doc_number", "source_feed_batch__doc_number"]
    ordering = ["-packaged_at"]


# ─── Shrinkage: profiles + state + report ─────────────────────────────────


class FeedShrinkageProfileViewSet(OrgScopedModelViewSet):
    """CRUD профилей усушки сырья / готового корма (spec §6).

    DELETE мягкий: профиль помечается is_active=False, чтобы не сломать
    ссылку с FeedLotShrinkageState. Жёсткое удаление через админку.
    """

    serializer_class = FeedShrinkageProfileSerializer
    queryset = FeedShrinkageProfile.objects.select_related(
        "nomenclature", "recipe", "warehouse"
    )
    module_code = "feed"
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = [
        "target_type",
        "nomenclature",
        "recipe",
        "warehouse",
        "is_active",
    ]
    ordering = ["target_type", "-updated_at"]

    def perform_destroy(self, instance):
        # Soft delete — не ломаем ссылки из FeedLotShrinkageState
        if instance.is_active:
            instance.is_active = False
            instance.save(update_fields=["is_active", "updated_at"])
            from apps.audit.models import AuditLog
            self._write_audit(AuditLog.Action.UPDATE, instance, verb="deactivate FeedShrinkageProfile")


class FeedLotShrinkageStateViewSet(OrgReadOnlyViewSet):
    """Read-only состояние усушки по партиям + админские actions:

    - POST /apply         — прогон алгоритма (можно по дате и/или конкретной партии).
    - POST /{id}/reset    — откат всех движений усушки этой партии и сброс state.
    """

    serializer_class = FeedLotShrinkageStateSerializer
    queryset = FeedLotShrinkageState.objects.select_related(
        "profile__nomenclature", "profile__recipe"
    )
    module_code = "feed"
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["lot_type", "lot_id", "profile", "is_frozen"]
    ordering = ["-updated_at"]

    @action(detail=False, methods=["post"], url_path="apply")
    def apply_now(self, request):
        """POST /api/feed/shrinkage-state/apply/

        Body (все поля опциональны):
            { "on_date": "YYYY-MM-DD", "lot_type": "raw_arrival|production_batch", "lot_id": "uuid" }

        - без полей → прогон по всем партиям организации;
        - с lot_type+lot_id → точечный прогон одной партии (для исправления после редактирования профиля).
        """
        from datetime import date as _date
        from decimal import Decimal

        from .services.shrinkage_runner import (
            apply_for_organization,
            apply_for_specific_lot,
        )

        on_date_str = request.data.get("on_date")
        try:
            on_date = _date.fromisoformat(on_date_str) if on_date_str else _date.today()
        except (TypeError, ValueError):
            raise DRFValidationError({"on_date": "Ожидается YYYY-MM-DD."})

        lot_type = request.data.get("lot_type")
        lot_id = request.data.get("lot_id")

        if bool(lot_type) ^ bool(lot_id):
            raise DRFValidationError(
                {"detail": "lot_type и lot_id указываются вместе."}
            )

        if lot_type and lot_id:
            from django.core.exceptions import ObjectDoesNotExist
            from rest_framework.exceptions import NotFound

            valid = {c[0] for c in FeedLotShrinkageState.LotType.choices}
            if lot_type not in valid:
                raise DRFValidationError({"lot_type": f"Допустимо: {sorted(valid)}."})
            try:
                res = apply_for_specific_lot(lot_type=lot_type, lot_id=lot_id, today=on_date)
            except ObjectDoesNotExist:
                raise NotFound({"detail": "Партия не найдена."})
            return Response(_apply_result_to_dict(res))

        results = apply_for_organization(request.organization, today=on_date)
        applied = [r for r in results if not r.skipped]
        return Response({
            "on_date": on_date.isoformat(),
            "lots_total": len(results),
            "lots_applied": len(applied),
            "loss_kg": str(sum((r.loss_kg for r in applied), Decimal("0"))),
            "movements": sum(1 for r in applied if r.movement_id),
            "results": [_apply_result_to_dict(r) for r in results],
        })

    @action(detail=True, methods=["get"], url_path="history")
    def history(self, request, pk=None):
        """GET /api/feed/shrinkage-state/{id}/history/

        Возвращает хронологию списаний усушки по партии: каждое движение —
        точка `{date, lost_kg, remaining_kg}`. Используется фронтом для
        sparkline в виджете партии.
        """
        from decimal import Decimal

        from django.contrib.contenttypes.models import ContentType

        from apps.warehouses.models import StockMovement

        state = self.get_object()
        ct = ContentType.objects.get_for_model(FeedLotShrinkageState)
        movements = (
            StockMovement.objects.filter(
                kind=StockMovement.Kind.SHRINKAGE,
                source_content_type=ct,
                source_object_id=state.id,
            )
            .order_by("date")
            .values("id", "date", "quantity", "amount_uzs")
        )

        initial = Decimal(state.initial_quantity)
        running_loss = Decimal("0")
        points = []
        for m in movements:
            running_loss += Decimal(m["quantity"])
            points.append({
                "movement_id": str(m["id"]),
                "date": m["date"].date().isoformat() if m["date"] else None,
                "lost_kg": str(m["quantity"]),
                "lost_uzs": str(m["amount_uzs"]),
                "cumulative_loss_kg": str(running_loss),
                "remaining_kg": str(max(initial - running_loss, Decimal("0"))),
            })

        return Response({
            "state_id": str(state.id),
            "initial_quantity": str(initial),
            "accumulated_loss": str(state.accumulated_loss),
            "is_frozen": state.is_frozen,
            "points": points,
        })

    @action(detail=True, methods=["post"], url_path="reset")
    def reset(self, request, pk=None):
        """POST /api/feed/shrinkage-state/{id}/reset/ — админская операция.

        Откатывает все StockMovement(kind=shrinkage) этой партии, восстанавливает
        current_quantity и сбрасывает state в исходное состояние. Следующий цикл
        алгоритма пересчитает усушку с нуля.
        """
        state = self.get_object()
        from .services.shrinkage_runner import reset_lot_shrinkage

        info = reset_lot_shrinkage(state)
        from apps.audit.models import AuditLog
        self._write_audit(
            AuditLog.Action.UNPOST,
            state,
            verb=f"reset shrinkage state {state.id}: reverted={info['reverted_movements']}",
        )
        return Response({
            "ok": True,
            "reverted_movements": info["reverted_movements"],
            "restored_kg": str(info["restored_kg"]),
        })


def _apply_result_to_dict(r):
    return {
        "lot_type": r.lot_type,
        "lot_id": r.lot_id,
        "skipped": r.skipped,
        "skipped_reason": r.skipped_reason or None,
        "loss_kg": str(r.loss_kg),
        "periods_applied": r.periods_applied,
        "frozen": r.frozen,
        "state_id": r.state_id,
        "movement_id": r.movement_id,
    }


class FeedShrinkageReportView(OrganizationContextMixin, APIView):
    """GET /api/feed/shrinkage-report/ — агрегированный отчёт «Потери от усушки».

    ?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD&group_by=ingredient|warehouse

    Возвращает: список строк {key, label, total_loss_kg, total_loss_uzs}
    + summary {date_from, date_to, total_kg, total_uzs}.
    """

    module_code = "feed"
    permission_classes = [IsAuthenticated, HasModulePermission]
    # CSVRenderer нужен только для DRF content-negotiation (?format=csv).
    # Реальный CSV рендерится через stream_csv() ниже.
    renderer_classes = [JSONRenderer, CSVRenderer]

    def get(self, request, *args, **kwargs):
        from datetime import date as _date
        from decimal import Decimal
        from django.db.models import Sum

        from apps.warehouses.models import StockMovement

        df = request.query_params.get("date_from")
        dt = request.query_params.get("date_to")
        group_by = request.query_params.get("group_by", "ingredient")
        if group_by not in {"ingredient", "warehouse"}:
            raise DRFValidationError({"group_by": "Допустимо: ingredient | warehouse."})

        try:
            df_d = _date.fromisoformat(df) if df else None
            dt_d = _date.fromisoformat(dt) if dt else None
        except ValueError:
            raise DRFValidationError({"detail": "Даты ожидаются в формате YYYY-MM-DD."})

        qs = StockMovement.objects.filter(
            organization=request.organization,
            kind=StockMovement.Kind.SHRINKAGE,
        )
        if df_d:
            qs = qs.filter(date__date__gte=df_d)
        if dt_d:
            qs = qs.filter(date__date__lte=dt_d)

        if group_by == "ingredient":
            grouped = (
                qs.values("nomenclature_id", "nomenclature__sku", "nomenclature__name")
                .annotate(total_kg=Sum("quantity"), total_uzs=Sum("amount_uzs"))
                .order_by("-total_kg")
            )
            rows = [
                {
                    "key": str(r["nomenclature_id"]),
                    "label": f"{r['nomenclature__sku']} · {r['nomenclature__name']}",
                    "total_loss_kg": str(r["total_kg"] or Decimal("0")),
                    "total_loss_uzs": str(r["total_uzs"] or Decimal("0")),
                }
                for r in grouped
            ]
        else:
            grouped = (
                qs.values("warehouse_from_id", "warehouse_from__code", "warehouse_from__name")
                .annotate(total_kg=Sum("quantity"), total_uzs=Sum("amount_uzs"))
                .order_by("-total_kg")
            )
            rows = [
                {
                    "key": str(r["warehouse_from_id"]) if r["warehouse_from_id"] else None,
                    "label": (
                        f"{r['warehouse_from__code']} · {r['warehouse_from__name']}"
                        if r["warehouse_from_id"]
                        else "(без склада)"
                    ),
                    "total_loss_kg": str(r["total_kg"] or Decimal("0")),
                    "total_loss_uzs": str(r["total_uzs"] or Decimal("0")),
                }
                for r in grouped
            ]

        agg = qs.aggregate(total_kg=Sum("quantity"), total_uzs=Sum("amount_uzs"))
        total_kg = agg["total_kg"] or Decimal("0")
        total_uzs = agg["total_uzs"] or Decimal("0")

        from apps.common.csv_export import stream_csv, wants_csv
        if wants_csv(request):
            label_col = "Ингредиент" if group_by == "ingredient" else "Склад"
            header = [label_col, "Списано (кг)", "Стоимость (UZS)"]
            data_rows = [[r["label"], r["total_loss_kg"], r["total_loss_uzs"]] for r in rows]
            data_rows.append(["Итого", str(total_kg), str(total_uzs)])
            period = f"{df_d or 'all'}_{dt_d or 'all'}"
            return stream_csv(f"feed-shrinkage_{group_by}_{period}.csv", header, data_rows)

        return Response({
            "date_from": df_d.isoformat() if df_d else None,
            "date_to": dt_d.isoformat() if dt_d else None,
            "group_by": group_by,
            "rows": rows,
            "summary": {
                "total_loss_kg": str(total_kg),
                "total_loss_uzs": str(total_uzs),
            },
        })


class FeedDashboardView(OrganizationContextMixin, APIView):
    """GET /api/feed/dashboard/?date=YYYY-MM-DD

    Сводка дня по модулю «Корма» — Excel-style панель для одной страницы:
      - recipe_matrix: все активные рецептуры × ингредиенты (доли %)
      - incoming: приход сырья за день (RawMaterialBatch + manual incoming
        StockMovement, не привязанные к партии)
      - outgoing: расход сырья за день (StockMovement OUTGOING для feed-сырья)
      - production: произведено корма за день (FeedBatch)
      - stock: текущие остатки сырья на feed-складах

    Без фильтров `date` — берём сегодня.
    """

    module_code = "feed"
    permission_classes = [IsAuthenticated, HasModulePermission]

    def get(self, request, *args, **kwargs):
        from datetime import date as _date, datetime, time, timedelta
        from decimal import Decimal
        from django.db.models import F, Sum
        from django.utils import timezone

        from apps.feed.models import (
            FeedBatch, RawMaterialBatch, RecipeComponent, RecipeVersion,
        )
        from apps.warehouses.models import StockMovement

        org = request.organization

        date_str = request.query_params.get("date")
        try:
            day = _date.fromisoformat(date_str) if date_str else _date.today()
        except ValueError:
            raise DRFValidationError({"date": "Ожидаю YYYY-MM-DD."})

        tz = timezone.get_current_timezone()
        day_start = datetime.combine(day, time.min, tzinfo=tz)
        day_end = day_start + timedelta(days=1)

        # ── Recipe matrix (active versions × components) ──────────────────
        versions = (
            RecipeVersion.objects
            .filter(recipe__organization=org, status=RecipeVersion.Status.ACTIVE)
            .select_related("recipe")
            .order_by("recipe__code", "version_number")
        )
        version_ids = [v.id for v in versions]
        components = (
            RecipeComponent.objects
            .filter(recipe_version_id__in=version_ids)
            .select_related("nomenclature", "nomenclature__unit")
            .order_by("nomenclature__sku")
        )
        # ingredient → list per version. shares value = {id, share} чтобы
        # фронт мог делать PATCH /recipe-components/{id}/ для inline-edit.
        comp_map: dict[str, dict[str, dict[str, str]]] = {}
        ingredient_meta: dict[str, dict] = {}
        for c in components:
            sku = c.nomenclature.sku
            ingredient_meta.setdefault(sku, {
                "sku": sku,
                "name": c.nomenclature.name,
                "unit": c.nomenclature.unit.code,
                "nomenclature_id": str(c.nomenclature_id),
            })
            comp_map.setdefault(sku, {})[str(c.recipe_version_id)] = {
                "id": str(c.id),
                "share": str(c.share_percent),
            }

        # Расширяем список ингредиентов: помимо тех, что уже есть в рецептах,
        # добавляем все KORM-* SKU из номенклатуры — чтобы пользователь мог
        # вписать долю для нового ингредиента прямо из матрицы.
        from apps.nomenclature.models import NomenclatureItem
        all_korm = NomenclatureItem.objects.filter(
            organization=org, sku__startswith="KORM-", is_active=True,
        ).exclude(sku__startswith="KORM-XALTA").select_related("unit").order_by("sku")
        for item in all_korm:
            ingredient_meta.setdefault(item.sku, {
                "sku": item.sku,
                "name": item.name,
                "unit": item.unit.code,
                "nomenclature_id": str(item.id),
            })

        recipe_matrix = {
            "versions": [
                {
                    "id": str(v.id),
                    "recipe_code": v.recipe.code,
                    "recipe_name": v.recipe.name,
                    "version": v.version_number,
                    "label": f"{v.recipe.code} v{v.version_number}",
                }
                for v in versions
            ],
            "ingredients": [
                {
                    **ingredient_meta[sku],
                    "shares": comp_map.get(sku, {}),
                }
                for sku in sorted(ingredient_meta)
            ],
        }

        # ── Приход (incoming) за день ─────────────────────────────────────
        # 1. RawMaterialBatch с received_date == day
        raw_today = (
            RawMaterialBatch.objects
            .filter(organization=org, received_date=day)
            .select_related("nomenclature", "supplier", "warehouse")
            .order_by("doc_number")
        )
        # 2. Manual INCOMING StockMovement без привязки к партии
        incoming_movements = (
            StockMovement.objects
            .filter(
                organization=org,
                kind=StockMovement.Kind.INCOMING,
                module__code="feed",
                date__gte=day_start, date__lt=day_end,
                source_object_id__isnull=True,  # не привязаны
            )
            .select_related("nomenclature", "counterparty", "warehouse_to")
            .order_by("doc_number")
        )

        incoming = []
        for b in raw_today:
            incoming.append({
                "kind": "raw_batch",
                "doc": b.doc_number,
                "sku": b.nomenclature.sku,
                "name": b.nomenclature.name,
                "qty": str(b.quantity),
                "warehouse": b.warehouse.code,
                "supplier": b.supplier.name if b.supplier else None,
                "amount_uzs": str(
                    (Decimal(b.quantity) * Decimal(b.price_per_unit_uzs))
                    .quantize(Decimal("0.01"))
                ),
            })
        for m in incoming_movements:
            incoming.append({
                "kind": "movement",
                "doc": m.doc_number,
                "sku": m.nomenclature.sku,
                "name": m.nomenclature.name,
                "qty": str(m.quantity),
                "warehouse": m.warehouse_to.code if m.warehouse_to else None,
                "supplier": m.counterparty.name if m.counterparty else None,
                "amount_uzs": str(m.amount_uzs),
            })

        # ── Расход (outgoing) за день ─────────────────────────────────────
        outgoing = []
        out_qs = (
            StockMovement.objects
            .filter(
                organization=org,
                module__code="feed",
                kind__in=[
                    StockMovement.Kind.OUTGOING,
                    StockMovement.Kind.WRITE_OFF,
                ],
                date__gte=day_start, date__lt=day_end,
            )
            .select_related("nomenclature", "warehouse_from")
            .order_by("doc_number")
        )
        for m in out_qs:
            outgoing.append({
                "doc": m.doc_number,
                "sku": m.nomenclature.sku,
                "name": m.nomenclature.name,
                "qty": str(m.quantity),
                "warehouse": m.warehouse_from.code if m.warehouse_from else None,
                "kind": m.kind,
                "amount_uzs": str(m.amount_uzs),
            })

        # ── Production (произведено корма) ────────────────────────────────
        produced_today = (
            FeedBatch.objects
            .filter(
                organization=org,
                produced_at__gte=day_start, produced_at__lt=day_end,
            )
            .select_related("recipe_version__recipe")
            .order_by("doc_number")
        )
        production = []
        for fb in produced_today:
            v = fb.recipe_version
            production.append({
                "doc": fb.doc_number,
                "recipe_code": v.recipe.code,
                "recipe_name": v.recipe.name,
                "qty_kg": str(fb.quantity_kg),
                "current_kg": str(fb.current_quantity_kg),
                "status": fb.status,
            })

        # ── Текущие остатки сырья по SKU (не привязано к дате) ────────────
        # Берём net по StockMovement: Σ(IN − OUT) на feed-складах группируя по
        # nomenclature. Дешёвый способ без таблицы остатков.
        stock_in = (
            StockMovement.objects
            .filter(
                organization=org, module__code="feed",
                kind=StockMovement.Kind.INCOMING,
                nomenclature__sku__startswith="KORM-",
            )
            .values("nomenclature__sku", "nomenclature__name")
            .annotate(qty=Sum("quantity"))
        )
        stock_out = (
            StockMovement.objects
            .filter(
                organization=org, module__code="feed",
                kind__in=[
                    StockMovement.Kind.OUTGOING,
                    StockMovement.Kind.WRITE_OFF,
                ],
                nomenclature__sku__startswith="KORM-",
            )
            .values("nomenclature__sku", "nomenclature__name")
            .annotate(qty=Sum("quantity"))
        )
        in_map = {r["nomenclature__sku"]: (r["qty"] or Decimal(0), r["nomenclature__name"]) for r in stock_in}
        out_map = {r["nomenclature__sku"]: r["qty"] or Decimal(0) for r in stock_out}
        skus = sorted(set(in_map) | set(out_map))
        stock = []
        for sku in skus:
            inc = in_map.get(sku, (Decimal(0), ""))
            out = out_map.get(sku, Decimal(0))
            stock.append({
                "sku": sku,
                "name": in_map[sku][1] if sku in in_map else "",
                "incoming_total": str(inc[0]),
                "outgoing_total": str(out),
                "balance": str(inc[0] - out),
            })

        return Response({
            "date": day.isoformat(),
            "recipe_matrix": recipe_matrix,
            "incoming": incoming,
            "outgoing": outgoing,
            "production": production,
            "stock": stock,
            "summary": {
                "incoming_count": len(incoming),
                "outgoing_count": len(outgoing),
                "production_count": len(production),
                "production_total_kg": str(
                    sum((Decimal(p["qty_kg"]) for p in production), Decimal(0))
                ),
            },
        })
