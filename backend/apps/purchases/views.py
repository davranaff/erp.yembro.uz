from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.common.lifecycle import DeleteReasonMixin, ImmutableStatusMixin
from apps.common.services.numbering import next_doc_number
from apps.common.viewsets import OrgScopedModelViewSet

from .filters import PurchaseOrderFilter
from .models import PurchaseAttachment, PurchaseOrder
from .serializers import (
    PurchaseAttachmentSerializer,
    PurchaseOrderSerializer,
)
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
    filterset_class = PurchaseOrderFilter
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

        # TG-уведомление о проведённом закупе — админ организации + head purchases.
        try:
            from apps.tgbot.services.orchestration import notify_purchase_event
            notify_purchase_event(order)
        except Exception:
            pass

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

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        """GET /api/purchases/orders/{id}/summary/ — детальная страница."""
        from decimal import Decimal as _D

        from django.contrib.contenttypes.models import ContentType

        from apps.common.services.document_timeline import (
            build_document_timeline,
            get_payment_events_for_order,
        )
        from apps.payments.models import PaymentAllocation

        from .models import PurchaseOrder

        order = self.get_object()

        # Items
        items = []
        for it in order.items.select_related("nomenclature").all():
            items.append({
                "id": str(it.id),
                "nomenclature_id": str(it.nomenclature_id) if it.nomenclature_id else None,
                "nomenclature_name": (
                    it.nomenclature.name if it.nomenclature_id else None
                ),
                "quantity": str(it.quantity),
                "unit_price_uzs": str(it.unit_price_uzs)
                if it.unit_price_uzs is not None else None,
                "line_total_uzs": str(it.line_total_uzs or 0),
            })

        # Allocated payments
        ct = ContentType.objects.get_for_model(PurchaseOrder)
        alloc_qs = (
            PaymentAllocation.objects.filter(
                target_content_type=ct, target_object_id=order.id,
            )
            .select_related("payment", "payment__currency")
            .order_by("-payment__date")
        )
        payments = []
        for a in alloc_qs:
            p = a.payment
            payments.append({
                "id": str(p.id),
                "allocation_id": str(a.id),
                "doc_number": p.doc_number,
                "date": p.date.isoformat(),
                "direction": p.direction,
                "channel": p.channel,
                "kind": p.kind,
                "status": p.status,
                "amount_uzs": str(a.amount_uzs),
                "payment_amount_uzs": str(p.amount_uzs),
                "currency_code": p.currency.code if p.currency_id else None,
                "notes": a.notes or p.notes or "",
            })

        # Attachments
        attachments = [
            {
                "id": str(att.id),
                "file": att.file.url if att.file else None,
                "name": getattr(att, "name", "") or "",
                "uploaded_at": att.created_at.isoformat() if hasattr(att, "created_at") else None,
            }
            for att in order.attachments.all()
        ] if hasattr(order, "attachments") else []

        # Timeline
        events = build_document_timeline(
            order, extra_events=get_payment_events_for_order(order),
        )

        amount = _D(order.amount_uzs or 0)
        paid = _D(order.paid_amount_uzs or 0)

        return Response({
            "order": {
                "id": str(order.id),
                "doc_number": order.doc_number,
                "date": order.date.isoformat(),
                "due_date": order.due_date.isoformat() if order.due_date else None,
                "status": order.status,
                "payment_status": getattr(order, "payment_status", None),
                "amount_uzs": str(amount),
                "paid_amount_uzs": str(paid),
                "outstanding_uzs": str(amount - paid),
                "currency_code": order.currency.code if order.currency_id else None,
                "amount_foreign": str(order.amount_foreign)
                if order.amount_foreign is not None else None,
                "exchange_rate": str(order.exchange_rate)
                if order.exchange_rate is not None else None,
                "notes": order.notes or "",
                "counterparty_id": str(order.counterparty_id)
                if order.counterparty_id else None,
                "counterparty_name": order.counterparty.name
                if order.counterparty_id else None,
                "counterparty_code": order.counterparty.code
                if order.counterparty_id else None,
                "warehouse_name": order.warehouse.name
                if order.warehouse_id else None,
                "module_code": order.module.code if order.module_id else None,
            },
            "items": items,
            "payments": payments,
            "attachments": attachments,
            "timeline": events,
        })


class PurchaseAttachmentViewSet(OrgScopedModelViewSet):
    """
    /api/purchases/attachments/ — файл-приложения к закупам.

    GET /?purchase=<uuid> — список файлов конкретного закупа.
    POST (multipart/form-data) — загрузить файл (поля: purchase, file,
        description?). uploaded_by, original_name, size_bytes,
        content_type заполняются автоматически.
    DELETE /{id}/ — удалить файл (включая физический файл с диска).
    Лимит 50МБ, валидируется в serializer + model.clean().
    """

    serializer_class = PurchaseAttachmentSerializer
    queryset = PurchaseAttachment.objects.select_related("purchase", "uploaded_by")
    organization_field = "purchase__organization"

    module_code = "purchases"
    required_level = "r"
    write_level = "rw"

    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["purchase"]
    ordering = ["-created_at"]

    # Multipart парсер для file-uploads. JSONParser оставляем — без него
    # PATCH/PUT description без файла отдают 415.
    from rest_framework.parsers import (  # noqa: E402
        FormParser,
        JSONParser,
        MultiPartParser,
    )
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def perform_create(self, serializer):
        from apps.audit.models import AuditLog
        from rest_framework.exceptions import PermissionDenied

        org = getattr(self.request, "organization", None)
        purchase = serializer.validated_data.get("purchase")
        if purchase is not None and org is not None and purchase.organization_id != org.id:
            raise PermissionDenied(
                {"purchase": "Закуп из другой организации."}
            )

        f = serializer.validated_data["file"]
        instance = serializer.save(
            uploaded_by=self.request.user,
            original_name=f.name,
            size_bytes=f.size,
            content_type=getattr(f, "content_type", "") or "",
        )
        # Дополнительная защита через model.clean() — на случай обхода
        # serializer-level валидации.
        instance.full_clean()
        self._write_audit(AuditLog.Action.CREATE, instance)

    def perform_destroy(self, instance):
        from apps.audit.models import AuditLog

        # Удаляем физический файл с диска перед удалением записи.
        if instance.file:
            instance.file.delete(save=False)
        self._write_audit(AuditLog.Action.DELETE, instance)
        instance.delete()
