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
        """AWAITING/UNDER_REVIEW → POSTED (atomic, создаёт JE + SM + chain step)."""
        try:
            result = accept_transfer(self.get_object(), user=request.user)
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
