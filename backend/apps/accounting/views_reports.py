"""
Endpoint'ы бухгалтерских отчётов: ОСВ, GL ledger, P&L.

Все три:
- GET, без побочных эффектов
- требуют RBAC `accounting` read-доступ
- поддерживают `?format=csv` для экспорта (через `Accept: text/csv` или query param)
"""
from __future__ import annotations

import csv
from datetime import date as date_cls
from decimal import Decimal
from typing import Any

from django.http import StreamingHttpResponse
from rest_framework import permissions
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import HasModulePermission
from apps.common.viewsets import OrganizationContextMixin

from .models import GLSubaccount
from .services.reports import (
    compute_gl_ledger,
    compute_pl_report,
    compute_trial_balance,
)


# ─── Helpers ─────────────────────────────────────────────────────


def _parse_date(value: str | None, *, name: str) -> date_cls:
    if not value:
        raise DRFValidationError({name: "Параметр обязателен (YYYY-MM-DD)."})
    try:
        return date_cls.fromisoformat(value)
    except ValueError as exc:
        raise DRFValidationError({name: f"Некорректная дата: {exc}"})


def _wants_csv(request) -> bool:
    fmt = request.query_params.get("format", "").lower()
    if fmt == "csv":
        return True
    return "text/csv" in request.headers.get("Accept", "")


class _Echo:
    """File-like объект для StreamingHttpResponse — просто возвращает то что записали."""
    def write(self, value):
        return value


def _stream_csv(filename: str, header: list[str], rows: list[list[Any]]) -> StreamingHttpResponse:
    pseudo = _Echo()
    writer = csv.writer(pseudo, delimiter=",", quoting=csv.QUOTE_MINIMAL)

    def gen():
        # BOM для Excel
        yield "﻿"
        yield writer.writerow(header)
        for r in rows:
            yield writer.writerow(r)

    response = StreamingHttpResponse(gen(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _decimal_str(v: Decimal | None) -> str:
    if v is None:
        return ""
    return f"{v:.2f}"


# ─── Common permission ──────────────────────────────────────────


class _AccountingReadView(OrganizationContextMixin, APIView):
    """Базовый класс для отчётов — требует RBAC ledger.r + org-контекст."""
    permission_classes = [permissions.IsAuthenticated, HasModulePermission]
    module_code = "ledger"
    required_level = "r"
    write_level = "rw"


# ─── Trial Balance ──────────────────────────────────────────────


class TrialBalanceView(_AccountingReadView):
    """
    GET /api/accounting/reports/trial-balance/
        ?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD
        &module_code=feedlot (optional)
        &include_zeros=true (optional, default false)
        &format=csv (optional)
    """

    def get(self, request):
        date_from = _parse_date(request.query_params.get("date_from"), name="date_from")
        date_to = _parse_date(request.query_params.get("date_to"), name="date_to")
        module_code = request.query_params.get("module_code") or None
        include_zeros = request.query_params.get("include_zeros", "").lower() == "true"

        rows = compute_trial_balance(
            request.organization,
            date_from=date_from,
            date_to=date_to,
            module_code=module_code,
            include_zeros=include_zeros,
        )

        if _wants_csv(request):
            header = [
                "Счёт", "Субсчёт", "Название", "Тип", "Модуль",
                "Нач. остаток", "Оборот Дт", "Оборот Кт", "Кон. остаток",
            ]
            data_rows = [
                [
                    r.account_code, r.subaccount_code, r.subaccount_name,
                    r.account_type, r.module_code or "",
                    _decimal_str(r.opening_balance),
                    _decimal_str(r.debit_turnover),
                    _decimal_str(r.credit_turnover),
                    _decimal_str(r.closing_balance),
                ]
                for r in rows
            ]
            return _stream_csv(
                f"trial-balance-{date_from}-{date_to}.csv",
                header, data_rows,
            )

        return Response({
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "module_code": module_code,
            "rows": [
                {
                    "subaccount_id": r.subaccount_id,
                    "subaccount_code": r.subaccount_code,
                    "subaccount_name": r.subaccount_name,
                    "account_code": r.account_code,
                    "account_name": r.account_name,
                    "account_type": r.account_type,
                    "module_code": r.module_code,
                    "opening_balance": str(r.opening_balance),
                    "debit_turnover": str(r.debit_turnover),
                    "credit_turnover": str(r.credit_turnover),
                    "closing_balance": str(r.closing_balance),
                }
                for r in rows
            ],
        })


# ─── GL Ledger ──────────────────────────────────────────────────


class GlLedgerView(_AccountingReadView):
    """
    GET /api/accounting/reports/gl-ledger/
        ?subaccount=<uuid>&date_from=&date_to=&format=csv
    """

    def get(self, request):
        subaccount_id = request.query_params.get("subaccount")
        if not subaccount_id:
            raise DRFValidationError({"subaccount": "Обязательно."})

        try:
            sub = (
                GLSubaccount.objects
                .select_related("account")
                .get(id=subaccount_id, account__organization=request.organization)
            )
        except GLSubaccount.DoesNotExist:
            raise DRFValidationError({"subaccount": "Не найден."})

        date_from = _parse_date(request.query_params.get("date_from"), name="date_from")
        date_to = _parse_date(request.query_params.get("date_to"), name="date_to")

        result = compute_gl_ledger(
            request.organization, sub,
            date_from=date_from, date_to=date_to,
        )

        if _wants_csv(request):
            header = [
                "Дата", "Документ", "Описание",
                "Дебет", "Кредит", "Остаток",
                "Контрагент", "Модуль",
            ]
            data_rows = [[
                f"Сальдо на {date_from}", "", "",
                "", "", _decimal_str(result.opening_balance), "", "",
            ]]
            for e in result.entries:
                data_rows.append([
                    e.entry_date, e.doc_number, e.description,
                    _decimal_str(e.debit_amount),
                    _decimal_str(e.credit_amount),
                    _decimal_str(e.running_balance),
                    e.counterparty_name or "",
                    e.module_code or "",
                ])
            data_rows.append([
                f"Сальдо на {date_to}", "", "",
                _decimal_str(result.total_debit),
                _decimal_str(result.total_credit),
                _decimal_str(result.closing_balance), "", "",
            ])
            return _stream_csv(
                f"gl-ledger-{result.subaccount_code}-{date_from}-{date_to}.csv",
                header, data_rows,
            )

        return Response({
            "subaccount_id": result.subaccount_id,
            "subaccount_code": result.subaccount_code,
            "subaccount_name": result.subaccount_name,
            "account_code": result.account_code,
            "account_name": result.account_name,
            "account_type": result.account_type,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "opening_balance": str(result.opening_balance),
            "closing_balance": str(result.closing_balance),
            "total_debit": str(result.total_debit),
            "total_credit": str(result.total_credit),
            "entries": [
                {
                    "entry_id": e.entry_id,
                    "doc_number": e.doc_number,
                    "entry_date": e.entry_date,
                    "description": e.description,
                    "debit_amount": str(e.debit_amount) if e.debit_amount is not None else None,
                    "credit_amount": str(e.credit_amount) if e.credit_amount is not None else None,
                    "running_balance": str(e.running_balance),
                    "counterparty_name": e.counterparty_name,
                    "module_code": e.module_code,
                }
                for e in result.entries
            ],
        })


# ─── P&L ────────────────────────────────────────────────────────


class PlReportView(_AccountingReadView):
    """
    GET /api/accounting/reports/pl/?date_from=&date_to=&format=csv
    """

    def get(self, request):
        date_from = _parse_date(request.query_params.get("date_from"), name="date_from")
        date_to = _parse_date(request.query_params.get("date_to"), name="date_to")

        result = compute_pl_report(
            request.organization,
            date_from=date_from, date_to=date_to,
        )

        if _wants_csv(request):
            header = ["Раздел", "Счёт", "Название", "Сумма", "По модулям"]
            data_rows = []
            for r in result.revenue:
                by_mod = " · ".join(f"{k}={v}" for k, v in r.by_module.items())
                data_rows.append([
                    "Доход", r.subaccount_code, r.subaccount_name,
                    _decimal_str(r.amount), by_mod,
                ])
            data_rows.append([
                "Σ Доходы", "", "", _decimal_str(result.total_revenue), "",
            ])
            for r in result.expense:
                by_mod = " · ".join(f"{k}={v}" for k, v in r.by_module.items())
                data_rows.append([
                    "Расход", r.subaccount_code, r.subaccount_name,
                    _decimal_str(r.amount), by_mod,
                ])
            data_rows.append([
                "Σ Расходы", "", "", _decimal_str(result.total_expense), "",
            ])
            data_rows.append([
                "Прибыль", "", "", _decimal_str(result.profit), "",
            ])
            return _stream_csv(
                f"pl-{date_from}-{date_to}.csv",
                header, data_rows,
            )

        return Response({
            "date_from": result.date_from,
            "date_to": result.date_to,
            "revenue": [
                {
                    "subaccount_id": r.subaccount_id,
                    "subaccount_code": r.subaccount_code,
                    "subaccount_name": r.subaccount_name,
                    "amount": str(r.amount),
                    "by_module": {k: str(v) for k, v in r.by_module.items()},
                }
                for r in result.revenue
            ],
            "expense": [
                {
                    "subaccount_id": r.subaccount_id,
                    "subaccount_code": r.subaccount_code,
                    "subaccount_name": r.subaccount_name,
                    "amount": str(r.amount),
                    "by_module": {k: str(v) for k, v in r.by_module.items()},
                }
                for r in result.expense
            ],
            "total_revenue": str(result.total_revenue),
            "total_expense": str(result.total_expense),
            "profit": str(result.profit),
        })
