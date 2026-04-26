from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.common.lifecycle import DeleteReasonMixin, ImmutableStatusMixin
from apps.common.services.numbering import next_doc_number
from apps.common.viewsets import OrgScopedModelViewSet

from .models import PurchaseOrder
from .serializers import PurchaseOrderSerializer
from .services.confirm import PurchaseConfirmError, confirm_purchase
from .services.reverse import PurchaseReverseError, reverse_purchase


class PurchaseOrderViewSet(ImmutableStatusMixin, DeleteReasonMixin, OrgScopedModelViewSet):
    """
    /api/purchases/orders/ — закупы.

    Список/создание/правка/удаление черновика (DRAFT). Проведение —
    через `POST .../{id}/confirm/`.
    """

    serializer_class = PurchaseOrderSerializer
    queryset = PurchaseOrder.objects.select_related(
        "counterparty", "warehouse", "currency", "exchange_rate_source"
    ).prefetch_related("items")

    module_code = "purchases"
    required_level = "r"
    write_level = "rw"

    # После confirm/paid/cancel закуп иммутабелен. Для отмены — reverse-action.
    immutable_statuses = ("confirmed", "paid", "cancelled")
    status_field = "status"

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status", "payment_status", "counterparty", "currency"]
    search_fields = ["doc_number", "counterparty__name", "counterparty__code", "notes"]
    ordering_fields = ["date", "doc_number", "amount_uzs", "created_at"]
    ordering = ["-date"]

    def perform_create(self, serializer):
        """
        Генерируем doc_number сразу при create — иначе unique_together
        (organization, doc_number) ругается на повторную пустую строку.
        Префикс «ЗК» (закуп). Формат: ЗК-YYYY-NNNNN.
        """
        org = getattr(self.request, "organization", None)
        kwargs = self._save_kwargs_for_create(serializer)
        if org is not None and not serializer.validated_data.get("doc_number"):
            kwargs["doc_number"] = next_doc_number(
                PurchaseOrder,
                organization=org,
                prefix="ЗК",
                on_date=serializer.validated_data.get("date"),
            )
        instance = serializer.save(**kwargs)
        from apps.audit.models import AuditLog
        self._write_audit(AuditLog.Action.CREATE, instance)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        """
        POST /api/purchases/orders/{id}/confirm/
        Провести закуп (DRAFT → CONFIRMED) с FX-snapshot.
        """
        order = self.get_object()
        try:
            result = confirm_purchase(order, user=request.user)
        except PurchaseConfirmError as exc:
            raise DRFValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)

        order.refresh_from_db()
        data = self.get_serializer(order).data
        data["_result"] = {
            "stock_movement": {
                "id": str(result.stock_movement.id),
                "doc_number": result.stock_movement.doc_number,
            },
            "journal_entry": {
                "id": str(result.journal_entry.id),
                "doc_number": result.journal_entry.doc_number,
            },
            "rate_snapshot": str(result.rate_snapshot) if result.rate_snapshot else None,
        }
        return Response(data)

    @action(detail=True, methods=["post"])
    def reverse(self, request, pk=None):
        """POST /api/purchases/orders/{id}/reverse/ — сторно закупа."""
        order = self.get_object()
        reason = request.data.get("reason", "")
        try:
            result = reverse_purchase(order, reason=reason, user=request.user)
        except PurchaseReverseError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        order.refresh_from_db()
        data = self.get_serializer(order).data
        data["_result"] = {
            "reverse_journal": {
                "id": str(result.reverse_journal.id),
                "doc_number": result.reverse_journal.doc_number,
            },
            "reverse_movements_count": len(result.reverse_movements),
        }
        return Response(data)

    @action(detail=True, methods=["get"])
    def timeline(self, request, pk=None):
        """GET /api/purchases/orders/{id}/timeline/"""
        from apps.common.services.document_timeline import (
            build_document_timeline,
            get_payment_events_for_order,
        )

        order = self.get_object()
        events = build_document_timeline(
            order,
            extra_events=get_payment_events_for_order(order),
        )
        return Response({"events": events, "count": len(events)})
