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
    update_manual_movement,
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

    @action(detail=True, methods=["get"], url_path="balance")
    def balance(self, request, pk=None):
        """
        GET /api/warehouses/warehouses/{id}/balance/

        Текущие остатки по этому складу: для каждой номенклатуры
        Σ(INCOMING) − Σ(OUTGOING + WRITE_OFF). Считаем по StockMovement,
        без отдельной таблицы остатков — для небольших объёмов это OK.

        Возвращает только SKU с положительным или ненулевым балансом.
        """
        from collections import defaultdict
        from decimal import Decimal
        from django.db.models import Q, Sum

        warehouse = self.get_object()

        movements = (
            StockMovement.objects
            .filter(
                organization=warehouse.organization,
            )
            .filter(Q(warehouse_from=warehouse) | Q(warehouse_to=warehouse))
            .values(
                "nomenclature_id",
                "nomenclature__sku",
                "nomenclature__name",
                "nomenclature__unit__code",
                "kind",
            )
            .annotate(
                in_qty=Sum("quantity", filter=Q(
                    warehouse_to=warehouse,
                    kind=StockMovement.Kind.INCOMING,
                )),
                in_amt=Sum("amount_uzs", filter=Q(
                    warehouse_to=warehouse,
                    kind=StockMovement.Kind.INCOMING,
                )),
                out_qty=Sum("quantity", filter=Q(
                    warehouse_from=warehouse,
                    kind__in=[
                        StockMovement.Kind.OUTGOING,
                        StockMovement.Kind.WRITE_OFF,
                    ],
                )),
                out_amt=Sum("amount_uzs", filter=Q(
                    warehouse_from=warehouse,
                    kind__in=[
                        StockMovement.Kind.OUTGOING,
                        StockMovement.Kind.WRITE_OFF,
                    ],
                )),
                xfer_in=Sum("quantity", filter=Q(
                    warehouse_to=warehouse,
                    kind=StockMovement.Kind.TRANSFER,
                )),
                xfer_out=Sum("quantity", filter=Q(
                    warehouse_from=warehouse,
                    kind=StockMovement.Kind.TRANSFER,
                )),
            )
        )

        # Агрегируем по nomenclature (groupby + values_kind дробит)
        agg: dict = defaultdict(lambda: {
            "in_qty": Decimal(0), "in_amt": Decimal(0),
            "out_qty": Decimal(0), "out_amt": Decimal(0),
            "xfer_in": Decimal(0), "xfer_out": Decimal(0),
            "sku": "", "name": "", "unit": "",
        })
        for row in movements:
            key = row["nomenclature_id"]
            a = agg[key]
            a["sku"] = row["nomenclature__sku"]
            a["name"] = row["nomenclature__name"]
            a["unit"] = row["nomenclature__unit__code"]
            for f in ("in_qty", "in_amt", "out_qty", "out_amt", "xfer_in", "xfer_out"):
                a[f] += row.get(f) or Decimal(0)

        rows = []
        for nom_id, a in agg.items():
            balance = (
                a["in_qty"] + a["xfer_in"] - a["out_qty"] - a["xfer_out"]
            )
            if balance == 0 and a["in_qty"] == 0 and a["out_qty"] == 0 and a["xfer_in"] == 0 and a["xfer_out"] == 0:
                continue
            rows.append({
                "nomenclature_id": str(nom_id),
                "sku": a["sku"],
                "name": a["name"],
                "unit": a["unit"],
                "incoming_qty": str(a["in_qty"]),
                "incoming_amount_uzs": str(a["in_amt"]),
                "outgoing_qty": str(a["out_qty"] + a["xfer_out"]),
                "outgoing_amount_uzs": str(a["out_amt"]),
                "balance_qty": str(balance),
            })

        # Сортируем: сначала с положительным остатком, потом нулевые/отрицательные
        rows.sort(key=lambda r: (
            -1 if Decimal(r["balance_qty"]) > 0 else (0 if Decimal(r["balance_qty"]) == 0 else 1),
            r["sku"],
        ))

        # Для vet-склада — добавляем детализацию по лотам у каждой строки
        # (lot_number, expiration_date, current_quantity на этом конкретном складе).
        # Лекарства физически идентифицируются лотом, не SKU — это критично для
        # отзыва (recall) и контроля сроков годности.
        is_vet = warehouse.module.code == "vet" if warehouse.module_id else False
        if is_vet:
            from apps.vet.models import VetStockBatch
            lots = (
                VetStockBatch.objects
                .filter(organization=warehouse.organization, warehouse=warehouse)
                .filter(current_quantity__gt=0)
                .exclude(status=VetStockBatch.Status.RECALLED)
                .select_related("drug", "drug__nomenclature")
                .order_by("expiration_date")
            )
            lots_by_nom: dict = defaultdict(list)
            for lot in lots:
                lots_by_nom[str(lot.drug.nomenclature_id)].append({
                    "id": str(lot.id),
                    "doc_number": lot.doc_number,
                    "lot_number": lot.lot_number,
                    "current_quantity": str(lot.current_quantity),
                    "expiration_date": (
                        lot.expiration_date.isoformat()
                        if lot.expiration_date else None
                    ),
                    "status": lot.status,
                })
            for r in rows:
                r["lots"] = lots_by_nom.get(r["nomenclature_id"], [])

        return Response({
            "warehouse": {
                "id": str(warehouse.id),
                "code": warehouse.code,
                "name": warehouse.name,
                "module_code": warehouse.module.code if warehouse.module_id else None,
            },
            "rows": rows,
            "summary": {
                "sku_count": len(rows),
                "with_balance": sum(1 for r in rows if Decimal(r["balance_qty"]) > 0),
            },
        })


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

    @action(detail=True, methods=["patch"], url_path="manual")
    def manual_update(self, request, pk=None):
        """
        PATCH /api/warehouses/movements/{id}/manual/

        Body (все поля опциональны):
          {
            "date": "ISO datetime",
            "counterparty": "<uuid>" | null,
            "batch": "<uuid>" | null
          }

        Разрешено ТОЛЬКО для ручных движений. quantity / unit_price /
        amount / kind / nomenclature / warehouse_* — иммутабельны (для
        изменения нужно delete + recreate, чтобы остатки пересчитались).
        """
        from datetime import datetime

        movement = self.get_object()
        org = request.organization

        date_value = None
        if "date" in request.data and request.data["date"]:
            raw = request.data["date"]
            try:
                date_value = (
                    raw if isinstance(raw, datetime)
                    else datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                )
            except ValueError:
                raise DRFValidationError(
                    {"date": "Некорректный формат даты (ожидаю ISO 8601)."}
                )

        counterparty = None
        clear_cp = False
        if "counterparty" in request.data:
            cp_id = request.data["counterparty"]
            if cp_id is None or cp_id == "":
                clear_cp = True
            else:
                counterparty = get_object_or_404(
                    Counterparty, pk=cp_id, organization=org
                )

        batch = None
        clear_batch = False
        if "batch" in request.data:
            b_id = request.data["batch"]
            if b_id is None or b_id == "":
                clear_batch = True
            else:
                batch = get_object_or_404(Batch, pk=b_id, organization=org)

        try:
            updated = update_manual_movement(
                movement,
                date_value=date_value,
                counterparty=counterparty,
                batch=batch,
                clear_counterparty=clear_cp,
                clear_batch=clear_batch,
                user=request.user,
            )
        except StockMovementCreateError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )

        return Response(StockMovementSerializer(updated).data)

    @action(detail=True, methods=["post"], url_path="promote-to-raw-batch")
    def promote_to_raw_batch(self, request, pk=None):
        """
        POST /api/warehouses/movements/{id}/promote-to-raw-batch/

        Превратить ручной INCOMING-движение в полноценную партию сырья
        (RawMaterialBatch) модуля «Корма». Существующее движение
        перепривязывается к новой партии — без дублирования в журнале.

        Body (опц.):
          {
            "moisture_pct_actual": "18.0",
            "dockage_pct_actual": "1.5",
            "shrinkage_pct": "5.0",
            "quarantine_until": "YYYY-MM-DD",
            "supplier": "<uuid>",
            "storage_bin": "БК-3",
            "notes": "..."
          }
        """
        from datetime import date as dt_date
        from decimal import Decimal, InvalidOperation

        from apps.feed.services.raw_batch_stock import (
            RawBatchPromoteError,
            promote_movement_to_raw_batch,
        )

        movement = self.get_object()
        org = request.organization

        def _decimal(key):
            v = request.data.get(key)
            if v is None or v == "":
                return None
            try:
                return Decimal(str(v))
            except (InvalidOperation, TypeError):
                raise DRFValidationError({key: "Некорректное число."})

        quarantine = None
        if request.data.get("quarantine_until"):
            try:
                quarantine = dt_date.fromisoformat(str(request.data["quarantine_until"]))
            except ValueError:
                raise DRFValidationError(
                    {"quarantine_until": "Ожидаю дату YYYY-MM-DD."}
                )

        supplier = None
        if request.data.get("supplier"):
            supplier = get_object_or_404(
                Counterparty, pk=request.data["supplier"], organization=org
            )

        try:
            batch = promote_movement_to_raw_batch(
                movement,
                moisture_pct_actual=_decimal("moisture_pct_actual"),
                dockage_pct_actual=_decimal("dockage_pct_actual"),
                shrinkage_pct=_decimal("shrinkage_pct"),
                quarantine_until=quarantine,
                supplier=supplier,
                storage_bin=request.data.get("storage_bin", "") or "",
                notes=request.data.get("notes", "") or "",
                user=request.user,
            )
        except RawBatchPromoteError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )

        movement.refresh_from_db()
        return Response(
            {
                "movement": StockMovementSerializer(movement).data,
                "raw_batch": {
                    "id": str(batch.id),
                    "doc_number": batch.doc_number,
                    "status": batch.status,
                    "quantity": str(batch.quantity),
                },
            },
            status=http_status.HTTP_201_CREATED,
        )

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
