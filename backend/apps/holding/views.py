"""
Эндпоинт холдинговой консолидации.

`GET /api/holding/companies/?period_from=YYYY-MM-DD&period_to=YYYY-MM-DD`

Возвращает массив компаний пользователя с агрегатами + сводные KPI.
НЕ требует X-Organization-Code (наоборот — показывает данные по всем
доступным организациям).

Доступ: только для пользователей с `ledger.r` хотя бы в одной из своих
организаций. Производственные менеджеры (без финансового доступа) не
должны видеть консолидированные финансы холдинга.
"""
from __future__ import annotations

from datetime import date

from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import can_see_finances
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

        orgs = list(
            Organization.objects.filter(
                memberships__user=request.user,
                memberships__is_active=True,
                is_active=True,
            )
            .select_related("accounting_currency")
            .order_by("code")
            .distinct()
        )

        # Фильтруем — оставляем только организации, в которых у юзера есть
        # доступ к финансам. В отфильтрованной выборке показываем агрегаты.
        # Если нет ни одной — возвращаем 403.
        orgs_with_finance = [o for o in orgs if can_see_finances(request.user, o)]
        if not orgs_with_finance:
            return Response(
                {"detail": (
                    "Холдинговая консолидация доступна только пользователям с "
                    "финансовым доступом (`ledger.r`) хотя бы в одной организации."
                )},
                status=403,
            )

        rows = consolidate(orgs_with_finance, period_from=d_from, period_to=d_to)
        return Response({
            "companies": [r.to_dict() for r in rows],
            "totals": total_kpis(rows),
        })
