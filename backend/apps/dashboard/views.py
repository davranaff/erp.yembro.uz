"""
Эндпоинты главной страницы (Dashboard).

Требуют X-Organization-Code (агрегаты — в контексте конкретной orgа).
"""
from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.viewsets import OrganizationContextMixin

from .services import (
    cash_balances,
    cashflow_chart,
    kpi_summary,
    production_summary,
)


class DashboardSummaryView(OrganizationContextMixin, APIView):
    """
    GET /api/dashboard/summary/
    Сводный KPI: финансы + производство + ожидающие передачи.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        org = request.organization
        return Response({
            "kpis": kpi_summary(org),
            "production": production_summary(org),
            "cash": cash_balances(org),
        })


class DashboardCashflowView(OrganizationContextMixin, APIView):
    """
    GET /api/dashboard/cashflow/?days=30
    Кэш-флоу по дням за период.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            days = int(request.query_params.get("days", "30"))
        except ValueError:
            days = 30
        days = max(1, min(days, 365))
        return Response({
            "days": days,
            "points": cashflow_chart(request.organization, days=days),
        })
