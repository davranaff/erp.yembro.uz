"""
Эндпоинты главной страницы (Dashboard).

Требуют X-Organization-Code (агрегаты — в контексте конкретной orgа).

Финансовые KPI скрываются у пользователей без `ledger.r` (производственный
менеджер не должен видеть выручку/прибыль/AR/AP всей организации).
"""
from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import can_see_finances
from apps.common.viewsets import OrganizationContextMixin

from .services import (
    cash_balances,
    cashflow_chart,
    kpi_summary,
    production_summary,
)


# Финансовые KPI — скрываются если у юзера нет ledger.r
_FINANCIAL_KPI_KEYS = (
    "purchases_confirmed_uzs",
    "creditor_balance_uzs",
    "debtor_balance_uzs",
    "payments_in_uzs",
    "payments_out_uzs",
    "sales_revenue_uzs",
    "sales_cost_uzs",
    "sales_margin_uzs",
)


def _strip_financial_kpis(kpis: dict) -> dict:
    """Возвращает копию KPI с обнулёнными финансовыми ключами (None)."""
    return {k: (None if k in _FINANCIAL_KPI_KEYS else v) for k, v in kpis.items()}


class DashboardSummaryView(OrganizationContextMixin, APIView):
    """
    GET /api/dashboard/summary/
    Сводный KPI: финансы + производство + ожидающие передачи.

    Производственный менеджер (без `ledger.r`) видит только производственные
    показатели — финансовые KPI и кассы скрываются.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        org = request.organization
        finances_visible = can_see_finances(request.user, org)

        kpis = kpi_summary(org)
        if not finances_visible:
            kpis = _strip_financial_kpis(kpis)

        return Response({
            "kpis": kpis,
            "production": production_summary(org),
            "cash": cash_balances(org) if finances_visible else None,
            "_finances_visible": finances_visible,
        })


class DashboardCashflowView(OrganizationContextMixin, APIView):
    """
    GET /api/dashboard/cashflow/?days=30
    Кэш-флоу по дням за период.

    Только для пользователей с доступом к финансам — это сводные денежные
    потоки организации. Без `ledger.r` возвращает 403.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not can_see_finances(request.user, request.organization):
            return Response(
                {"detail": "Нет доступа к финансовым отчётам организации."},
                status=403,
            )
        try:
            days = int(request.query_params.get("days", "30"))
        except ValueError:
            days = 30
        days = max(1, min(days, 365))
        return Response({
            "days": days,
            "points": cashflow_chart(request.organization, days=days),
        })
