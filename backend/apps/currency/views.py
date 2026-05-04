from datetime import date as date_cls

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import OuterRef, Subquery
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from apps.common.pagination import FlexiblePageNumberPagination

from .filters import ExchangeRateFilter
from .models import Currency, ExchangeRate, IntegrationSyncLog
from .selectors import get_rate_for
from .serializers import (
    CurrencySerializer,
    ExchangeRateSerializer,
    IntegrationSyncLogSerializer,
)
from .services.cbu import CBUFetchError, sync_cbu_rates


class CurrencyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Справочник валют (read-only). Глобальный, не требует X-Organization-Code.

    Пагинация отключена: валют всего ~80 (ЦБ Узбекистана), клиентский код
    использует этот endpoint как справочник — нужны все сразу в dropdown-ах.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = CurrencySerializer
    queryset = Currency.objects.all().order_by("code")
    filterset_fields = ("is_active",)
    search_fields = ("code", "name_ru", "name_en")
    lookup_field = "code"
    lookup_value_regex = "[A-Za-z]{3}"
    pagination_class = None


class ExchangeRateViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Курсы валют. Read-only. Глобальный.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = ExchangeRateSerializer
    queryset = ExchangeRate.objects.select_related("currency").order_by(
        "-date", "currency__code"
    )
    filterset_class = ExchangeRateFilter
    ordering_fields = ("date", "currency__code")
    ordering = ("-date",)
    pagination_class = FlexiblePageNumberPagination

    @action(detail=False, methods=["get"])
    def latest(self, request):
        """
        GET /api/currency/rates/latest/
        Последний курс по каждой активной валюте.
        """
        latest_subq = (
            ExchangeRate.objects.filter(currency=OuterRef("currency"))
            .order_by("-date")
            .values("id")[:1]
        )
        qs = (
            ExchangeRate.objects.filter(
                currency__is_active=True, id__in=Subquery(latest_subq)
            )
            .select_related("currency")
            .order_by("currency__code")
        )
        data = ExchangeRateSerializer(qs, many=True).data
        return Response(data)

    @action(detail=False, methods=["get"], url_path="on-date")
    def on_date(self, request):
        """
        GET /api/currency/rates/on-date/?currency=USD&date=2026-04-25
        Курс конкретной валюты на дату с fallback по `get_rate_for` (до 7
        дней назад). Используется фронтом при создании PO/SO/Payment когда
        нужен курс именно на дату документа, а не последний доступный.

        404 если курса нет даже в окне fallback.
        """
        code = (request.query_params.get("currency") or "").strip().upper()
        date_raw = (request.query_params.get("date") or "").strip()
        if not code or not date_raw:
            raise DRFValidationError(
                {"detail": "Нужны параметры currency=<CODE>&date=YYYY-MM-DD."}
            )
        try:
            target_date = date_cls.fromisoformat(date_raw)
        except ValueError as exc:
            raise DRFValidationError({"date": str(exc)})

        try:
            rate = get_rate_for(code, target_date)
        except DjangoValidationError as exc:
            return Response(
                {"detail": exc.message_dict if hasattr(exc, "message_dict") else exc.messages},
                status=404,
            )
        return Response(ExchangeRateSerializer(rate).data)

    @action(detail=False, methods=["post"], permission_classes=[IsAdminUser])
    def sync_now(self, request):
        """
        POST /api/currency/rates/sync_now/ — ручная синхронизация с cbu.uz.
        Только для админов. Пишет в IntegrationSyncLog по итогам.
        """
        try:
            result = sync_cbu_rates()
        except CBUFetchError as exc:
            IntegrationSyncLog.objects.create(
                provider="cbu.uz",
                status=IntegrationSyncLog.Status.FAILED,
                error_message=str(exc)[:500],
                triggered_by=getattr(request.user, "email", "") or "manual",
            )
            return Response({"detail": str(exc)}, status=502)

        IntegrationSyncLog.objects.create(
            provider="cbu.uz",
            status=IntegrationSyncLog.Status.SUCCESS,
            stats=result.as_dict(),
            triggered_by=getattr(request.user, "email", "") or "manual",
        )
        return Response(result.as_dict())


class IntegrationSyncLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    /api/currency/sync-log/ — журнал попыток синхронизации (CBU и т.п.).
    Только для админов: используется для диагностики, когда курсы
    «застряли» на старой дате.
    """

    permission_classes = [IsAdminUser]
    serializer_class = IntegrationSyncLogSerializer
    queryset = IntegrationSyncLog.objects.all().order_by("-occurred_at")
    filterset_fields = ("provider", "status")
    pagination_class = FlexiblePageNumberPagination
