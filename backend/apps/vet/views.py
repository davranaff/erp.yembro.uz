import secrets

from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status as drf_status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.common.viewsets import OrgScopedModelViewSet

from .models import (
    SellerDeviceToken,
    VaccinationSchedule,
    VaccinationScheduleItem,
    VetDrug,
    VetStockBatch,
    VetTreatmentLog,
)
from .serializers import (
    SellerDeviceTokenCreateSerializer,
    SellerDeviceTokenSerializer,
    VaccinationScheduleItemSerializer,
    VaccinationScheduleSerializer,
    VetDrugSerializer,
    VetStockBatchSerializer,
    VetTreatmentLogSerializer,
)
from .services.apply_treatment import (
    VetTreatmentApplyError,
    apply_vet_treatment,
)
from .services.cancel import VetTreatmentCancelError, cancel_vet_treatment
from .services.receive_stock import (
    VetStockReceiveError,
    receive_vet_stock_batch,
    release_vet_stock_from_quarantine,
)
from .services.recall import VetRecallError, recall_vet_stock_batch


class VetDrugViewSet(OrgScopedModelViewSet):
    serializer_class = VetDrugSerializer
    queryset = VetDrug.objects.select_related("nomenclature")
    module_code = "vet"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["drug_type", "administration_route", "is_active"]
    search_fields = ["nomenclature__sku", "nomenclature__name"]
    ordering = ["nomenclature__sku"]


class VetStockBatchViewSet(OrgScopedModelViewSet):
    serializer_class = VetStockBatchSerializer
    queryset = VetStockBatch.objects.select_related(
        "drug__nomenclature", "warehouse", "supplier", "unit"
    )
    module_code = "vet"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["drug", "warehouse", "status"]
    search_fields = ["doc_number", "lot_number", "barcode"]
    ordering = ["-received_date"]

    @action(detail=False, methods=["post"])
    def receive(self, request):
        """POST /api/vet/stock-batches/receive/
        Приёмка партии препарата на карантин.
        Body: {
            "drug": uuid, "lot_number": str, "warehouse": uuid, "supplier": uuid,
            "purchase": uuid (REQUIRED),
            "received_date": "YYYY-MM-DD", "expiration_date": "YYYY-MM-DD",
            "quantity": decimal, "unit": uuid, "price_per_unit_uzs": decimal,
            "quarantine_until": "YYYY-MM-DD" (optional),
            "barcode": str (optional, авто-генерится),
            "notes": str (optional)
        }
        """
        from datetime import date as date_type
        from decimal import Decimal
        from apps.counterparties.models import Counterparty
        from apps.nomenclature.models import Unit
        from apps.purchases.models import PurchaseOrder
        from apps.warehouses.models import Warehouse

        try:
            drug = VetDrug.objects.get(pk=request.data["drug"])
            wh = Warehouse.objects.get(pk=request.data["warehouse"])
            supplier = Counterparty.objects.get(pk=request.data["supplier"])
            unit = Unit.objects.get(pk=request.data["unit"])
            received = date_type.fromisoformat(request.data["received_date"])
            expires = date_type.fromisoformat(request.data["expiration_date"])
            qty = Decimal(str(request.data["quantity"]))
            price = Decimal(str(request.data["price_per_unit_uzs"]))
        except (KeyError, VetDrug.DoesNotExist, Warehouse.DoesNotExist,
                Counterparty.DoesNotExist, Unit.DoesNotExist, ValueError) as exc:
            raise DRFValidationError({"__all__": f"Некорректные параметры: {exc}"})

        if not request.data.get("purchase"):
            raise DRFValidationError({
                "purchase": "Закуп обязателен (compliance). Создайте PurchaseOrder сначала."
            })
        try:
            purchase = PurchaseOrder.objects.get(pk=request.data["purchase"])
        except PurchaseOrder.DoesNotExist:
            raise DRFValidationError({"purchase": "Не найден."})

        q_until = request.data.get("quarantine_until")
        q_until_date = date_type.fromisoformat(q_until) if q_until else None

        try:
            result = receive_vet_stock_batch(
                organization=request.organization,
                drug=drug,
                lot_number=request.data["lot_number"],
                warehouse=wh,
                supplier=supplier,
                received_date=received,
                expiration_date=expires,
                quantity=qty,
                unit=unit,
                price_per_unit_uzs=price,
                purchase=purchase,
                quarantine_until=q_until_date,
                barcode=request.data.get("barcode") or None,
                notes=request.data.get("notes", ""),
                user=request.user,
            )
        except VetStockReceiveError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        return Response(self.get_serializer(result.stock_batch).data, status=201)

    @action(detail=True, methods=["post"], url_path="release-quarantine")
    def release_quarantine(self, request, pk=None):
        """POST /api/vet/stock-batches/{id}/release-quarantine/"""
        sb = self.get_object()
        try:
            release_vet_stock_from_quarantine(sb, user=request.user)
        except VetStockReceiveError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        sb.refresh_from_db()
        return Response(self.get_serializer(sb).data)

    @action(detail=True, methods=["post"])
    def recall(self, request, pk=None):
        """POST /api/vet/stock-batches/{id}/recall/

        Body: {"reason": str (мин. 3 симв.)}

        Отзывает лот с реверсом всех связанных лечений.
        """
        sb = self.get_object()
        reason = request.data.get("reason", "")
        try:
            result = recall_vet_stock_batch(sb, reason=reason, user=request.user)
        except VetRecallError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        sb.refresh_from_db()
        data = self.get_serializer(sb).data
        data["_result"] = {
            "cancelled_treatments_count": len(result.cancelled_treatments),
        }
        return Response(data)

    @action(detail=False, methods=["get"], url_path="by-barcode")
    def by_barcode(self, request):
        """GET /api/vet/stock-batches/by-barcode/?barcode=X"""
        barcode = request.query_params.get("barcode")
        if not barcode:
            raise DRFValidationError({"barcode": "Обязательно."})
        qs = self.get_queryset().filter(barcode=barcode)
        sb = qs.first()
        if not sb:
            return Response(
                {"detail": "Лот не найден."},
                status=drf_status.HTTP_404_NOT_FOUND,
            )
        return Response(self.get_serializer(sb).data)


class VaccinationScheduleViewSet(OrgScopedModelViewSet):
    serializer_class = VaccinationScheduleSerializer
    queryset = VaccinationSchedule.objects.prefetch_related("items")
    module_code = "vet"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["direction", "is_active"]
    search_fields = ["code", "name"]
    ordering = ["code"]


class VaccinationScheduleItemViewSet(OrgScopedModelViewSet):
    serializer_class = VaccinationScheduleItemSerializer
    queryset = VaccinationScheduleItem.objects.select_related("drug__nomenclature")
    module_code = "vet"
    organization_field = "schedule__organization"
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["schedule", "drug", "is_mandatory"]


class VetTreatmentLogViewSet(OrgScopedModelViewSet):
    """
    /api/vet/treatments/ — журнал применения препаратов.
    POST /api/vet/treatments/{id}/apply/ — провести (сервис).
    POST /api/vet/treatments/{id}/cancel/ — отменить (с reverse JE).
    GET  /api/vet/treatments/timeline/?batch=<uuid>|herd=<uuid> — хронология.
    """

    serializer_class = VetTreatmentLogSerializer
    queryset = VetTreatmentLog.objects.select_related(
        "drug__nomenclature", "stock_batch", "target_block",
        "target_batch", "target_herd", "unit", "veterinarian",
    )
    module_code = "vet"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        "drug",
        "target_batch",
        "target_herd",
        "target_block",
        "indication",
        "stock_batch",
    ]
    search_fields = ["doc_number", "notes"]
    ordering = ["-treatment_date"]

    @action(detail=True, methods=["post"])
    def apply(self, request, pk=None):
        """Провести лечение (декремент лота + withdrawal + JE)."""
        treatment = self.get_object()
        try:
            result = apply_vet_treatment(treatment, user=request.user)
        except VetTreatmentApplyError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )

        treatment.refresh_from_db()
        data = self.get_serializer(treatment).data
        data["_result"] = {
            "stock_movement": {
                "id": str(result.stock_movement.id),
                "doc_number": result.stock_movement.doc_number,
                "amount_uzs": str(result.stock_movement.amount_uzs),
            },
            "journal_entry": {
                "id": str(result.journal_entry.id),
                "doc_number": result.journal_entry.doc_number,
            },
            "batch_cost_entry_id": (
                str(result.batch_cost_entry.id)
                if result.batch_cost_entry
                else None
            ),
            "withdrawal_period_ends": {
                "previous": (
                    result.previous_withdrawal_end.isoformat()
                    if result.previous_withdrawal_end
                    else None
                ),
                "new": (
                    result.new_withdrawal_end.isoformat()
                    if result.new_withdrawal_end
                    else None
                ),
            },
        }
        return Response(data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """POST /api/vet/treatments/{id}/cancel/  body={reason}"""
        treatment = self.get_object()
        reason = request.data.get("reason", "")
        try:
            result = cancel_vet_treatment(treatment, reason=reason, user=request.user)
        except VetTreatmentCancelError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        treatment.refresh_from_db()
        data = self.get_serializer(treatment).data
        data["_result"] = {
            "reversal_je_doc": result.reversal_je.doc_number,
            "reversal_sm_doc": (
                result.reversal_sm.doc_number if result.reversal_sm else None
            ),
            "new_withdrawal_end": (
                result.new_withdrawal_end.isoformat()
                if result.new_withdrawal_end
                else None
            ),
        }
        return Response(data)

    @action(detail=False, methods=["get"])
    def timeline(self, request):
        """GET /api/vet/treatments/timeline/?batch=<uuid>  или ?herd=<uuid>

        Возвращает все лечения партии/стада в хронологическом порядке.
        """
        batch_id = request.query_params.get("batch")
        herd_id = request.query_params.get("herd")
        if not batch_id and not herd_id:
            raise DRFValidationError(
                {"__all__": "Укажите ?batch=<uuid> или ?herd=<uuid>."}
            )
        qs = self.get_queryset()
        if batch_id:
            qs = qs.filter(target_batch_id=batch_id)
        if herd_id:
            qs = qs.filter(target_herd_id=herd_id)
        qs = qs.order_by("treatment_date", "created_at")
        data = self.get_serializer(qs, many=True).data
        return Response(data)


class SellerDeviceTokenViewSet(OrgScopedModelViewSet):
    """
    /api/vet/seller-tokens/ — управление токенами продавцов (admin only).

    POST: создаёт токен для user, генерирует raw token (показывается ОДИН раз
    в ответе на create — потом masked_token).
    POST /{id}/revoke/: помечает revoked_at.
    """

    serializer_class = SellerDeviceTokenSerializer
    queryset = SellerDeviceToken.objects.select_related("user", "organization")
    module_code = "vet"
    write_level = "admin"  # только админ модуля может управлять токенами
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["is_active", "user"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "create":
            return SellerDeviceTokenCreateSerializer
        return SellerDeviceTokenSerializer

    def perform_create(self, serializer):
        from apps.audit.models import AuditLog

        org = self.request.organization
        # Генерируем raw token
        raw = secrets.token_urlsafe(32)
        instance = serializer.save(
            organization=org,
            token=raw,
            is_active=True,
            created_by=self.request.user if self.request.user.is_authenticated else None,
        )
        self._write_audit(AuditLog.Action.CREATE, instance)

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        """POST /api/vet/seller-tokens/{id}/revoke/"""
        from django.utils import timezone
        from apps.audit.models import AuditLog

        tok = self.get_object()
        if tok.revoked_at is not None:
            return Response(
                {"detail": "Токен уже отозван."},
                status=drf_status.HTTP_400_BAD_REQUEST,
            )
        tok.revoked_at = timezone.now()
        tok.is_active = False
        tok.revoked_by = request.user
        tok.save(update_fields=["revoked_at", "is_active", "revoked_by", "updated_at"])
        self._write_audit(
            AuditLog.Action.UPDATE,
            tok,
            verb=f"revoked seller token {tok.masked_token} for {tok.user}",
        )
        return Response(SellerDeviceTokenSerializer(tok).data)
