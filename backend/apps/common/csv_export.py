"""
Хелперы для CSV-экспорта в endpoint'ах отчётов.

Backwards-compatible: поддерживает оба способа триггера —
`?format=csv` query param или `Accept: text/csv` header.

Записывает BOM в начало для корректного открытия Excel'ом.
"""
from __future__ import annotations

import csv
from typing import Any, Iterable

from django.http import StreamingHttpResponse


def wants_csv(request) -> bool:
    fmt = request.query_params.get("format", "").lower()
    if fmt == "csv":
        return True
    return "text/csv" in request.headers.get("Accept", "")


class _Echo:
    """File-like для csv.writer — возвращает записанное вместо буферизации."""

    def write(self, value):  # noqa: D401
        return value


def stream_csv(
    filename: str,
    header: list[str],
    rows: Iterable[list[Any]],
) -> StreamingHttpResponse:
    """Стримит CSV: BOM + header + rows. Памяти не ест на больших отчётах."""
    pseudo = _Echo()
    writer = csv.writer(pseudo, delimiter=",", quoting=csv.QUOTE_MINIMAL)

    def gen():
        yield "﻿"  # BOM для Excel
        yield writer.writerow(header)
        for r in rows:
            yield writer.writerow(r)

    response = StreamingHttpResponse(gen(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
