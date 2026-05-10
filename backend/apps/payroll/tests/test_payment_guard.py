"""Гард: kind=salary через /api/payments/ запрещён."""
from datetime import date
from decimal import Decimal

import pytest

from apps.payments.models import Payment
from apps.payments.serializers import PaymentSerializer

pytestmark = pytest.mark.django_db


def test_serializer_blocks_salary_kind_without_context(org, cash_subaccount):
    data = {
        "doc_number": "ПЛ-2026-99999",
        "date": "2026-05-01",
        "direction": "out",
        "channel": "cash",
        "kind": "salary",
        "amount_uzs": "100000",
        "cash_subaccount": str(cash_subaccount.id),
    }
    ser = PaymentSerializer(data=data)
    assert not ser.is_valid()
    assert "kind" in ser.errors


def test_serializer_allows_salary_kind_from_payroll_service(org, cash_subaccount):
    data = {
        "doc_number": "ПЛ-2026-99998",
        "date": "2026-05-01",
        "direction": "out",
        "channel": "cash",
        "kind": "salary",
        "amount_uzs": "100000",
        "cash_subaccount": str(cash_subaccount.id),
    }
    ser = PaymentSerializer(data=data, context={"from_payroll_service": True})
    # is_valid может всё равно упасть на других полях (organization),
    # но kind не должен ругаться
    ser.is_valid()
    assert "kind" not in ser.errors
