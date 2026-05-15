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

from apps.common.permissions import can_see_finances, get_user_readable_module_codes
from apps.common.viewsets import OrganizationContextMixin

from .services import (
    ar_summary,
    cash_balances,
    cashflow_chart,
    kpi_summary,
    module_cash_balances,
    production_summary,
)


# Финансовые KPI — скрываются если у юзера нет ledger.r
_FINANCIAL_KPI_KEYS = (
    "purchases_confirmed_uzs",
    "purchases_paid_uzs",
    "creditor_balance_uzs",
    "debtor_balance_uzs",
    "payments_in_uzs",
    "payments_out_uzs",
    "sales_revenue_uzs",
    "sales_invoiced_uzs",
    "sales_unpaid_uzs",
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
        # Superusers see everything including finances; RBAC applies to everyone else.
        finances_visible = request.user.is_superuser or can_see_finances(request.user, org)

        # membership is guaranteed non-None here: OrganizationContextMixin raises
        # 403 before get() is called when membership cannot be resolved.
        membership = request.membership
        if request.user.is_superuser:
            readable_modules = None  # unlimited: superuser bypasses module-level RBAC
        else:
            readable_modules = get_user_readable_module_codes(membership)

        kpis = kpi_summary(org, readable_modules=readable_modules)
        if not finances_visible:
            kpis = _strip_financial_kpis(kpis)

        return Response({
            "kpis": kpis,
            "production": production_summary(org, readable_modules=readable_modules),
            "cash": cash_balances(org) if finances_visible else None,
            "ar": ar_summary(org) if finances_visible else None,
            # Per-module kassa balances — visible to anyone who can read that module.
            # Finance role sees all modules; production roles see only their own.
            "module_kassas": module_cash_balances(org, readable_modules=readable_modules),
            "_finances_visible": finances_visible,
        })


class DashboardArSummaryView(OrganizationContextMixin, APIView):
    """
    GET /api/dashboard/ar-summary/[?dso_window=90]

    Снимок дебиторки для виджета на /dashboard и страницы /reports:
    aging buckets, DSO, top-3 должников. Только для ledger.r+.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not can_see_finances(request.user, request.organization):
            return Response(
                {"detail": "Нет доступа к финансовым отчётам организации."},
                status=403,
            )
        try:
            window = int(request.query_params.get("dso_window", "90"))
        except ValueError:
            window = 90
        window = max(7, min(window, 365))
        return Response(ar_summary(request.organization, days_for_dso=window))


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
