from decimal import Decimal

from django.db.models import Sum
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.common.viewsets import OrgScopedModelViewSet

from .models import Counterparty
from .serializers import CounterpartySerializer


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
