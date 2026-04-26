from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.common.viewsets import OrgReadOnlyViewSet

from .models import Batch, BatchChainStep, BatchCostEntry
from .serializers import (
    BatchChainStepSerializer,
    BatchCostEntrySerializer,
    BatchSerializer,
)
from .services.close_batch import BatchCloseError, close_batch


class BatchViewSet(OrgReadOnlyViewSet):
    """/api/batches/ — партии (read-only)."""

    serializer_class = BatchSerializer
    queryset = Batch.objects.select_related(
        "nomenclature", "unit", "origin_module", "current_module",
        "current_block", "parent_batch",
    )
    module_code = "core"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        "state",
        "current_module",
        "origin_module",
        "nomenclature",
        "parent_batch",
    ]
    search_fields = ["doc_number", "notes", "nomenclature__sku", "nomenclature__name"]
    ordering_fields = ["started_at", "doc_number", "accumulated_cost_uzs"]
    ordering = ["-started_at"]

    @action(detail=True, methods=["get"], url_path="cost-entries")
    def cost_entries(self, request, pk=None):
        """GET /api/batches/{id}/cost-entries/ — затраты по партии."""
        batch = self.get_object()
        qs = BatchCostEntry.objects.filter(batch=batch).select_related("module").order_by(
            "-occurred_at"
        )
        return Response(BatchCostEntrySerializer(qs, many=True).data)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        """POST /api/batches/{id}/close/
        Body: {"force": bool (default false), "reason": str (optional)}
        """
        from datetime import date as date_type
        batch = self.get_object()
        d = request.data.get("closed_on")
        try:
            closed_on = date_type.fromisoformat(d) if d else None
        except ValueError as exc:
            raise DRFValidationError({"closed_on": str(exc)})
        try:
            close_batch(
                batch,
                closed_on=closed_on,
                force=bool(request.data.get("force", False)),
                reason=request.data.get("reason", ""),
                user=request.user,
            )
        except BatchCloseError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        batch.refresh_from_db()
        return Response(self.get_serializer(batch).data)

    @action(detail=True, methods=["get"], url_path="chain")
    def chain(self, request, pk=None):
        """GET /api/batches/{id}/chain/ — timeline перемещений партии."""
        batch = self.get_object()
        qs = (
            BatchChainStep.objects.filter(batch=batch)
            .select_related("module", "block", "transfer_in", "transfer_out")
            .order_by("sequence")
        )
        return Response(BatchChainStepSerializer(qs, many=True).data)

    @action(detail=True, methods=["post"], url_path="send-to-feedlot")
    def send_to_feedlot(self, request, pk=None):
        """
        POST /api/batches/{id}/send-to-feedlot/

        Создаёт InterModuleTransfer incubation→feedlot и сразу его проводит.
        Доступно только для партий из инкубации (origin_module=incubation).
        """
        from apps.incubation.services.send_to_feedlot import (
            SendToFeedlotError,
            send_chicks_to_feedlot,
        )

        batch = self.get_object()
        try:
            result = send_chicks_to_feedlot(batch, user=request.user)
        except SendToFeedlotError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )

        batch.refresh_from_db()
        data = self.get_serializer(batch).data
        data["_result"] = {
            "transfer_id": str(result.transfer.id),
            "transfer_doc_number": result.transfer.doc_number,
            "transfer_state": result.transfer.state,
            "current_module_code": (
                batch.current_module.code if batch.current_module_id else None
            ),
        }
        return Response(data)

    @action(detail=True, methods=["post"], url_path="send-to-incubation")
    def send_to_incubation(self, request, pk=None):
        """
        POST /api/batches/{id}/send-to-incubation/

        Создаёт InterModuleTransfer matochnik→incubation и сразу его проводит.
        Доступно только для партий из маточника (origin_module=matochnik).
        """
        from apps.matochnik.services.send_to_incubation import (
            SendToIncubationError,
            send_eggs_to_incubation,
        )

        batch = self.get_object()
        try:
            result = send_eggs_to_incubation(batch, user=request.user)
        except SendToIncubationError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )

        batch.refresh_from_db()
        data = self.get_serializer(batch).data
        data["_result"] = {
            "transfer_id": str(result.transfer.id),
            "transfer_doc_number": result.transfer.doc_number,
            "transfer_state": result.transfer.state,
            "current_module_code": (
                batch.current_module.code if batch.current_module_id else None
            ),
        }
        return Response(data)

    @action(detail=True, methods=["get"])
    def trace(self, request, pk=None):
        """
        GET /api/batches/{id}/trace/

        Сквозная трассировка партии:
            - сама партия (snapshot)
            - parent_batch (откуда родилась — например, egg_batch для chick_batch)
            - children — дочерние партии (output_batches убойни и т.п.)
            - chain_steps — timeline по модулям
            - cost_breakdown — затраты по категориям с долями
            - totals — сводка
        """
        from collections import OrderedDict
        from decimal import Decimal

        batch = self.get_object()

        # 1. Chain steps
        steps = list(
            BatchChainStep.objects.filter(batch=batch)
            .select_related("module", "block", "transfer_in", "transfer_out")
            .order_by("sequence")
        )

        # 2. Cost entries — группируем по категории
        cost_entries = list(
            BatchCostEntry.objects.filter(batch=batch)
            .select_related("module")
            .order_by("occurred_at")
        )
        by_category: dict = OrderedDict()
        total_cost = Decimal("0")
        for ce in cost_entries:
            by_category.setdefault(ce.category, Decimal("0"))
            by_category[ce.category] += ce.amount_uzs
            total_cost += ce.amount_uzs

        breakdown = []
        cat_labels = dict(BatchCostEntry.Category.choices)
        for cat, amt in by_category.items():
            share = (amt / total_cost * 100) if total_cost > 0 else Decimal("0")
            breakdown.append({
                "category": cat,
                "category_label": cat_labels.get(cat, cat),
                "amount_uzs": str(amt),
                "share_percent": str(share.quantize(Decimal("0.01"))),
            })

        # 3. Parent + children
        parent_data = None
        if batch.parent_batch_id:
            p = batch.parent_batch
            parent_data = {
                "id": str(p.id),
                "doc_number": p.doc_number,
                "nomenclature_sku": p.nomenclature.sku if p.nomenclature_id else None,
                "current_quantity": str(p.current_quantity),
                "accumulated_cost_uzs": str(p.accumulated_cost_uzs),
                "state": p.state,
            }

        children = []
        for c in Batch.objects.filter(parent_batch=batch).select_related(
            "nomenclature", "current_module"
        ):
            children.append({
                "id": str(c.id),
                "doc_number": c.doc_number,
                "nomenclature_sku": c.nomenclature.sku if c.nomenclature_id else None,
                "current_quantity": str(c.current_quantity),
                "accumulated_cost_uzs": str(c.accumulated_cost_uzs),
                "current_module": (
                    c.current_module.code if c.current_module_id else None
                ),
                "state": c.state,
            })

        # 4. Сводка
        unit_cost = (
            (batch.accumulated_cost_uzs / batch.initial_quantity)
            if batch.initial_quantity and batch.initial_quantity > 0
            else Decimal("0")
        )

        return Response({
            "batch": BatchSerializer(batch).data,
            "parent": parent_data,
            "children": children,
            "chain_steps": BatchChainStepSerializer(steps, many=True).data,
            "cost_breakdown": breakdown,
            "totals": {
                "total_cost_uzs": str(total_cost),
                "accumulated_cost_uzs": str(batch.accumulated_cost_uzs),
                "unit_cost_uzs": str(unit_cost.quantize(Decimal("0.01"))),
                "initial_quantity": str(batch.initial_quantity),
                "current_quantity": str(batch.current_quantity),
            },
        })


class BatchCostEntryViewSet(OrgReadOnlyViewSet):
    """/api/batch-cost-entries/ — глобальный список затрат."""

    serializer_class = BatchCostEntrySerializer
    queryset = BatchCostEntry.objects.select_related("batch", "module")
    module_code = "core"
    organization_field = "batch__organization"
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["batch", "category", "module"]
    ordering_fields = ["occurred_at", "amount_uzs"]
    ordering = ["-occurred_at"]


class BatchChainStepViewSet(OrgReadOnlyViewSet):
    """/api/batch-chain-steps/ — глобальный список шагов чейна."""

    serializer_class = BatchChainStepSerializer
    queryset = BatchChainStep.objects.select_related(
        "batch", "module", "block", "transfer_in", "transfer_out"
    )
    module_code = "core"
    organization_field = "batch__organization"
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["batch", "module", "block"]
    ordering_fields = ["batch", "sequence", "entered_at"]
    ordering = ["batch", "sequence"]
