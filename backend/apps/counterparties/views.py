from decimal import Decimal

from django.db.models import Sum
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.common.viewsets import OrgScopedModelViewSet

from .models import Counterparty
from .serializers import CounterpartySerializer


def _build_debt_summary(counterparty, organization) -> dict:
    """Свод по долгу одного клиента: aging, лимит, открытые счета, касания.

    Используется в карточке клиента (FE drawer/page).
    Дёргает существующие сервисы (compute_aging_report, check_customer_credit)
    чтобы не дублировать логику.
    """
    from apps.sales.models import SaleCommunication, SaleOrder
    from apps.sales.services.aging import compute_aging_report
    from apps.sales.services.credit_check import check_customer_credit

    aging = compute_aging_report(organization, customer_id=str(counterparty.id))
    aging_row = aging.rows[0].to_dict() if aging.rows else None

    credit = check_customer_credit(
        organization=organization, customer=counterparty,
    ).to_dict()

    # Открытые продажи (CONFIRMED, не PAID)
    open_orders_qs = (
        SaleOrder.objects
        .filter(
            organization=organization,
            customer=counterparty,
            status=SaleOrder.Status.CONFIRMED,
        )
        .exclude(payment_status=SaleOrder.PaymentStatus.PAID)
        .order_by("-date")
    )
    open_orders = [
        {
            "id": str(o.id),
            "doc_number": o.doc_number,
            "date": o.date.isoformat(),
            "due_date": o.due_date.isoformat() if o.due_date else None,
            "amount_uzs": str(o.amount_uzs),
            "paid_amount_uzs": str(o.paid_amount_uzs or 0),
            "outstanding_uzs": str(
                Decimal(o.amount_uzs) - Decimal(o.paid_amount_uzs or 0)
            ),
            "payment_status": o.payment_status,
        }
        for o in open_orders_qs
    ]

    # Все касания этого клиента (через order__customer)
    comms_qs = (
        SaleCommunication.objects
        .filter(order__customer=counterparty,
                order__organization=organization)
        .select_related("contacted_by", "order")
        .order_by("-contacted_at")[:50]
    )
    comms = [
        {
            "id": str(c.id),
            "order_id": str(c.order_id),
            "order_doc": c.order.doc_number,
            "contacted_at": c.contacted_at.isoformat(),
            "method": c.method,
            "method_display": c.get_method_display(),
            "outcome": c.outcome,
            "outcome_display": c.get_outcome_display(),
            "customer_response": c.customer_response,
            "internal_note": c.internal_note,
            "promised_pay_date": (
                c.promised_pay_date.isoformat() if c.promised_pay_date else None
            ),
            "expected_pay_date": (
                c.expected_pay_date.isoformat() if c.expected_pay_date else None
            ),
            "next_action_date": (
                c.next_action_date.isoformat() if c.next_action_date else None
            ),
            "contacted_by": str(c.contacted_by_id) if c.contacted_by_id else None,
            "contacted_by_name": (
                getattr(c.contacted_by, "full_name", None)
                or getattr(c.contacted_by, "email", None)
                if c.contacted_by_id else None
            ),
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat(),
        }
        for c in comms_qs
    ]

    # Утилизация лимита (% от лимита, занятый текущим долгом)
    limit_uzs = counterparty.credit_limit_uzs
    current_debt = Decimal(credit["current_debt_uzs"])
    if limit_uzs and limit_uzs > 0:
        utilization_pct = round(float(current_debt / limit_uzs * 100), 1)
    else:
        utilization_pct = None

    return {
        "counterparty": CounterpartySerializer(counterparty).data,
        "aging": aging_row,
        "aging_as_of": aging.as_of.isoformat(),
        "credit": credit,
        "credit_utilization_pct": utilization_pct,
        "open_orders": open_orders,
        "open_orders_count": len(open_orders),
        "communications": comms,
        "communications_count": len(comms),
    }


class CounterpartyViewSet(OrgScopedModelViewSet):
    """
    CRUD контрагентов для текущей организации.
    Требует: IsAuthenticated + X-Organization-Code + модуль `core` (r/rw).
    """

    serializer_class = CounterpartySerializer
    queryset = Counterparty.objects.all()

    module_code = "core"
    required_level = "r"
    write_level = "rw"

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["kind", "is_active"]
    search_fields = ["code", "name", "inn"]
    ordering_fields = ["code", "name", "balance_uzs", "created_at"]
    ordering = ["code"]

    def perform_create(self, serializer):
        super().perform_create(serializer)
        self._sync_opening_balance(serializer.instance)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        self._sync_opening_balance(serializer.instance)

    def _sync_opening_balance(self, counterparty):
        """Материализует opening_debt в синтетический SaleOrder.

        Без этого долг живёт только числом на карточке — касса не может
        принять оплату, /tasks молчит, aging требует костыля. Подробнее
        в apps/sales/services/opening_balance.py.
        """
        from apps.sales.services.opening_balance import (
            sync_opening_balance_for_counterparty,
        )

        sync_opening_balance_for_counterparty(counterparty)

    @action(detail=False, methods=["get"], url_path="balances")
    def balances(self, request):
        """GET /api/counterparties/balances/

        Auto-AR/AP отчёт: для каждого контрагента возвращает невыплаченные
        суммы по PurchaseOrder (AP — мы должны поставщикам) и SaleOrder
        (AR — нам должны клиенты).

        Источник истины — `payment_status` + `paid_amount_uzs` на самих
        документах. Отдельной таблицы AR/AP не нужно: при confirm/post
        ордера и при создании Payment эти поля обновляются автоматически.

        Параметры: `?kind=supplier|customer` (опционально).
        """
        from apps.purchases.models import PurchaseOrder
        from apps.sales.models import SaleOrder

        org = request.organization
        kind_filter = request.query_params.get("kind")

        ap_qs = (
            PurchaseOrder.objects.filter(
                organization=org,
                status=PurchaseOrder.Status.CONFIRMED,
            )
            .exclude(payment_status=PurchaseOrder.PaymentStatus.PAID)
            .values(
                "counterparty_id",
                "counterparty__code",
                "counterparty__name",
                "counterparty__kind",
            )
            .annotate(amount=Sum("amount_uzs"), paid=Sum("paid_amount_uzs"))
        )

        rows: dict = {}
        for row in ap_qs:
            cp_id = row["counterparty_id"]
            if cp_id is None:
                continue
            outstanding = (row["amount"] or Decimal("0")) - (row["paid"] or Decimal("0"))
            if outstanding <= 0:
                continue
            rows[cp_id] = {
                "counterparty_id": str(cp_id),
                "code": row["counterparty__code"],
                "name": row["counterparty__name"],
                "kind": row["counterparty__kind"],
                "ap_uzs": str(outstanding),
                "ar_uzs": "0",
            }

        ar_qs = (
            SaleOrder.objects.filter(
                organization=org,
                status=SaleOrder.Status.CONFIRMED,
            )
            .exclude(payment_status=SaleOrder.PaymentStatus.PAID)
            .values(
                "counterparty_id",
                "counterparty__code",
                "counterparty__name",
                "counterparty__kind",
            )
            .annotate(amount=Sum("amount_uzs"), paid=Sum("paid_amount_uzs"))
        )

        for row in ar_qs:
            cp_id = row["counterparty_id"]
            if cp_id is None:
                continue
            outstanding = (row["amount"] or Decimal("0")) - (row["paid"] or Decimal("0"))
            if outstanding <= 0:
                continue
            existing = rows.get(cp_id)
            if existing:
                existing["ar_uzs"] = str(outstanding)
            else:
                rows[cp_id] = {
                    "counterparty_id": str(cp_id),
                    "code": row["counterparty__code"],
                    "name": row["counterparty__name"],
                    "kind": row["counterparty__kind"],
                    "ap_uzs": "0",
                    "ar_uzs": str(outstanding),
                }

        result = list(rows.values())
        if kind_filter:
            result = [r for r in result if r["kind"] == kind_filter]
        result.sort(
            key=lambda r: max(Decimal(r["ap_uzs"]), Decimal(r["ar_uzs"])),
            reverse=True,
        )

        total_ap = sum((Decimal(r["ap_uzs"]) for r in result), Decimal("0"))
        total_ar = sum((Decimal(r["ar_uzs"]) for r in result), Decimal("0"))

        return Response({
            "rows": result,
            "summary": {
                "total_ap_uzs": str(total_ap),     # мы должны
                "total_ar_uzs": str(total_ar),     # нам должны
                "net_uzs": str(total_ar - total_ap),
                "counterparties_count": len(result),
            },
        })

    @action(detail=True, methods=["get"], url_path="debt_summary")
    def debt_summary(self, request, pk=None):
        """GET /api/counterparties/{id}/debt_summary/

        Сводный отчёт по клиенту для карточки должника:
          - реквизиты
          - aging (бакеты просрочки)
          - кредитный лимит + утилизация %
          - открытые счета (CONFIRMED, не PAID)
          - последние 50 касаний (cross-order)

        Использует существующие сервисы compute_aging_report и
        check_customer_credit — не дублирует логику.
        """
        cp = self.get_object()
        return Response(_build_debt_summary(cp, request.organization))
