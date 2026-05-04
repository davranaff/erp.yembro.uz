from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.common.viewsets import OrgScopedModelViewSet

from .models import InterModuleTransfer
from .serializers import InterModuleTransferSerializer
from .services.accept import (
    TransferAcceptError,
    accept_transfer,
    cancel_transfer,
    review_transfer,
    submit_transfer,
)


class InterModuleTransferViewSet(OrgScopedModelViewSet):
    """
    /api/transfers/ — межмодульные передачи.

    Жизненный цикл:
        POST /api/transfers/               → draft
        POST /api/transfers/{id}/submit/    → draft → awaiting_acceptance
        POST /api/transfers/{id}/accept/    → awaiting/review → posted (atomic)
        POST /api/transfers/{id}/review/    → awaiting → under_review (с reason)
        POST /api/transfers/{id}/cancel/    → любой кроме posted → cancelled
    """

    serializer_class = InterModuleTransferSerializer
    queryset = InterModuleTransfer.objects.select_related(
        "from_module",
        "to_module",
        "from_block",
        "to_block",
        "from_warehouse",
        "to_warehouse",
        "nomenclature",
        "unit",
        "batch",
        "feed_batch",
        "journal_sender",
        "journal_receiver",
    )

    module_code = "stock"
    required_level = "r"
    write_level = "rw"

    def get_permissions(self):
        # `incoming` — это inbox конкретного модуля; гейт делается внутри
        # action на уровне `to_module` (см. ниже). Не требуем stock-доступ,
        # иначе feedlot.r-пользователь без stock не увидит свой inbox.
        if getattr(self, "action", None) == "incoming":
            from rest_framework.permissions import IsAuthenticated
            return [IsAuthenticated()]
        return super().get_permissions()

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        "state",
        "from_module",
        "to_module",
        "batch",
        "feed_batch",
    ]
    search_fields = ["doc_number", "notes"]
    ordering_fields = ["transfer_date", "doc_number"]
    ordering = ["-transfer_date"]

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        """DRAFT → AWAITING_ACCEPTANCE."""
        try:
            transfer = submit_transfer(self.get_object(), user=request.user)
        except TransferAcceptError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        return Response(self.get_serializer(transfer).data)

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        """AWAITING → UNDER_REVIEW (с причиной)."""
        reason = request.data.get("reason", "")
        try:
            transfer = review_transfer(self.get_object(), user=request.user, reason=reason)
        except TransferAcceptError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        return Response(self.get_serializer(transfer).data)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        """AWAITING/UNDER_REVIEW → POSTED (atomic, создаёт JE + SM + chain step).

        Body (опционально):
            {
                "to_warehouse_id": "<uuid>",   # склад приёмки
                "to_block_id": "<uuid>"        # блок (опционально)
            }

        Эти поля переписывают `transfer.to_warehouse` / `to_block` ДО
        проводки. Это нужно когда отправитель не знал, на какой склад
        receiver хочет принять — выбор делает оператор-приёмщик в момент
        accept. После проводки accept_transfer проверит что to_warehouse
        задан (см. apps/transfers/services/accept.py — guard).

        Валидация: warehouse/block должны принадлежать `to_module`
        transfer-а и той же организации (то же что в Transfer.clean()).
        """
        from apps.warehouses.models import ProductionBlock, Warehouse

        transfer = self.get_object()
        wh_id = request.data.get("to_warehouse_id")
        block_id = request.data.get("to_block_id")
        updates: list[str] = []

        if wh_id:
            try:
                wh = Warehouse.objects.get(
                    id=wh_id,
                    organization=transfer.organization,
                    module=transfer.to_module,
                )
            except Warehouse.DoesNotExist:
                raise DRFValidationError({
                    "to_warehouse_id": (
                        "Склад не найден или не принадлежит модулю-приёмнику."
                    ),
                })
            transfer.to_warehouse = wh
            updates.append("to_warehouse")

        if block_id:
            try:
                block = ProductionBlock.objects.get(
                    id=block_id,
                    organization=transfer.organization,
                    module=transfer.to_module,
                )
            except ProductionBlock.DoesNotExist:
                raise DRFValidationError({
                    "to_block_id": (
                        "Блок не найден или не принадлежит модулю-приёмнику."
                    ),
                })
            transfer.to_block = block
            updates.append("to_block")

        if updates:
            transfer.save(update_fields=updates + ["updated_at"])

        try:
            result = accept_transfer(transfer, user=request.user)
        except TransferAcceptError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        result.transfer.refresh_from_db()
        data = self.get_serializer(result.transfer).data
        data["_result"] = {
            "journal_sender": {
                "id": str(result.journal_sender.id),
                "doc_number": result.journal_sender.doc_number,
            },
            "journal_receiver": {
                "id": str(result.journal_receiver.id),
                "doc_number": result.journal_receiver.doc_number,
            },
            "stock_outgoing": {
                "id": str(result.stock_outgoing.id),
                "doc_number": result.stock_outgoing.doc_number,
            },
            "stock_incoming": {
                "id": str(result.stock_incoming.id),
                "doc_number": result.stock_incoming.doc_number,
            },
            "affected_batches": [
                {
                    "id": str(b.id),
                    "doc_number": b.doc_number,
                    "current_module": b.current_module.code if b.current_module_id else None,
                    "accumulated_cost_uzs": str(b.accumulated_cost_uzs),
                    "withdrawal_period_ends": (
                        b.withdrawal_period_ends.isoformat()
                        if b.withdrawal_period_ends
                        else None
                    ),
                }
                for b in result.affected_batches
            ],
        }
        return Response(data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        reason = request.data.get("reason", "")
        try:
            transfer = cancel_transfer(self.get_object(), user=request.user, reason=reason)
        except TransferAcceptError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        return Response(self.get_serializer(transfer).data)

    @action(detail=False, methods=["get"], url_path="incoming")
    def incoming(self, request):
        """GET /api/transfers/incoming/?to_module=<code>

        Универсальный endpoint для UI «Входящие партии» в любом модуле.
        Возвращает transfer'ы с `to_module=<code>` в состояниях
        AWAITING_ACCEPTANCE / UNDER_REVIEW (требуют действия пользователя).

        RBAC:
          - юзер должен иметь `r`-доступ к запрошенному `to_module`
            (иначе 403). Это разрешает feedlot.r видеть свой incoming
            без необходимости иметь stock-доступ.
          - без `to_module` параметра возвращаем все incoming-транзферы по
            всем модулям, к которым у юзера есть доступ (универсальный
            inbox).
        """
        from apps.common.permissions import _effective_level, level_satisfies
        from apps.modules.models import Module
        from rest_framework.exceptions import PermissionDenied

        org = getattr(request, "organization", None)
        membership = getattr(request, "membership", None)
        if org is None or membership is None:
            return Response([])

        to_module_code = request.query_params.get("to_module", "").strip()

        qs = InterModuleTransfer.objects.filter(
            organization=org,
            state__in=[
                InterModuleTransfer.State.AWAITING_ACCEPTANCE,
                InterModuleTransfer.State.UNDER_REVIEW,
            ],
        )

        if to_module_code:
            # Точечный запрос: проверяем что у юзера есть r-доступ к этому модулю.
            if not level_satisfies(_effective_level(membership, to_module_code), "r"):
                raise PermissionDenied({
                    "detail": f"Нет доступа к модулю '{to_module_code}'.",
                })
            qs = qs.filter(to_module__code=to_module_code)
        else:
            # Без фильтра — отдаём только те модули, к которым у юзера r+.
            allowed_codes = [
                code for code in Module.objects.values_list("code", flat=True)
                if level_satisfies(_effective_level(membership, code), "r")
            ]
            qs = qs.filter(to_module__code__in=allowed_codes)

        qs = qs.select_related(
            "from_module", "to_module",
            "from_block", "to_block",
            "from_warehouse", "to_warehouse",
            "nomenclature", "unit", "batch",
        ).order_by("-transfer_date")

        return Response(self.get_serializer(qs, many=True).data)
