"""
Тесты для compute_diff.

snapshot_model — это тонкий wrapper над `_meta.get_fields()` + сериализация,
проверять его на конкретной модели бессмысленно (зависит от мутирующего
prod-окружения). Сериализация Decimal/UUID/datetime покрывается через
direct `_serialize`.
"""
from __future__ import annotations

import datetime
import decimal
import uuid

from apps.audit.services.diff import _serialize, compute_diff


def test_compute_diff_empty_when_no_changes():
    assert compute_diff({"a": 1, "b": 2}, {"a": 1, "b": 2}) == {}


def test_compute_diff_reports_only_changed_fields():
    before = {"status": "DRAFT", "amount": "0", "name": "X"}
    after = {"status": "CONFIRMED", "amount": "100", "name": "X"}
    diff = compute_diff(before, after)
    assert diff == {
        "status": {"before": "DRAFT", "after": "CONFIRMED"},
        "amount": {"before": "0", "after": "100"},
    }


def test_compute_diff_create_marker():
    diff = compute_diff(None, {"status": "DRAFT"})
    assert diff == {"_created": {"status": "DRAFT"}}


def test_compute_diff_delete_marker():
    diff = compute_diff({"status": "DRAFT"}, None)
    assert diff == {"_deleted": {"status": "DRAFT"}}


def test_compute_diff_handles_added_and_removed_keys():
    before = {"a": 1}
    after = {"b": 2}
    diff = compute_diff(before, after)
    assert diff == {
        "a": {"before": 1, "after": None},
        "b": {"before": None, "after": 2},
    }


def test_serialize_primitives_passthrough():
    assert _serialize(None) is None
    assert _serialize(True) is True
    assert _serialize(42) == 42
    assert _serialize(3.14) == 3.14
    assert _serialize("x") == "x"


def test_serialize_decimal_to_string():
    assert _serialize(decimal.Decimal("100.50")) == "100.50"


def test_serialize_uuid_to_string():
    u = uuid.uuid4()
    assert _serialize(u) == str(u)


def test_serialize_datetime_isoformat():
    dt = datetime.datetime(2026, 5, 17, 12, 30, 45)
    assert _serialize(dt) == "2026-05-17T12:30:45"

    d = datetime.date(2026, 5, 17)
    assert _serialize(d) == "2026-05-17"


def test_compute_diff_decimal_string_comparison():
    # snapshot_model сериализует Decimal в str — diff не должен ложно
    # срабатывать на эквивалентных числах в разной форме внутри одного
    # снапшота (мы всегда сравниваем str к str).
    before = {"price": str(decimal.Decimal("100.00"))}
    after = {"price": str(decimal.Decimal("100.00"))}
    assert compute_diff(before, after) == {}

    after_changed = {"price": str(decimal.Decimal("150.00"))}
    assert compute_diff(before, after_changed) == {
        "price": {"before": "100.00", "after": "150.00"}
    }
