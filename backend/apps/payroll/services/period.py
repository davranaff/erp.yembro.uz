"""
PayrollPeriod: проверка что дата не попадает в закрытый период.
"""
from __future__ import annotations

from datetime import date

from django.core.exceptions import ValidationError

from ..models import PayrollPeriod


def assert_date_open(organization, target: date, *, field_label: str = "date") -> None:
    """
    Если для organization есть PayrollPeriod(status=closed) куда попадает target —
    raise ValidationError.
    """
    locked = PayrollPeriod.objects.filter(
        organization=organization,
        status=PayrollPeriod.Status.CLOSED,
        period_from__lte=target,
        period_to__gte=target,
    ).first()
    if locked is not None:
        raise ValidationError({
            field_label: (
                f"Период {locked.period_from}..{locked.period_to} закрыт. "
                "Сначала переоткройте его."
            ),
        })
