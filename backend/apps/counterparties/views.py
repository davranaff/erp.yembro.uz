import re
from decimal import Decimal

from django.db.models import Sum
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.common.viewsets import OrgScopedModelViewSet

from .models import Counterparty
from .serializers import CounterpartySerializer


_CP_CODE_RE = re.compile(r"^(.+)-(\d+)$")


def _next_counterparty_code(organization, prefix: str) -> str:
    """Следующий свободный код вида `{prefix}-NNN` в рамках организации.

    Сканируем существующие коды по `code__startswith`, парсим цифровой
    суффикс, берём max+1. Без advisory lock — конкурентные создания
    редки, в худшем случае unique_together словит дубль и юзер
    перезапустит.
    """
    existing = Counterparty.objects.filter(
        organization=organization, code__startswith=f"{prefix}-",
    ).values_list("code", flat=True)
    max_n = 0
    for c in existing:
        m = _CP_CODE_RE.match(c)
        if not m:
            continue
        if m.group(1) != prefix:
            continue
        try:
            n = int(m.group(2))
            if n > max_n:
                max_n = n
        except ValueError:
            continue
    return f"{prefix}-{max_n + 1:03d}"


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

    # Свободный кредит из стартовой предоплаты (kind=opening_balance_prepayment).
    # Если у клиента/поставщика был отрицательный opening_debt — здесь сидит
    # POSTED Payment без allocations. Кассир может применить часть к новой
    # SO/PO через /api/payments/{id}/apply_prepayment/.
    from django.db.models import Sum

    from apps.payments.models import Payment

    prepayments = []
    prepay_qs = Payment.objects.filter(
        organization=organization,
        counterparty=counterparty,
        kind=Payment.Kind.OPENING_BALANCE_PREPAYMENT,
        status=Payment.Status.POSTED,
    ).prefetch_related("allocations")
    for pay in prepay_qs:
        used = pay.allocations.aggregate(s=Sum("amount_uzs"))["s"] or Decimal("0")
        free = Decimal(pay.amount_uzs) - used
        if free <= 0:
            continue
        prepayments.append({
            "id": str(pay.id),
            "doc_number": pay.doc_number,
            "date": pay.date.isoformat(),
            "amount_uzs": str(pay.amount_uzs),
            "used_uzs": str(used),
            "free_uzs": str(free),
            "direction": pay.direction,
        })

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
        "prepayments": prepayments,
        "prepayments_total_free_uzs": str(
            sum(
                (Decimal(p["free_uzs"]) for p in prepayments),
                Decimal("0"),
            )
        ),
    }


def _build_extended_summary(counterparty, organization) -> dict:
    """
    Расширение для full_summary: вся история документов и платежей,
    + помесячная агрегация оборотов за последние 12 месяцев.
    """
    from datetime import date, timedelta

    from django.db.models import Sum

    from apps.payments.models import Payment
    from apps.purchases.models import PurchaseOrder
    from apps.sales.models import SaleOrder

    # ── all_orders: SaleOrder + PurchaseOrder любого статуса ─────────────
    sale_qs = (
        SaleOrder.objects.filter(
            organization=organization, customer=counterparty,
        ).order_by("-date")
    )
    purchase_qs = (
        PurchaseOrder.objects.filter(
            organization=organization, counterparty=counterparty,
        ).order_by("-date")
    )

    all_orders = []
    for o in sale_qs:
        amt = Decimal(o.amount_uzs or 0)
        paid = Decimal(o.paid_amount_uzs or 0)
        all_orders.append({
            "id": str(o.id),
            "kind": "sale",
            "doc_number": o.doc_number,
            "date": o.date.isoformat(),
            "due_date": o.due_date.isoformat() if o.due_date else None,
            "status": o.status,
            "payment_status": o.payment_status,
            "amount_uzs": str(amt),
            "paid_amount_uzs": str(paid),
            "outstanding_uzs": str(amt - paid),
        })
    for o in purchase_qs:
        amt = Decimal(o.amount_uzs or 0)
        paid = Decimal(o.paid_amount_uzs or 0)
        all_orders.append({
            "id": str(o.id),
            "kind": "purchase",
            "doc_number": o.doc_number,
            "date": o.date.isoformat(),
            "due_date": o.due_date.isoformat() if getattr(o, "due_date", None) else None,
            "status": o.status,
            "payment_status": getattr(o, "payment_status", None),
            "amount_uzs": str(amt),
            "paid_amount_uzs": str(paid),
            "outstanding_uzs": str(amt - paid),
        })
    all_orders.sort(key=lambda r: r["date"], reverse=True)

    # ── all_payments: вся история Payment этого контрагента ──────────────
    payments_qs = (
        Payment.objects.filter(
            organization=organization, counterparty=counterparty,
        )
        .select_related("currency")
        .order_by("-date")
    )
    all_payments = []
    for p in payments_qs:
        all_payments.append({
            "id": str(p.id),
            "doc_number": p.doc_number,
            "date": p.date.isoformat(),
            "direction": p.direction,
            "channel": p.channel,
            "kind": p.kind,
            "status": p.status,
            "amount_uzs": str(p.amount_uzs),
            "currency_code": p.currency.code if p.currency_id else None,
            "amount_foreign": str(p.amount_foreign) if p.amount_foreign is not None else None,
            "exchange_rate": str(p.exchange_rate) if p.exchange_rate is not None else None,
            "notes": p.notes or "",
        })

    # ── monthly_turnover: помесячная агрегация за 12 мес ──────────────────
    today = date.today()
    months: list[dict] = []
    for i in range(11, -1, -1):
        # Собираем 12 точек, последняя — текущий месяц.
        year = today.year
        month = today.month - i
        while month <= 0:
            month += 12
            year -= 1
        month_start = date(year, month, 1)
        if month == 12:
            next_start = date(year + 1, 1, 1)
        else:
            next_start = date(year, month + 1, 1)
        month_end = next_start - timedelta(days=1)

        sales_total = sale_qs.filter(
            date__gte=month_start, date__lte=month_end,
            status=SaleOrder.Status.CONFIRMED,
        ).aggregate(s=Sum("amount_uzs"))["s"] or Decimal("0")
        purchases_total = purchase_qs.filter(
            date__gte=month_start, date__lte=month_end,
        ).aggregate(s=Sum("amount_uzs"))["s"] or Decimal("0")
        payments_in = payments_qs.filter(
            date__gte=month_start, date__lte=month_end,
            direction=Payment.Direction.IN,
            status=Payment.Status.POSTED,
        ).aggregate(s=Sum("amount_uzs"))["s"] or Decimal("0")
        payments_out = payments_qs.filter(
            date__gte=month_start, date__lte=month_end,
            direction=Payment.Direction.OUT,
            status=Payment.Status.POSTED,
        ).aggregate(s=Sum("amount_uzs"))["s"] or Decimal("0")

        months.append({
            "month": month_start.isoformat()[:7],  # "2026-04"
            "sales_uzs": str(sales_total),
            "purchases_uzs": str(purchases_total),
            "payments_in_uzs": str(payments_in),
            "payments_out_uzs": str(payments_out),
        })

    return {
        "all_orders": all_orders,
        "all_orders_count": len(all_orders),
        "all_payments": all_payments,
        "all_payments_count": len(all_payments),
        "monthly_turnover": months,
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

    def get_serializer_context(self):
        """
        Для list-ответа один раз агрегируем outstanding по непогашенным
        SaleOrder (AR) и PurchaseOrder (AP) — это и есть «реальный долг»,
        включая синтетический OPENING_BALANCE SO. Передаём словарём в
        context, сериализатор берёт оттуда current_debt_uzs.
        """
        ctx = super().get_serializer_context()
        # debt_map нужен только на list. retrieve/create/update обходятся
        # fallback'ом на opening_debt_uzs в сериализаторе.
        if self.action != "list":
            return ctx

        from decimal import Decimal

        from django.db.models import F, Sum

        from apps.purchases.models import PurchaseOrder
        from apps.sales.models import SaleOrder

        org = getattr(self.request, "organization", None)
        if org is None:
            return ctx

        debt_map: dict = {}

        ar_rows = (
            SaleOrder.objects
            .filter(organization=org, status=SaleOrder.Status.CONFIRMED)
            .exclude(payment_status=SaleOrder.PaymentStatus.PAID)
            .values("customer_id")
            .annotate(out=Sum(F("amount_uzs") - F("paid_amount_uzs")))
        )
        for r in ar_rows:
            cp_id = r["customer_id"]
            if cp_id is None:
                continue
            outstanding = r["out"] or Decimal("0")
            if outstanding > 0:
                debt_map[cp_id] = debt_map.get(cp_id, Decimal("0")) + outstanding

        ap_rows = (
            PurchaseOrder.objects
            .filter(organization=org, status=PurchaseOrder.Status.CONFIRMED)
            .exclude(payment_status=PurchaseOrder.PaymentStatus.PAID)
            .values("counterparty_id")
            .annotate(out=Sum(F("amount_uzs") - F("paid_amount_uzs")))
        )
        for r in ap_rows:
            cp_id = r["counterparty_id"]
            if cp_id is None:
                continue
            outstanding = r["out"] or Decimal("0")
            if outstanding > 0:
                debt_map[cp_id] = debt_map.get(cp_id, Decimal("0")) + outstanding

        ctx["current_debt_map"] = debt_map
        return ctx

    def perform_create(self, serializer):
        """Авто-генерация code по kind если не задан: К-NNN / КС-NNN / КП-NNN."""
        org = getattr(self.request, "organization", None)
        code = (serializer.validated_data.get("code") or "").strip()
        if not code and org is not None:
            kind = serializer.validated_data.get("kind", "other")
            prefix = {"buyer": "К", "supplier": "КС"}.get(kind, "КП")
            serializer.validated_data["code"] = _next_counterparty_code(org, prefix)
        super().perform_create(serializer)
        self._sync_opening_balance(serializer.instance)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        self._sync_opening_balance(serializer.instance)

    def _sync_opening_balance(self, counterparty):
        """Материализует opening_debt в синтетический документ.

        Без этого «снимок миграции» живёт только числом на карточке и не
        участвует в стандартных пайплайнах (касса/aging/tasks).

        Положительное opening_debt:
            - kind=buyer    → SaleOrder      (мы выставляем счёт клиенту)
            - kind=supplier → PurchaseOrder  (поставщик выставил нам счёт)

        Отрицательное opening_debt (стартовая предоплата):
            - kind=buyer    → Payment(IN)    (клиент уже занёс)
            - kind=supplier → Payment(OUT)   (мы уже заплатили авансом)

        Все три ветки идемпотентны — повторные save'ы карточки не плодят
        дубликаты.
        """
        from apps.payments.services.opening_balance_prepayment import (
            sync_opening_balance_prepayment_for_counterparty,
        )
        from apps.purchases.services.opening_balance import (
            sync_opening_balance_for_supplier,
        )
        from apps.sales.services.opening_balance import (
            sync_opening_balance_for_counterparty,
        )

        sync_opening_balance_for_counterparty(counterparty)
        sync_opening_balance_for_supplier(counterparty)
        sync_opening_balance_prepayment_for_counterparty(counterparty)

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

        # SaleOrder использует поле `customer` (а не counterparty), нужен
        # отдельный alias для агрегации.
        ar_qs = (
            SaleOrder.objects.filter(
                organization=org,
                status=SaleOrder.Status.CONFIRMED,
            )
            .exclude(payment_status=SaleOrder.PaymentStatus.PAID)
            .values(
                "customer_id",
                "customer__code",
                "customer__name",
                "customer__kind",
            )
            .annotate(amount=Sum("amount_uzs"), paid=Sum("paid_amount_uzs"))
        )

        for row in ar_qs:
            cp_id = row["customer_id"]
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
                    "code": row["customer__code"],
                    "name": row["customer__name"],
                    "kind": row["customer__kind"],
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

    @action(detail=True, methods=["post"], url_path="notify-debt")
    def notify_debt(self, request, pk=None):
        """POST /api/counterparties/{id}/notify-debt/

        body: {"channels": ["sms", "tg"]} — выбор каналов уведомления.
        Возвращает по каждому каналу: успех/ошибка + текстовый detail
        для UI ("у клиента нет телефона", "Eskiz отказал", и т.п.).

        Безопасно к повторному вызову — каждый зов плодит новую запись
        в SmsMessage/TgMessage (это и есть audit trail).
        """
        from .services.notify import notify_counterparty_debt

        cp = self.get_object()
        raw = request.data.get("channels") or []
        if not isinstance(raw, list):
            return Response(
                {"detail": "channels должен быть массивом."},
                status=400,
            )
        channels = [str(c).lower() for c in raw if c in ("sms", "tg")]
        if not channels:
            return Response(
                {"detail": "Укажите хотя бы один канал: sms или tg."},
                status=400,
            )

        result = notify_counterparty_debt(
            counterparty=cp,
            organization=request.organization,
            channels=channels,
            sender_user=request.user,
        )
        return Response(result.to_dict())

    @action(detail=True, methods=["post"], url_path="invite-tg")
    def invite_tg(self, request, pk=None):
        """POST /api/counterparties/{id}/invite-tg/

        Генерит одноразовый TgLinkToken, формирует deep-link и шлёт SMS
        с приглашением (узбекская латиница, чтобы Eskiz не считал
        кириллицу как 2 байта/символ — экономия 3× по стоимости).
        """
        from .services.notify import invite_counterparty_to_tg

        cp = self.get_object()
        res = invite_counterparty_to_tg(
            counterparty=cp,
            organization=request.organization,
            sender_user=request.user,
        )
        return Response({
            "channel": res.channel,
            "ok": res.ok,
            "detail": res.detail,
            "record_id": res.record_id,
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

    @action(detail=True, methods=["get"], url_path="full_summary")
    def full_summary(self, request, pk=None):
        """GET /api/counterparties/{id}/full_summary/

        Полная сводка для детальной страницы:
          - всё что в debt_summary
          - all_orders: вся история документов (SaleOrder + PurchaseOrder, любой статус)
          - all_payments: вся история платежей (Payment, любой direction/kind)
          - monthly_turnover: помесячная агрегация выручки/закупок за 12 мес
        """
        cp = self.get_object()
        org = request.organization
        base = _build_debt_summary(cp, org)
        base.update(_build_extended_summary(cp, org))
        return Response(base)
