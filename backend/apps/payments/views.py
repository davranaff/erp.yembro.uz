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

    # Row-level scope по module_id: finance_head с module-assignment
    # видит платежи только своего модуля. Применяется поверх RW-фильтра.
    scope_fields = ("module_id",)

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
        # Head видит платежи своего модуля + платежи без явного module,
        # но привязанные к его кассе (cash_subaccount.module).
        # Плюс: синтетические prepayment'ы миграции (kind=
        # OPENING_BALANCE_PREPAYMENT) — у них нет ни module, ни кассы,
        # это перенесённый кредит контрагента, должен быть виден любому
        # head'у который вообще может видеть контрагентов.
        from django.db.models import Q
        return qs.filter(
            Q(module__code__in=allowed)
            | Q(module__isnull=True, cash_subaccount__module__code__in=allowed)
            | Q(kind=Payment.Kind.OPENING_BALANCE_PREPAYMENT)
        )

    def _check_module_allowed(self, module, cash_subaccount=None):
        """
        Разрешает операцию если у юзера rw на target module.
        Если payment.module не задан — берём fallback с cash_subaccount.module
        (касса привязана к модулю → значит платёж принадлежит этому модулю).
        Org-admin проходит всё.
        """
        allowed = self._allowed_module_codes()
        if allowed is None:
            return

        effective_module = module or (
            cash_subaccount.module if cash_subaccount else None
        )

        if effective_module is None:
            raise PermissionDenied({
                "module": (
                    "Платёж без модуля и без модульной кассы — только администратор. "
                    "Выберите кассу с привязкой к модулю или укажите module."
                ),
            })
        if effective_module.code not in allowed:
            raise PermissionDenied({
                "module": f"Нет прав rw на модуль «{effective_module.code}» — нельзя управлять его кассой.",
            })

    def perform_create(self, serializer):
        self._check_module_allowed(
            serializer.validated_data.get("module"),
            cash_subaccount=serializer.validated_data.get("cash_subaccount"),
        )
        super().perform_create(serializer)

    def perform_update(self, serializer):
        # Защита от смены module на тот, к которому нет доступа
        new_module = serializer.validated_data.get("module") or serializer.instance.module
        new_cash = (
            serializer.validated_data.get("cash_subaccount")
            or serializer.instance.cash_subaccount
        )
        self._check_module_allowed(new_module, cash_subaccount=new_cash)
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
        # objects.create() пропускает Model.clean() — поэтому строим
        # через __init__ + full_clean() + save(). Иначе можно было
        # просунуть amount_uzs <= 0 или target не PO/SO (см.
        # PaymentAllocation.clean()).
        allocation = PaymentAllocation(payment=payment, **serializer.validated_data)
        allocation.full_clean()
        allocation.save()
        payment = (
            Payment.objects.prefetch_related("allocations").get(pk=payment.pk)
        )
        return Response(
            self.get_serializer(payment).data, status=http_status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"], url_path="apply_prepayment")
    def apply_prepayment(self, request, pk=None):
        """
        POST /api/payments/{id}/apply_prepayment/
        Body: {"target_content_type": <id>, "target_object_id": <uuid>, "amount_uzs": "..."}

        Для kind=opening_balance_prepayment (POSTED Payment без проводки):
        кассир аллоцирует часть стартовой предоплаты на новый SO/PO,
        paid_amount_uzs целевого документа пересчитывается автоматом.

        Это отдельный endpoint потому что обычный /allocate/ блокирует
        POSTED-платежи — для регулярных Payment'ов аллокация после post
        ломает баланс журнала. У синтетической предоплаты JE нет, поэтому
        аллокация безопасна.
        """
        from decimal import Decimal as _D

        from django.contrib.contenttypes.models import ContentType

        from apps.purchases.models import PurchaseOrder
        from apps.sales.models import SaleOrder

        from .models import PaymentAllocation
        from .services.post import (
            _recalc_purchase_payment_status,
            _recalc_sale_payment_status,
        )

        payment = self.get_object()
        if payment.kind != Payment.Kind.OPENING_BALANCE_PREPAYMENT:
            raise DRFValidationError({
                "kind": (
                    "apply_prepayment работает только для синтетической "
                    "стартовой предоплаты. Обычные платежи аллоцируются "
                    "до post через /allocate/."
                ),
            })
        if payment.status != Payment.Status.POSTED:
            raise DRFValidationError(
                {"status": "Применять можно только проведённую предоплату."}
            )

        serializer = PaymentAllocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        amount = _D(str(serializer.validated_data["amount_uzs"]))
        if amount <= 0:
            raise DRFValidationError(
                {"amount_uzs": "Сумма должна быть > 0."}
            )

        # Не даём перетянуть больше, чем осталось свободного кредита.
        from django.db.models import Sum

        used = (
            payment.allocations.aggregate(s=Sum("amount_uzs"))["s"] or _D("0")
        )
        free = _D(payment.amount_uzs) - used
        if amount > free:
            raise DRFValidationError({
                "amount_uzs": (
                    f"Доступно {free} сум свободного кредита, "
                    f"запрошено {amount}."
                ),
            })

        # Direction-validity: IN-предоплата → SO, OUT-предоплата → PO.
        po_ct = ContentType.objects.get_for_model(PurchaseOrder)
        so_ct = ContentType.objects.get_for_model(SaleOrder)
        target_ct = serializer.validated_data["target_content_type"]
        if payment.direction == Payment.Direction.IN and target_ct.id != so_ct.id:
            raise DRFValidationError({
                "target_content_type": "IN-предоплата применяется только к SaleOrder.",
            })
        if payment.direction == Payment.Direction.OUT and target_ct.id != po_ct.id:
            raise DRFValidationError({
                "target_content_type": "OUT-предоплата применяется только к PurchaseOrder.",
            })

        # objects.create() пропускает Model.clean(); собираем + full_clean()
        # чтобы прогнать те же проверки что и в /allocate/.
        allocation = PaymentAllocation(
            payment=payment, **serializer.validated_data,
        )
        allocation.full_clean()
        allocation.save()

        # Пересчёт target документа.
        target_id = serializer.validated_data["target_object_id"]
        if target_ct.id == so_ct.id:
            order = SaleOrder.objects.get(pk=target_id)
            _recalc_sale_payment_status(order)
        else:
            order = PurchaseOrder.objects.get(pk=target_id)
            _recalc_purchase_payment_status(order)

        payment = (
            Payment.objects.prefetch_related("allocations").get(pk=payment.pk)
        )
        return Response(
            self.get_serializer(payment).data,
            status=http_status.HTTP_201_CREATED,
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
