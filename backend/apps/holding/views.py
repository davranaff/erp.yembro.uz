"""
Эндпоинт холдинговой консолидации.

`GET /api/holding/companies/?period_from=YYYY-MM-DD&period_to=YYYY-MM-DD`

Возвращает массив компаний пользователя с агрегатами + сводные KPI.
НЕ требует X-Organization-Code (наоборот — показывает данные по всем
доступным организациям).
"""
from __future__ import annotations

from datetime import date

from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.models import Organization

from .services import consolidate, total_kpis


def _parse_date(s):
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError as exc:
        raise DRFValidationError({"detail": f"Некорректная дата: {s} ({exc})"})


class HoldingCompaniesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        d_from = _parse_date(request.query_params.get("period_from"))
        d_to = _parse_date(request.query_params.get("period_to"))

        orgs = (
            Organization.objects.filter(
                memberships__user=request.user,
                memberships__is_active=True,
                is_active=True,
            )
            .select_related("accounting_currency")
            .order_by("code")
            .distinct()
        )

        rows = consolidate(orgs, period_from=d_from, period_to=d_to)
        return Response({
            "companies": [r.to_dict() for r in rows],
            "totals": total_kpis(rows),
        })
