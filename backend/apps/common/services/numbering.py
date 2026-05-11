"""
Универсальный генератор doc_number для любых документов с форматом
`{PREFIX}-{YYYY}-{NNNNN}`, per (organization, year).

Используется покупками (ЗК), проводками (ПР), стоковыми движениями (СД),
платежами (ПЛ), межмодульными передачами (ММ), партиями (П) и т.д.
"""
import hashlib
import re
from datetime import date
from typing import Type

from django.db import connection, models, transaction


_NUMBER_REGEX_TEMPLATE = r"^{prefix}-{year}-(\d+)$"


def _series_lock_key(organization_pk, prefix: str, year: int) -> int:
    """64-битный signed int для pg_advisory_xact_lock из строки серии."""
    raw = f"docnum:{organization_pk}:{prefix}:{year}"
    digest = hashlib.blake2b(raw.encode("utf-8"), digest_size=8).digest()
    val = int.from_bytes(digest, "big", signed=False)
    # привести к диапазону bigint (signed 64-bit)
    if val >= 2 ** 63:
        val -= 2 ** 64
    return val


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

    Реализация:
      - regex-скан существующих + max+1.
      - сериализация конкурентных вычислений через pg_advisory_xact_lock
        на ключ (organization, prefix, year). Lock держится до конца
        текущей транзакции, поэтому функция должна вызываться внутри
        atomic-блока. Если транзакции нет — лок не берётся (best-effort),
        и единственной защитой остаётся unique_together в модели.
    """
    target_date = on_date or date.today()
    year = target_date.year
    regex = _NUMBER_REGEX_TEMPLATE.format(prefix=re.escape(prefix), year=year)

    # Advisory lock — только PostgreSQL и только если мы в транзакции
    # (xact-лок без транзакции бесполезен и сбрасывается мгновенно).
    if connection.vendor == "postgresql" and not transaction.get_autocommit():
        lock_key = _series_lock_key(organization.pk, prefix, year)
        with connection.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s)", [lock_key])

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
