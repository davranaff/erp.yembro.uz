from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.common.lifecycle import DeleteReasonMixin, ImmutableStatusMixin
from apps.common.services.numbering import next_doc_number
from apps.common.viewsets import OrgScopedModelViewSet

from .models import SaleCommunication, SaleOrder
from .serializers import SaleCommunicationSerializer, SaleOrderSerializer
from .services.aging import compute_aging_report
from .services.confirm import SaleConfirmError, confirm_sale
from .services.reverse import SaleReverseError, reverse_sale


class SaleOrderViewSet(ImmutableStatusMixin, DeleteReasonMixin, OrgScopedModelViewSet):
    """
    /api/sales/orders/ — продажи.

    Список / создание / правка / удаление черновика (DRAFT).
    Проведение — `POST .../{id}/confirm/`. Сторно — `POST .../{id}/reverse/`.
    """

    serializer_class = SaleOrderSerializer
    queryset = SaleOrder.objects.select_related(
        "customer", "warehouse", "currency", "exchange_rate_source", "module",
    ).prefetch_related("items")

    module_code = "sales"
    required_level = "r"
    write_level = "rw"

    # После confirm/cancel запрещаем PATCH/DELETE — изменения только через
    # reverse-action.
    immutable_statuses = ("confirmed", "cancelled")
    status_field = "status"

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status", "payment_status", "customer", "currency", "module"]
    search_fields = ["doc_number", "customer__name", "customer__code", "notes"]
    ordering_fields = ["date", "doc_number", "amount_uzs", "cost_uzs", "created_at"]
    ordering = ["-date"]

    def perform_create(self, serializer):
        """
        Генерируем doc_number если не задан, чтобы избежать конфликта
        unique_together (organization, doc_number) на пустых строках.
        Префикс «П-» (продажа). Формат: П-YYYY-NNNNN.
        """
        org = getattr(self.request, "organization", None)
        kwargs = self._save_kwargs_for_create(serializer)
        if org is not None and not serializer.validated_data.get("doc_number"):
            kwargs["doc_number"] = next_doc_number(
                SaleOrder,
                organization=org,
                prefix="П",
                on_date=serializer.validated_data.get("date"),
            )
        instance = serializer.save(**kwargs)
        from apps.audit.models import AuditLog
        self._write_audit(AuditLog.Action.CREATE, instance)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        """POST /api/sales/orders/{id}/confirm/

        Body (опционально):
            {"force_credit_override": true}

        Override доступен только sales:admin. Логируется в audit как
        обычный POST + помечается verb-ом 'credit_override'.
        """
        from apps.common.permissions import _effective_level, level_satisfies

        order = self.get_object()

        force = bool(request.data.get("force_credit_override"))
        if force:
            membership = getattr(request, "membership", None)
            if not (membership and level_satisfies(
                _effective_level(membership, "sales"), "admin"
            )):
                raise DRFValidationError({
                    "force_credit_override": (
                        "Override кредитного лимита доступен только sales:admin."
                    ),
                })

        try:
            result = confirm_sale(
                order, user=request.user, force_credit_override=force,
            )
        except SaleConfirmError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )

        if force:
            from apps.audit.models import AuditLog
            from apps.audit.services.writer import audit_log
            audit_log(
                organization=order.organization,
                module=order.module,
                actor=request.user,
                action=AuditLog.Action.UPDATE,
                entity=order,
                action_verb=f"credit_override on confirm of {order.doc_number}",
            )

        order.refresh_from_db()

        # TG-уведомление админам с доступом к sales (parity с purchases.confirm).
        # Без этого владелец не видит что продажа проведена — только в /sales.
        try:
            from apps.tgbot.notifications import fmt_sale_confirmed
            from apps.tgbot.tasks import notify_admins_task
            notify_admins_task.delay(
                fmt_sale_confirmed(order), str(order.organization_id), "sales"
            )
        except Exception:
            pass

        data = self.get_serializer(order).data
        data["_result"] = {
            "stock_movements_count": len(result.stock_movements),
            "revenue_journal": {
                "id": str(result.revenue_journal.id),
                "doc_number": result.revenue_journal.doc_number,
            },
            "cost_journals": [
                {"id": str(je.id), "doc_number": je.doc_number}
                for je in result.cost_journals
            ],
            "rate_snapshot": str(result.rate_snapshot) if result.rate_snapshot else None,
        }
        return Response(data)

    @action(detail=True, methods=["post"])
    def reverse(self, request, pk=None):
        order = self.get_object()
        reason = request.data.get("reason", "")
        try:
            result = reverse_sale(order, reason=reason, user=request.user)
        except SaleReverseError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        order.refresh_from_db()
        data = self.get_serializer(order).data
        data["_result"] = {
            "reverse_movements_count": len(result.reverse_movements),
            "reverse_journals_count": len(result.reverse_journals),
        }
        return Response(data)

    @action(detail=True, methods=["post"], url_path="record_payment")
    def record_payment(self, request, pk=None):
        """
        POST /api/sales/orders/{id}/record_payment/
        Body: {
          "channel": "cash" | "transfer" | "click" | "other",
          "amount_uzs": "...",        # опционально, default = оставшаяся сумма
          "date": "YYYY-MM-DD",       # опционально, default = сегодня
          "notes": "..."              # опционально
        }

        Создаёт Payment(kind=counterparty, direction=in) с аллокацией на эту
        продажу и сразу проводит (create_and_post_payment). После этого
        paid_amount_uzs и payment_status продажи обновляются автоматически
        в post_payment.
        """
        from datetime import date as date_cls
        from decimal import Decimal

        from apps.payments.models import Payment
        from apps.payments.services.post import (
            PaymentPostError,
            create_and_post_payment,
        )

        order = self.get_object()

        if order.status != SaleOrder.Status.CONFIRMED:
            raise DRFValidationError(
                {"status": (
                    f"Принимать оплату можно только за проведённую продажу, "
                    f"текущий статус: {order.get_status_display()}."
                )}
            )

        channel = request.data.get("channel", "cash")
        if channel not in {"cash", "transfer", "click", "other"}:
            raise DRFValidationError({"channel": f"Недопустимое значение: {channel}."})

        # Сумма: если не передана — остаток долга
        amount_raw = request.data.get("amount_uzs")
        remaining = Decimal(order.amount_uzs) - Decimal(order.paid_amount_uzs or 0)
        if amount_raw is None or amount_raw == "":
            amount = remaining
        else:
            try:
                amount = Decimal(str(amount_raw))
            except Exception:
                raise DRFValidationError({"amount_uzs": "Некорректная сумма."})

        if amount <= 0:
            raise DRFValidationError(
                {"amount_uzs": "Сумма должна быть больше нуля."}
            )

        date_raw = request.data.get("date")
        if date_raw:
            try:
                pay_date = date_cls.fromisoformat(date_raw)
            except ValueError as exc:
                raise DRFValidationError({"date": str(exc)})
        else:
            pay_date = date_cls.today()

        try:
            result = create_and_post_payment(
                organization=order.organization,
                direction=Payment.Direction.IN,
                channel=channel,
                counterparty=order.customer,
                amount_uzs=amount,
                date=pay_date,
                module=order.module,
                allocations=[{"target": order, "amount_uzs": amount}],
                notes=request.data.get("notes", f"Оплата по {order.doc_number}"),
                user=request.user,
            )
        except PaymentPostError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )

        # TG-уведомление о входящей оплате — service create_and_post_payment
        # бэйпасит обычный POST /api/payments/{id}/post/, поэтому здесь
        # вызываем notify явно, иначе админ не увидит cash inflow.
        try:
            from apps.tgbot.notifications import fmt_payment_posted
            from apps.tgbot.tasks import notify_admins_task
            notify_admins_task.delay(
                fmt_payment_posted(result.payment),
                str(result.payment.organization_id),
                "sales",
            )
        except Exception:
            pass

        order.refresh_from_db()
        data = self.get_serializer(order).data
        data["_result"] = {
            "payment": {
                "id": str(result.payment.id),
                "doc_number": result.payment.doc_number,
                "amount_uzs": str(result.payment.amount_uzs),
            },
            "journal_entry": {
                "id": str(result.journal_entry.id),
                "doc_number": result.journal_entry.doc_number,
            },
        }
        return Response(data)

    @action(detail=True, methods=["get"], url_path="credit_check")
    def credit_check(self, request, pk=None):
        """GET /api/sales/orders/{id}/credit_check/

        Превью кредитной проверки для draft-продажи. FE дёргает перед
        кнопкой confirm, чтобы показать warning «у клиента долг X, лимит Y»
        ещё до клика. Не делает никаких изменений.
        """
        from decimal import Decimal

        from .services.credit_check import check_customer_credit

        order = self.get_object()
        new_sale_uzs = sum(
            (Decimal(it.quantity) * Decimal(it.unit_price_uzs)
             for it in order.items.all()),
            Decimal("0"),
        )
        result = check_customer_credit(
            organization=order.organization,
            customer=order.customer,
            new_sale_uzs=new_sale_uzs,
        )
        return Response(result.to_dict())

    @action(detail=False, methods=["get"], url_path="tasks")
    def tasks(self, request):
        """GET /api/sales/orders/tasks/[?mine=true]

        Workflow задач по сбору дебиторки. Категории:
          - callback_due  : запланированный обзвон
          - promise_broken: клиент не сдержал обещание
          - forecast_due  : не пришла прогнозная оплата
          - escalation    : долг 60+ дней без касаний за 7+ дней

        `?mine=true` — фильтр на касания текущего пользователя
        (escalation остаётся глобальной — её делает руководитель).
        """
        from .services.collection_tasks import compute_collection_tasks

        mine = request.query_params.get("mine") in ("1", "true", "True")
        contacted_by = request.user if mine else None
        report = compute_collection_tasks(
            request.organization, contacted_by=contacted_by,
        )
        return Response(report.to_dict())

    @action(detail=False, methods=["get"], url_path="aging")
    def aging(self, request):
        """GET /api/sales/orders/aging/[?customer=<uuid>]

        AR aging report — старение дебиторки. Группирует непогашенные
        confirmed-продажи по бакетам просрочки (current / 0-30 / 31-60 /
        61-90 / 90+) для каждого клиента.

        Параметр `?customer=<uuid>` сужает отчёт до одного клиента
        (используется в карточке должника).
        """
        org = request.organization
        customer_id = request.query_params.get("customer")
        report = compute_aging_report(org, customer_id=customer_id)
        return Response(report.to_dict())

    @action(detail=True, methods=["get"])
    def timeline(self, request, pk=None):
        """GET /api/sales/orders/{id}/timeline/

        Хронология событий по заказу: создание, проведение, платежи, сторно.
        """
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


class SaleCommunicationViewSet(OrgScopedModelViewSet):
    """
    /api/sales/communications/ — история общения с клиентом по продаже.

    Список фильтруется по `?order=<uuid>` для drawer-а конкретной продажи.
    Создание: тот, кто звонил/писал, фиксирует ответ клиента + (опционально)
    обещанную дату оплаты + дату следующего касания.

    Доступ — те же кто работает с продажами (`sales` модуль).
    """

    serializer_class = SaleCommunicationSerializer
    queryset = SaleCommunication.objects.select_related("order", "contacted_by")
    organization_field = "order__organization"

    module_code = "sales"
    required_level = "r"
    write_level = "rw"

    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["order", "method", "outcome"]
    ordering_fields = ["contacted_at", "promised_pay_date", "created_at"]
    ordering = ["-contacted_at"]

    def perform_create(self, serializer):
        """`contacted_by` всегда = request.user; не разрешаем подделать.
        Cross-org защита: order должен принадлежать current org."""
        from apps.audit.models import AuditLog
        from rest_framework.exceptions import PermissionDenied

        org = getattr(self.request, "organization", None)
        order = serializer.validated_data.get("order")
        if order is not None and org is not None and order.organization_id != org.id:
            raise PermissionDenied(
                {"order": "Продажа из другой организации."}
            )

        instance = serializer.save(contacted_by=self.request.user)
        self._write_audit(AuditLog.Action.CREATE, instance)
