from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status as http_status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.lifecycle import DeleteReasonMixin, ImmutableStatusMixin
from apps.common.permissions import (
    HasAnyModuleRw,
    get_user_rw_module_codes,
    is_org_admin,
)
from apps.common.viewsets import OrgScopedModelViewSet

from .models import Payment, PaymentAllocation
from .serializers import PaymentAllocationSerializer, PaymentSerializer
from .services.post import PaymentPostError, post_payment
from .services.reverse import PaymentReverseError, reverse_payment


class PaymentViewSet(ImmutableStatusMixin, DeleteReasonMixin, OrgScopedModelViewSet):
    """
    /api/payments/ — платежи (AP + AR).

    Доступ: cross-module — head'у любого модуля разрешено управлять кассой
    своего модуля. Скоуп через get_queryset() (фильтр по `module__code IN
    user.rw_modules`). На create/edit проверяется что body['module']
    тоже в rw_modules. Org-admin (любой override level=admin) — без
    ограничений.

    Жизненный цикл:
      POST /api/payments/                       → draft
      POST /api/payments/{id}/allocate/          → добавить аллокацию
      POST /api/payments/{id}/post/              → провести (POSTED)
      POST /api/payments/{id}/cancel/            → отменить (из draft/confirmed)
    """

    permission_classes = [IsAuthenticated, HasAnyModuleRw]
    serializer_class = PaymentSerializer
    queryset = Payment.objects.select_related(
        "counterparty", "currency", "exchange_rate_source",
        "cash_subaccount", "journal_entry",
    ).prefetch_related("allocations")

    # module_code не задан намеренно — HasAnyModuleRw + queryset-скоуп
    # сами обеспечивают защиту. required_level/write_level тоже не нужны.

    # Проведённые/отменённые платежи иммутабельны (для reverse — отдельный action).
    immutable_statuses = ("posted", "cancelled")
    status_field = "status"

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        "status", "direction", "channel", "kind",
        "counterparty", "currency", "module",
        "cash_subaccount", "contra_subaccount",
    ]
    search_fields = ["doc_number", "counterparty__name", "counterparty__code", "notes"]
    ordering_fields = ["date", "doc_number", "amount_uzs", "created_at"]
    ordering = ["-date"]

    def _allowed_module_codes(self) -> set[str] | None:
        """
        Возвращает set кодов модулей, которыми текущий юзер может управлять.
        None — без ограничения (org-admin).
        """
        membership = getattr(self.request, "membership", None)
        if membership is None:
            return set()
        if is_org_admin(membership):
            return None
        return get_user_rw_module_codes(membership)

    def get_queryset(self):
        qs = super().get_queryset()
        allowed = self._allowed_module_codes()
        if allowed is None:
            return qs
        if not allowed:
            return qs.none()
        return qs.filter(module__code__in=allowed)

    def _check_module_allowed(self, module):
        allowed = self._allowed_module_codes()
        if allowed is None:
            return
        if module is None or module.code not in allowed:
            code = module.code if module else "(не задан)"
            raise PermissionDenied({
                "module": f"Нет прав rw на модуль «{code}» — нельзя управлять его кассой.",
            })

    def perform_create(self, serializer):
        self._check_module_allowed(serializer.validated_data.get("module"))
        super().perform_create(serializer)

    def perform_update(self, serializer):
        # Защита от смены module на тот, к которому нет доступа
        new_module = serializer.validated_data.get("module") or serializer.instance.module
        self._check_module_allowed(new_module)
        super().perform_update(serializer)

    @action(detail=True, methods=["post"])
    def post(self, request, pk=None):
        """POST /api/payments/{id}/post/ — провести платёж."""
        payment = self.get_object()
        try:
            result = post_payment(payment, user=request.user)
        except PaymentPostError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )

        payment.refresh_from_db()

        # TG-уведомления через orchestrator: клиент/поставщик + админы
        # организации + head sales/purchases в зависимости от direction.
        try:
            from apps.tgbot.services.orchestration import notify_payment_event
            notify_payment_event(payment)
        except Exception:
            pass

        data = self.get_serializer(payment).data
        data["_result"] = {
            "journal_entry": {
                "id": str(result.journal_entry.id),
                "doc_number": result.journal_entry.doc_number,
            },
            "affected_orders": [
                {
                    "id": str(o.id),
                    "doc_number": o.doc_number,
                    "paid_amount_uzs": str(o.paid_amount_uzs),
                    "payment_status": o.payment_status,
                }
                for o in result.affected_orders
            ],
        }
        return Response(data)

    @action(detail=True, methods=["post"])
    def allocate(self, request, pk=None):
        """
        POST /api/payments/{id}/allocate/
        Body: {"target_content_type": <id>, "target_object_id": <uuid>, "amount_uzs": "..."}
        """
        payment = self.get_object()
        if payment.status == Payment.Status.POSTED:
            raise DRFValidationError(
                {"status": "Нельзя аллоцировать проведённый платёж."}
            )
        serializer = PaymentAllocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        PaymentAllocation.objects.create(payment=payment, **serializer.validated_data)
        payment = (
            Payment.objects.prefetch_related("allocations").get(pk=payment.pk)
        )
        return Response(
            self.get_serializer(payment).data, status=http_status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """POST /api/payments/{id}/cancel/ — отменить DRAFT/CONFIRMED."""
        payment = self.get_object()
        if payment.status == Payment.Status.POSTED:
            raise DRFValidationError(
                {"status": "Проведённый платёж нельзя отменить — нужен reversal."}
            )
        if payment.status == Payment.Status.CANCELLED:
            return Response(self.get_serializer(payment).data)
        payment.status = Payment.Status.CANCELLED
        payment.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(payment).data)

    @action(detail=True, methods=["post"])
    def reverse(self, request, pk=None):
        """POST /api/payments/{id}/reverse/ — сторно проведённого платежа."""
        payment = self.get_object()
        reason = request.data.get("reason", "")
        try:
            result = reverse_payment(payment, reason=reason, user=request.user)
        except PaymentReverseError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        payment.refresh_from_db()
        data = self.get_serializer(payment).data
        data["_result"] = {
            "reverse_journal": {
                "id": str(result.reverse_journal.id),
                "doc_number": result.reverse_journal.doc_number,
            },
            "affected_orders": [
                {
                    "id": str(o.id),
                    "doc_number": o.doc_number,
                    "paid_amount_uzs": str(o.paid_amount_uzs),
                    "payment_status": o.payment_status,
                }
                for o in result.affected_orders
            ],
        }
        return Response(data)

    @action(detail=True, methods=["get"])
    def timeline(self, request, pk=None):
        """GET /api/payments/{id}/timeline/"""
        from apps.common.services.document_timeline import build_document_timeline

        payment = self.get_object()
        # Для платежа extra-событий нет — только аудит. Аллокации видны в drawer'е отдельно.
        events = build_document_timeline(payment)
        return Response({"events": events, "count": len(events)})
