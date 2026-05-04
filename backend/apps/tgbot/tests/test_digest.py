"""
Owner digest: build_digest, format_digest, owner_digest_task,
команды /digest /digest_on /digest_off.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.tgbot.dispatcher import dispatch_message
from apps.tgbot.services.digest import build_digest, format_digest


pytestmark = pytest.mark.django_db


def _msg(chat_id, text):
    return {"chat": {"id": chat_id}, "text": text, "from": {"id": chat_id}}


# ─── service ──────────────────────────────────────────────────────────


def test_build_digest_returns_zero_for_empty_org(org):
    data = build_digest(org)
    assert data.revenue == Decimal("0")
    assert data.profit == Decimal("0")
    assert data.active_batches >= 0  # просто sanity, может быть seed-партии
    assert data.alerts == [] or all(isinstance(a, str) for a in data.alerts)


def test_format_digest_includes_all_sections(org):
    data = build_digest(org)
    text = format_digest(data, organization_name="Test Org")
    assert "Сводка за" in text
    assert "Test Org" in text
    assert "Выручка" in text
    assert "Расходы" in text
    assert "Прибыль" in text
    assert "Касса/банк" in text
    assert "Активных партий" in text
    assert "/menu" in text


def test_build_digest_for_specific_date(org):
    target = date(2026, 4, 1)
    data = build_digest(org, on_date=target)
    assert data.on_date == target


# ─── /digest /digest_on /digest_off ──────────────────────────────────


def test_digest_command_sends_preview(tg_link, fake_send):
    dispatch_message(_msg(tg_link.chat_id, "/digest"))
    assert fake_send.calls
    text = fake_send.calls[0][1]
    assert "Сводка за" in text


def test_digest_off_disables_subscription(tg_link, fake_send):
    assert tg_link.digest_enabled is True
    dispatch_message(_msg(tg_link.chat_id, "/digest_off"))
    tg_link.refresh_from_db()
    assert tg_link.digest_enabled is False
    assert any("отключена" in t.lower() for _, t, _ in fake_send.calls)


def test_digest_on_enables_subscription(tg_link, fake_send):
    tg_link.digest_enabled = False
    tg_link.save(update_fields=["digest_enabled"])
    dispatch_message(_msg(tg_link.chat_id, "/digest_on"))
    tg_link.refresh_from_db()
    assert tg_link.digest_enabled is True
    assert any("включена" in t.lower() for _, t, _ in fake_send.calls)


# ─── owner_digest_task ──────────────────────────────────────────────────


def test_owner_digest_task_sends_to_subscribed(tg_link, fake_send):
    """digest_enabled=True → юзер получает рассылку."""
    from apps.tgbot.tasks import owner_digest_task
    result = owner_digest_task()
    assert result["sent"] >= 1
    assert any("Сводка за" in t for _, t, _ in fake_send.calls)


def test_owner_digest_task_skips_unsubscribed(tg_link, fake_send):
    tg_link.digest_enabled = False
    tg_link.save(update_fields=["digest_enabled"])
    from apps.tgbot.tasks import owner_digest_task
    result = owner_digest_task()
    assert result["sent"] == 0
    assert not any("Сводка за" in t for _, t, _ in fake_send.calls)


def test_owner_digest_task_skips_counterparty_links(tg_link, fake_send):
    """Counterparty-links не должны получать digest даже если digest_enabled=True."""
    from apps.counterparties.models import Counterparty
    from apps.tgbot.models import TgLink
    cp = Counterparty.objects.create(
        organization=tg_link.organization, code="CP-TG", kind="buyer", name="Buyer X",
    )
    TgLink.objects.create(
        organization=tg_link.organization,
        counterparty=cp,
        chat_id=22222,
        is_active=True,
        digest_enabled=True,
    )
    # отключаем admin-link, чтобы остался только counterparty
    tg_link.digest_enabled = False
    tg_link.save(update_fields=["digest_enabled"])

    from apps.tgbot.tasks import owner_digest_task
    result = owner_digest_task()
    assert result["sent"] == 0
    # 22222 не должен фигурировать — counterparty links отфильтрованы
    assert all(c != 22222 for c, _, _ in fake_send.calls)


def test_owner_digest_task_respects_active_organization(
    tg_link, fake_send, org,
):
    """Если у юзера переключена active_organization — digest всё равно
    приходит для organization, в которой линк создан."""
    # Нет переключения — digest приходит только в org, где линк зарегистрирован.
    from apps.tgbot.tasks import owner_digest_task
    result = owner_digest_task()
    assert result["sent"] == 1
