from django.core.exceptions import ValidationError as DjangoValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import HasModulePermission
from apps.common.viewsets import (
    OrganizationContextMixin,
    OrgReadOnlyViewSet,
    OrgScopedModelViewSet,
)

from .models import (
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
            valid = {c[0] for c in FeedLotShrinkageState.LotType.choices}
            if lot_type not in valid:
                raise DRFValidationError({"lot_type": f"Допустимо: {sorted(valid)}."})
            res = apply_for_specific_lot(lot_type=lot_type, lot_id=lot_id, today=on_date)
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
