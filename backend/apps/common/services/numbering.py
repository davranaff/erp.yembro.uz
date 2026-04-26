"""
Универсальный генератор doc_number для любых документов с форматом
`{PREFIX}-{YYYY}-{NNNNN}`, per (organization, year).

Используется покупками (ЗК), проводками (ПР), стоковыми движениями (СД),
платежами (ПЛ), межмодульными передачами (ММ), партиями (П) и т.д.
"""
import re
from datetime import date
from typing import Type

from django.db import models


_NUMBER_REGEX_TEMPLATE = r"^{prefix}-{year}-(\d+)$"


def next_doc_number(
    model: Type[models.Model],
    *,
    organization,
    prefix: str,
    field: str = "doc_number",
    organization_field: str = "organization",
    on_date: date | None = None,
    width: int = 5,
) -> str:
    """
    Вернуть следующий свободный doc_number в серии `{prefix}-{year}-{NNNNN}`.

    Реализация: regex-скан существующих + max+1. `unique_together` в
    модели страхует от race при параллельных вставках.
    """
    target_date = on_date or date.today()
    year = target_date.year
    regex = _NUMBER_REGEX_TEMPLATE.format(prefix=re.escape(prefix), year=year)

    qs = model.objects.filter(
        **{organization_field: organization, f"{field}__regex": regex}
    ).values_list(field, flat=True)

    max_num = 0
    compiled = re.compile(regex)
    for val in qs:
        m = compiled.match(val or "")
        if m:
            n = int(m.group(1))
            if n > max_num:
                max_num = n

    return f"{prefix}-{year}-{(max_num + 1):0{width}d}"
