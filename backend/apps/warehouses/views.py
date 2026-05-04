from decimal import Decimal

from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status as http_status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.batches.models import Batch
from apps.common.permissions import HasModulePermission
from apps.common.viewsets import OrganizationScopedMixin, OrgScopedModelViewSet
from apps.counterparties.models import Counterparty
from apps.modules.models import Module
from apps.nomenclature.models import NomenclatureItem

from .filters import ProductionBlockFilter, StockMovementFilter, WarehouseFilter
from .models import ProductionBlock, StockMovement, Warehouse
from .serializers import (
    ProductionBlockSerializer,
    StockMovementManualCreateSerializer,
    StockMovementSerializer,
    WarehouseSerializer,
)
from .services.create import (
    StockMovementCreateError,
    create_manual_movement,
    delete_manual_movement,
    is_manual_movement,
)


class ProductionBlockViewSet(OrgScopedModelViewSet):
    """
    /api/warehouses/blocks/ — производственные блоки (корпуса, шкафы,
    птичники, линии, бункеры и т.д.).
    """

    serializer_class = ProductionBlockSerializer
    queryset = ProductionBlock.objects.select_related("module", "capacity_unit")
    module_code = "core"
    required_level = "r"
    write_level = "rw"

    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ProductionBlockFilter
    ordering_fields = ["code", "kind", "created_at"]
    ordering = ["code"]


class WarehouseViewSet(OrgScopedModelViewSet):
    """
    /api/warehouses/warehouses/ — склады (логические).
    Полный CRUD: create / retrieve / update / partial_update / destroy.
    """

    serializer_class = WarehouseSerializer
    queryset = Warehouse.objects.select_related(
        "module", "production_block", "default_gl_subaccount"
    )
    module_code = "stock"
    required_level = "r"
    write_level = "rw"

    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = WarehouseFilter
    ordering_fields = ["code", "created_at"]
    ordering = ["code"]


class StockMovementViewSet(
    OrganizationScopedMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    /api/warehouses/movements/ — журнал движений по складу.

    По умолчанию read-only — большинство движений создаются как
    побочный эффект сервисов (`confirm_purchase`, `accept_transfer` и т.п.)
    и иммутабельны.

    Для ручных операций (инвентаризация, прямой приход без закупа,
    бытовое списание) предусмотрены два action'а:

      POST /api/warehouses/movements/manual/      — ручное создание
      DELETE /api/warehouses/movements/{id}/      — удаление manual-only

    Удаление сервисных движений (с source_content_type) запрещено —
    их нужно сторнировать через reverse-сервис исходного документа.
    """

    serializer_class = StockMovementSerializer
    queryset = StockMovement.objects.select_related(
        "module",
        "nomenclature",
        "warehouse_from",
        "warehouse_to",
        "counterparty",
        "batch",
    )
    permission_classes = [IsAuthenticated, HasModulePermission]
    module_code = "stock"
    required_level = "r"
    write_level = "rw"

    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = StockMovementFilter
    ordering_fields = ["date", "doc_number", "amount_uzs"]
    ordering = ["-date"]

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """
        GET /api/warehouses/movements/stats/

        Агрегированная статистика по движениям с теми же фильтрами что у list.
        Возвращает суммы по UZS и счётчики по каждому виду движения.

        Query params (наследуются из StockMovementFilter):
          ?date_after=&date_before=&module_code=&kind=&warehouse_from=...
        """
        qs = self.filter_queryset(self.get_queryset())

        agg = (
            qs.values("kind")
            .annotate(total_uzs=Sum("amount_uzs"), count=Count("id"))
        )

        result = {
            "total_count": qs.count(),
            "total_amount_uzs": str(qs.aggregate(s=Sum("amount_uzs"))["s"] or Decimal("0")),
            "by_kind": {
                "incoming": {"count": 0, "amount_uzs": "0"},
                "outgoing": {"count": 0, "amount_uzs": "0"},
                "transfer": {"count": 0, "amount_uzs": "0"},
                "write_off": {"count": 0, "amount_uzs": "0"},
            },
        }
        for row in agg:
            kind = row["kind"]
            if kind in result["by_kind"]:
                result["by_kind"][kind] = {
                    "count": row["count"],
                    "amount_uzs": str(row["total_uzs"] or Decimal("0")),
                }
        return Response(result)

    @action(detail=False, methods=["post"], url_path="manual")
    def manual_create(self, request):
        """
        POST /api/warehouses/movements/manual/

        Body: {
          module: <uuid>,
          kind: incoming|outgoing|transfer|write_off,
          nomenclature: <uuid>,
          quantity: "...",
          unit_price_uzs: "...",
          warehouse_from?: <uuid>,
          warehouse_to?: <uuid>,
          counterparty?: <uuid>,
          batch?: <uuid>,
          date?: "ISO datetime"
        }
        """
        serializer = StockMovementManualCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        org = request.organization

        try:
            module = Module.objects.get(pk=data["module"])
        except Module.DoesNotExist:
            raise DRFValidationError({"module": "Модуль не найден."})

        nomenclature = get_object_or_404(
            NomenclatureItem, pk=data["nomenclature"], organization=org
        )

        wh_from = None
        if data.get("warehouse_from"):
            wh_from = get_object_or_404(
                Warehouse, pk=data["warehouse_from"], organization=org
            )

        wh_to = None
        if data.get("warehouse_to"):
            wh_to = get_object_or_404(
                Warehouse, pk=data["warehouse_to"], organization=org
            )

        counterparty = None
        if data.get("counterparty"):
            counterparty = get_object_or_404(
                Counterparty, pk=data["counterparty"], organization=org
            )

        batch = None
        if data.get("batch"):
            batch = get_object_or_404(Batch, pk=data["batch"], organization=org)

        try:
            result = create_manual_movement(
                organization=org,
                module=module,
                kind=data["kind"],
                nomenclature=nomenclature,
                quantity=data["quantity"],
                unit_price_uzs=data["unit_price_uzs"],
                warehouse_from=wh_from,
                warehouse_to=wh_to,
                counterparty=counterparty,
                batch=batch,
                date_value=data.get("date"),
                user=request.user,
            )
        except StockMovementCreateError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )

        out = StockMovementSerializer(result.movement).data
        return Response(out, status=http_status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        """
        DELETE /api/warehouses/movements/{id}/

        Разрешено ТОЛЬКО для ручных движений (без source_content_type).
        Системные движения (созданные confirm_purchase и т.п.) удалять
        нельзя — нужно сторнировать исходный документ.
        """
        movement = self.get_object()
        if not is_manual_movement(movement):
            raise DRFValidationError(
                {
                    "__all__": (
                        "Это движение создано автоматически по документу-источнику. "
                        "Удаление возможно только через сторно исходного документа."
                    )
                }
            )
        try:
            delete_manual_movement(movement, user=request.user)
        except StockMovementCreateError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        return Response(status=http_status.HTTP_204_NO_CONTENT)
