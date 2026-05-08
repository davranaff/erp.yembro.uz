"""
TTL токена привязки TG: для user (сотрудника) — 30 минут (default),
для counterparty (контрагента) — 7 дней.

Контрагенту менеджер шлёт ссылку через WhatsApp/SMS — там нужна
длинная жизнь токена, иначе клиент не успеет привязать.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.counterparties.models import Counterparty
from apps.organizations.models import Organization, OrganizationMembership
from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def admin_user(org):
    u = User.objects.create(email="admin@y.local", full_name="Admin")
    OrganizationMembership.objects.create(user=u, organization=org, is_active=True)
    return u


@pytest.fixture
def api(admin_user, org):
    c = APIClient()
    c.force_authenticate(user=admin_user)
    c.credentials(HTTP_X_ORGANIZATION_CODE=org.code)
    return c


def test_user_token_lives_30_minutes(api):
    """Сотрудник создаёт токен для себя — TTL 30 минут (короткий, флоу
    интерактивный)."""
    before = timezone.now()
    resp = api.post("/api/tg/link-token/", {}, format="json")
    assert resp.status_code == 201, resp.content
    expires_at = timezone.datetime.fromisoformat(resp.json()["expires_at"])

    delta = expires_at - before
    # 30 минут ± погрешность на исполнение запроса
    assert timedelta(minutes=29) < delta < timedelta(minutes=31), delta


def test_counterparty_token_lives_one_week(api, org):
    """Токен для контрагента живёт 7 дней — менеджер успевает разослать
    клиенту через WhatsApp/SMS, тот не торопясь привязывает бота."""
    cp = Counterparty.objects.create(
        organization=org, code="CP-TTL", kind="buyer", name="Test Buyer",
    )
    before = timezone.now()
    resp = api.post(
        "/api/tg/link-token/", {"counterparty": str(cp.id)}, format="json",
    )
    assert resp.status_code == 201, resp.content
    expires_at = timezone.datetime.fromisoformat(resp.json()["expires_at"])

    delta = expires_at - before
    assert timedelta(days=6, hours=23, minutes=59) < delta < timedelta(days=7, minutes=1), delta
