from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.common.lifecycle import DeleteReasonMixin, ImmutableStatusMixin
from apps.common.viewsets import OrgScopedModelViewSet

from .models import (
    SlaughterLabTest,
    SlaughterQualityCheck,
    SlaughterShift,
    SlaughterYield,
)
from .serializers import (
    SlaughterLabTestSerializer,
    SlaughterQualityCheckSerializer,
    SlaughterShiftSerializer,
    SlaughterYieldSerializer,
)
from .services.post_shift import SlaughterPostError, post_slaughter_shift
from .services.reverse_shift import (
    SlaughterReverseError,
    reverse_slaughter_shift,
)
from .services.stats import get_shift_kpi
from .services.timeline import get_shift_timeline


class SlaughterShiftViewSet(ImmutableStatusMixin, OrgScopedModelViewSet):
    serializer_class = SlaughterShiftSerializer
    queryset = SlaughterShift.objects.select_related(
        "line_block", "source_batch", "foreman"
    )
    module_code = "slaughter"
    immutable_statuses = ("posted", "cancelled")
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status", "line_block", "source_batch"]
    search_fields = ["doc_number"]
    ordering = ["-shift_date"]

    @action(detail=True, methods=["post"])
    def post_shift(self, request, pk=None):
        """POST /api/slaughter/shifts/{id}/post_shift/

        Body: {
          "output_warehouse": "uuid",
          "source_warehouse": "uuid"
        }
        """
        from apps.warehouses.models import Warehouse

        shift = self.get_object()
        out_wh_id = request.data.get("output_warehouse")
        src_wh_id = request.data.get("source_warehouse")

        if not out_wh_id:
            raise DRFValidationError({"output_warehouse": "Обязательно."})
        if not src_wh_id:
            raise DRFValidationError({"source_warehouse": "Обязательно."})

        try:
            out_wh = Warehouse.objects.get(pk=out_wh_id)
        except Warehouse.DoesNotExist:
            raise DRFValidationError({"output_warehouse": "Не найден."})

        try:
            src_wh = Warehouse.objects.get(pk=src_wh_id)
        except Warehouse.DoesNotExist:
            raise DRFValidationError({"source_warehouse": "Не найден."})

        try:
            result = post_slaughter_shift(
                shift,
                output_warehouse=out_wh,
                source_warehouse=src_wh,
                user=request.user,
            )
        except SlaughterPostError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )

        shift.refresh_from_db()
        data = self.get_serializer(shift).data
        data["_result"] = {
            "output_batches": [
                {"id": str(b.id), "doc_number": b.doc_number, "sku": b.nomenclature.sku}
                for b in result.output_batches
            ],
            "journal_entries": [
                {"id": str(je.id), "doc_number": je.doc_number}
                for je in result.journal_entries
            ],
            "stock_movements_count": len(result.stock_movements),
            "source_batch_state": result.source_batch.state,
        }
        return Response(data)

    @action(detail=True, methods=["get"])
    def timeline(self, request, pk=None):
        """GET /api/slaughter/shifts/{id}/timeline/"""
        shift = self.get_object()
        events = get_shift_timeline(shift)
        counts: dict[str, int] = {}
        for ev in events:
            counts[ev["type"]] = counts.get(ev["type"], 0) + 1
        return Response({"events": events, "counts": counts})

    @action(detail=True, methods=["get"])
    def stats(self, request, pk=None):
        """GET /api/slaughter/shifts/{id}/stats/ — KPI смены + breakdown по SKU."""
        shift = self.get_object()
        kpi = get_shift_kpi(shift)
        return Response(
            {
                "shift_id": str(shift.id),
                "live_heads": shift.live_heads_received,
                "live_weight_kg": str(shift.live_weight_kg_total),
                "total_output_kg": str(kpi.total_output_kg),
                "total_output_pct": (
                    str(kpi.total_output_pct)
                    if kpi.total_output_pct is not None
                    else None
                ),
                "waste_kg": (
                    str(kpi.waste_kg) if kpi.waste_kg is not None else None
                ),
                "waste_pct": (
                    str(kpi.waste_pct) if kpi.waste_pct is not None else None
                ),
                "carcass_kg": str(kpi.carcass_kg),
                "carcass_yield_pct": (
                    str(kpi.carcass_yield_pct)
                    if kpi.carcass_yield_pct is not None
                    else None
                ),
                "yield_per_head_kg": (
                    str(kpi.yield_per_head_kg)
                    if kpi.yield_per_head_kg is not None
                    else None
                ),
                "defect_rate": (
                    str(kpi.defect_rate) if kpi.defect_rate is not None else None
                ),
                "quality_checked": kpi.quality_checked,
                "yields_count": kpi.yields_count,
                "lab_pending_count": kpi.lab_pending_count,
                "lab_passed_count": kpi.lab_passed_count,
                "lab_failed_count": kpi.lab_failed_count,
                "breakdown": [
                    {
                        "sku": row.sku,
                        "name": row.name,
                        "quantity_kg": str(row.quantity_kg),
                        "yield_pct": (
                            str(row.yield_pct) if row.yield_pct is not None else None
                        ),
                        "norm_pct": (
                            str(row.norm_pct) if row.norm_pct is not None else None
                        ),
                        "deviation_pct": (
                            str(row.deviation_pct)
                            if row.deviation_pct is not None
                            else None
                        ),
                        "is_within_tolerance": row.is_within_tolerance,
                    }
                    for row in kpi.breakdown
                ],
            }
        )

    @action(detail=True, methods=["post"], url_path="bulk-yields")
    def bulk_yields(self, request, pk=None):
        """POST /api/slaughter/shifts/{id}/bulk-yields/

        Body: {
            "yields": [
                {"nomenclature": "uuid", "quantity": "412.5", "share_percent": "25.0", "notes": ""},
                ...
            ],
            "replace_existing": true|false  # default false: добавляет к существующим
        }

        Если `replace_existing=true` — все существующие SlaughterYield с unit=kg
        для этой смены удаляются перед созданием новых (только для shifts в ACTIVE/CLOSED).
        Атомарно: все выходы создаются в одной транзакции.
        """
        from decimal import Decimal

        from django.db import transaction
        from rest_framework.exceptions import ValidationError as DRFValidationError

        from apps.nomenclature.models import NomenclatureItem, Unit

        from .models import SlaughterYield
        from .services.stats import KG_CODES

        shift = self.get_object()
        if shift.status not in (
            SlaughterShift.Status.ACTIVE,
            SlaughterShift.Status.CLOSED,
        ):
            raise DRFValidationError(
                {"status": f"Нельзя редактировать выходы в статусе {shift.get_status_display()}."}
            )

        rows = request.data.get("yields") or []
        replace_existing = bool(request.data.get("replace_existing", False))
        if not isinstance(rows, list) or not rows:
            raise DRFValidationError({"yields": "Массив выходов обязателен."})

        # Резолвим единицу kg для организации (или кг)
        kg_unit = (
            Unit.objects.filter(organization=shift.organization)
            .filter(code__iregex=r"^(kg|кг)$")
            .first()
        )
        if kg_unit is None:
            raise DRFValidationError(
                {"unit": "В организации нет единицы измерения 'kg'/'кг'."}
            )

        # Валидация перед записью
        prepared = []
        for i, row in enumerate(rows):
            nom_id = row.get("nomenclature")
            qty_raw = row.get("quantity")
            if not nom_id:
                raise DRFValidationError(
                    {f"yields[{i}].nomenclature": "Обязательно."}
                )
            try:
                qty = Decimal(str(qty_raw))
            except Exception:
                raise DRFValidationError(
                    {f"yields[{i}].quantity": f"Неверное число: {qty_raw}"}
                )
            if qty <= 0:
                raise DRFValidationError(
                    {f"yields[{i}].quantity": "Должно быть > 0."}
                )
            try:
                nom = NomenclatureItem.objects.get(
                    id=nom_id, organization=shift.organization
                )
            except NomenclatureItem.DoesNotExist:
                raise DRFValidationError(
                    {f"yields[{i}].nomenclature": "Не найдена."}
                )
            share = row.get("share_percent")
            if share not in (None, ""):
                try:
                    share = Decimal(str(share))
                except Exception:
                    raise DRFValidationError(
                        {f"yields[{i}].share_percent": f"Неверное число: {share}"}
                    )
            else:
                share = None
            prepared.append({
                "nomenclature": nom,
                "quantity": qty,
                "share_percent": share,
                "notes": row.get("notes", "") or "",
            })

        # Сумма выходов не должна превышать живой вес
        live_kg = shift.live_weight_kg_total or Decimal("0")
        new_total = sum((p["quantity"] for p in prepared), Decimal("0"))

        with transaction.atomic():
            existing_qs = (
                SlaughterYield.objects.filter(shift=shift)
                .select_related("unit")
            )
            if replace_existing:
                # Удаляем только kg-выходы
                kg_existing = [
                    y for y in existing_qs
                    if y.unit and y.unit.code.lower() in KG_CODES
                ]
                for y in kg_existing:
                    y.delete()
                existing_kg = Decimal("0")
            else:
                existing_kg = sum(
                    (
                        y.quantity
                        for y in existing_qs
                        if y.unit and y.unit.code.lower() in KG_CODES
                    ),
                    Decimal("0"),
                )

            if live_kg > 0 and existing_kg + new_total > live_kg:
                raise DRFValidationError({
                    "yields": (
                        f"Сумма выходов {existing_kg + new_total} кг превысит "
                        f"живой вес {live_kg} кг. Доступно для добавления: "
                        f"{max(live_kg - existing_kg, Decimal('0'))} кг."
                    )
                })

            created = []
            for p in prepared:
                # Уникальность (shift, nomenclature) — если запись есть, обновляем quantity
                existing = SlaughterYield.objects.filter(
                    shift=shift, nomenclature=p["nomenclature"]
                ).first()
                if existing:
                    existing.quantity = p["quantity"]
                    existing.unit = kg_unit
                    existing.share_percent = p["share_percent"]
                    existing.notes = p["notes"]
                    existing.save()
                    created.append(existing)
                else:
                    y = SlaughterYield.objects.create(
                        shift=shift,
                        nomenclature=p["nomenclature"],
                        unit=kg_unit,
                        quantity=p["quantity"],
                        share_percent=p["share_percent"],
                        notes=p["notes"],
                    )
                    created.append(y)

        # Возвращаем shift с обновлёнными KPI
        shift.refresh_from_db()
        data = self.get_serializer(shift).data
        data["_result"] = {
            "yields_created": len(created),
            "total_kg": str(new_total),
        }
        return Response(data)

    @action(detail=False, methods=["get"])
    def incoming(self, request):
        """GET /api/slaughter/shifts/incoming/

        Список межмодульных транзферов в slaughter, ожидающих приёма.
        """
        from apps.transfers.models import InterModuleTransfer
        from apps.transfers.serializers import InterModuleTransferSerializer

        org = getattr(request, "organization", None)
        if org is None:
            return Response([])

        qs = (
            InterModuleTransfer.objects.filter(
                organization=org,
                to_module__code="slaughter",
                state__in=[
                    InterModuleTransfer.State.AWAITING_ACCEPTANCE,
                    InterModuleTransfer.State.UNDER_REVIEW,
                ],
            )
            .select_related(
                "from_module",
                "to_module",
                "from_block",
                "to_block",
                "from_warehouse",
                "to_warehouse",
                "nomenclature",
                "unit",
                "batch",
            )
            .order_by("-transfer_date")
        )
        data = InterModuleTransferSerializer(qs, many=True).data
        return Response(data)

    @action(detail=True, methods=["post"])
    def reverse(self, request, pk=None):
        """POST /api/slaughter/shifts/{id}/reverse/
        Body: {"reason": str (optional)}
        """
        shift = self.get_object()
        try:
            result = reverse_slaughter_shift(
                shift,
                reason=request.data.get("reason", ""),
                user=request.user,
            )
        except SlaughterReverseError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        shift.refresh_from_db()
        data = self.get_serializer(shift).data
        data["_result"] = {
            "reverse_movements_count": len(result.reverse_movements),
            "reverse_journals": [
                {"id": str(je.id), "doc_number": je.doc_number}
                for je in result.reverse_journals
            ],
            "source_batch_state": result.source_batch.state,
        }
        return Response(data)


class _ChildOfShiftMixin:
    """
    Mixin для дочерних моделей SlaughterShift — переопределяет _save_kwargs_for_create,
    чтобы не передавать `shift__organization=...` в `Model.objects.create()`
    (организация наследуется через FK на shift).
    """

    def _save_kwargs_for_create(self, serializer) -> dict:
        kwargs: dict = {}
        model = serializer.Meta.model if hasattr(serializer, "Meta") else None
        if model is not None:
            field_names = {f.name for f in model._meta.get_fields()}
            if "created_by" in field_names:
                user = getattr(self.request, "user", None)
                if user and getattr(user, "is_authenticated", False):
                    kwargs["created_by"] = user
        return kwargs


class SlaughterYieldViewSet(DeleteReasonMixin, _ChildOfShiftMixin, OrgScopedModelViewSet):
    serializer_class = SlaughterYieldSerializer
    queryset = SlaughterYield.objects.select_related(
        "shift", "nomenclature", "unit", "output_batch"
    )
    module_code = "slaughter"
    organization_field = "shift__organization"
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["shift", "nomenclature"]


class SlaughterQualityCheckViewSet(DeleteReasonMixin, _ChildOfShiftMixin, OrgScopedModelViewSet):
    serializer_class = SlaughterQualityCheckSerializer
    queryset = SlaughterQualityCheck.objects.select_related("shift", "inspector")
    module_code = "slaughter"
    organization_field = "shift__organization"
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["shift", "vet_inspection_passed"]


class SlaughterLabTestViewSet(DeleteReasonMixin, _ChildOfShiftMixin, OrgScopedModelViewSet):
    serializer_class = SlaughterLabTestSerializer
    queryset = SlaughterLabTest.objects.select_related("shift", "operator")
    module_code = "slaughter"
    organization_field = "shift__organization"
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["shift", "status"]
