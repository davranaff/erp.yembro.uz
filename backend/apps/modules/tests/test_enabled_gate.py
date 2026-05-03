"""Тесты org-level module enable/disable gate.

Покрывают:
  - disable feed → GET /api/feed/raw-batches/ → 403 {"code": "module_disabled"}
  - row absent → endpoint всё равно 200 (back-compat default-allow)
  - cannot disable admin / ledger / core (PATCH → 400)
  - даже после disable всех — /api/organization-modules/ всё ещё 200
    (модуль сам на admin, который защищён)
  - per-request cache: 5 GET-ов → 1 SQL на OrganizationModule
"""
from datetime import date
from decimal import Decimal

import pytest
from django.test.utils import CaptureQueriesContext
from django.db import connection
from rest_framework.test import APIClient

from apps.counterparties.models import Counterparty
from apps.feed.models import RawMaterialBatch
from apps.modules.models import Module, OrganizationModule
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization, OrganizationMembership
from apps.rbac.models import AccessLevel, UserModuleAccessOverride
from apps.users.models import User
from apps.warehouses.models import Warehouse


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_feed():
    return Module.objects.get(code="feed")


@pytest.fixture
def m_admin():
    return Module.objects.get(code="admin")


@pytest.fixture
def feed_user(org, m_feed, m_admin):
    """Юзер с feed.r и admin.admin — может дёргать feed-ендпоинты И toggle модулей."""
    u = User.objects.create(email="gate@y.local", full_name="Gate")
    membership = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True,
    )
    UserModuleAccessOverride.objects.create(
        membership=membership, module=m_feed, level=AccessLevel.READ,
    )
    UserModuleAccessOverride.objects.create(
        membership=membership, module=m_admin, level=AccessLevel.ADMIN,
    )
    return u


def _client(user):
    api = APIClient()
    api.force_authenticate(user=user)
    api.credentials(HTTP_X_ORGANIZATION_CODE="DEFAULT")
    return api


# ─── Disable → 403 ──────────────────────────────────────────────────────


def test_disabled_module_returns_403_with_code(org, m_feed, feed_user):
    """Отключаем feed → юзер с feed.r получает 403 + код module_disabled."""
    OrganizationModule.objects.update_or_create(
        organization=org, module=m_feed, defaults={"is_enabled": False},
    )
    api = _client(feed_user)
    resp = api.get("/api/feed/raw-batches/")
    assert resp.status_code == 403
    body = resp.json()
    assert body.get("code") == "module_disabled"
    assert "отключ" in body.get("detail", "").lower()


def test_row_absent_defaults_to_enabled(org, m_feed, feed_user):
    """Если OrganizationModule для feed нет — endpoint должен пускать (back-compat)."""
    OrganizationModule.objects.filter(organization=org, module=m_feed).delete()
    api = _client(feed_user)
    resp = api.get("/api/feed/raw-batches/")
    assert resp.status_code == 200


def test_enabled_module_returns_200(org, m_feed, feed_user):
    """Sanity-check: явно включён → endpoint работает."""
    OrganizationModule.objects.update_or_create(
        organization=org, module=m_feed, defaults={"is_enabled": True},
    )
    api = _client(feed_user)
    resp = api.get("/api/feed/raw-batches/")
    assert resp.status_code == 200


# ─── Cannot disable system modules ──────────────────────────────────────


@pytest.mark.parametrize("system_code", ["admin", "ledger", "core"])
def test_cannot_disable_system_modules(org, feed_user, system_code):
    """PATCH is_enabled=false для admin/ledger/core → 400."""
    sys_mod = Module.objects.get(code=system_code)
    om, _ = OrganizationModule.objects.update_or_create(
        organization=org, module=sys_mod, defaults={"is_enabled": True},
    )
    api = _client(feed_user)
    resp = api.patch(
        f"/api/organization-modules/{om.id}/",
        {"is_enabled": False},
        format="json",
    )
    assert resp.status_code == 400, resp.content
    body = resp.json()
    assert "is_enabled" in body
    # is_enabled в БД не изменилось
    om.refresh_from_db()
    assert om.is_enabled is True


def test_disable_does_not_block_settings_endpoint(org, m_admin, feed_user):
    """admin защищён → /api/organization-modules/ доступен даже если попытаться отключить."""
    # admin реально не отключится (см. тест выше), но даже если бы — проверим
    # что _disabled_module_codes исключает SYSTEM_MODULES.
    # Имитируем: ставим в БД is_enabled=False напрямую (минуя API guard).
    OrganizationModule.objects.update_or_create(
        organization=org, module=m_admin, defaults={"is_enabled": False},
    )
    api = _client(feed_user)
    resp = api.get("/api/organization-modules/")
    assert resp.status_code == 200, resp.content


# ─── Per-request cache ──────────────────────────────────────────────────


def test_per_request_cache_one_query_for_disabled_set(
    org, m_feed, feed_user,
):
    """Несколько вызовов has_permission в рамках одного request → 1 SQL.

    Проверяем напрямую через хелпер: cache на request.
    """
    from apps.common.permissions import _disabled_module_codes

    OrganizationModule.objects.update_or_create(
        organization=org, module=m_feed, defaults={"is_enabled": False},
    )

    class FakeRequest:
        pass

    req = FakeRequest()
    req.organization = org

    with CaptureQueriesContext(connection) as ctx:
        for _ in range(5):
            result = _disabled_module_codes(req)
        # Первый вызов делает 1 SELECT на OrganizationModule, остальные —
        # из request._disabled_modules_cache.
        org_module_queries = [
            q for q in ctx.captured_queries
            if "modules_organizationmodule" in q["sql"].lower()
        ]
    assert len(org_module_queries) == 1
    assert "feed" in result


# ─── is_module_enabled_for_org helper (для celery tasks) ────────────────


def test_is_module_enabled_for_org_default_allow(org, m_feed):
    """Если строки нет — модуль считается включённым (back-compat)."""
    from apps.common.permissions import is_module_enabled_for_org

    OrganizationModule.objects.filter(organization=org, module=m_feed).delete()
    assert is_module_enabled_for_org(org, "feed") is True


def test_is_module_enabled_for_org_respects_disabled(org, m_feed):
    from apps.common.permissions import is_module_enabled_for_org

    OrganizationModule.objects.update_or_create(
        organization=org, module=m_feed, defaults={"is_enabled": False},
    )
    assert is_module_enabled_for_org(org, "feed") is False


def test_is_module_enabled_for_org_system_always_true(org, m_admin):
    """Системные модули всегда True даже если в БД is_enabled=False."""
    from apps.common.permissions import is_module_enabled_for_org

    OrganizationModule.objects.update_or_create(
        organization=org, module=m_admin, defaults={"is_enabled": False},
    )
    assert is_module_enabled_for_org(org, "admin") is True
    assert is_module_enabled_for_org(org, "ledger") is True
    assert is_module_enabled_for_org(org, "core") is True


# ─── Celery beat tasks: skip disabled orgs ──────────────────────────────


def test_feed_shrinkage_task_skips_disabled_org(org, m_feed):
    """apply_feed_shrinkage_task видит org с feed=disabled → пропускает."""
    from apps.feed.tasks import apply_feed_shrinkage_task

    OrganizationModule.objects.update_or_create(
        organization=org, module=m_feed, defaults={"is_enabled": False},
    )
    result = apply_feed_shrinkage_task()
    org_result = result["per_org"].get(str(org.id))
    assert org_result == {"skipped": "module_disabled"}


def test_feedlot_kpi_alerts_task_skips_disabled_org(org):
    """feedlot.kpi_alerts_task: org с feedlot=disabled → не считается."""
    from unittest.mock import patch
    from apps.feedlot.tasks import kpi_alerts_task

    m_feedlot = Module.objects.get(code="feedlot")
    OrganizationModule.objects.update_or_create(
        organization=org, module=m_feedlot, defaults={"is_enabled": False},
    )
    with patch("apps.tgbot.tasks.notify_admins_task.delay") as notify:
        result = kpi_alerts_task()
    # этой org нет в checked_orgs (всех активных орг = 1)
    assert result["checked_orgs"] == 0
    notify.assert_not_called()


def test_matochnik_daily_log_check_skips_disabled_org(org):
    """matочник.daily_log_check_task: matочник=disabled → пропуск."""
    from unittest.mock import patch
    from apps.matochnik.tasks import daily_log_check_task

    m_mat = Module.objects.get(code="matochnik")
    OrganizationModule.objects.update_or_create(
        organization=org, module=m_mat, defaults={"is_enabled": False},
    )
    with patch("apps.tgbot.tasks.notify_admins_task.delay") as notify:
        result = daily_log_check_task()
    assert result["checked_orgs"] == 0
    notify.assert_not_called()


def test_incubation_kpi_alerts_skips_disabled_org(org):
    from unittest.mock import patch
    from apps.incubation.tasks import kpi_alerts_task

    m_inc = Module.objects.get(code="incubation")
    OrganizationModule.objects.update_or_create(
        organization=org, module=m_inc, defaults={"is_enabled": False},
    )
    with patch("apps.tgbot.tasks.notify_admins_task.delay") as notify:
        result = kpi_alerts_task()
    assert result["checked_orgs"] == 0
    notify.assert_not_called()
