"""
Тесты cancel_production_task.
"""
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.feed.models import ProductionTask, Recipe, RecipeVersion
from apps.feed.services.cancel_task import cancel_production_task
from apps.modules.models import Module
from apps.organizations.models import Organization
from apps.users.models import User
from apps.warehouses.models import ProductionBlock


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_feed():
    return Module.objects.get(code="feed")


@pytest.fixture
def user():
    return User.objects.create(email="f@y.local", full_name="F")


@pytest.fixture
def recipe(org):
    return Recipe.objects.create(
        organization=org, code="БР-С-01", name="Старт",
        direction="broiler", is_medicated=False,
    )


@pytest.fixture
def rv(recipe):
    from datetime import date
    return RecipeVersion.objects.create(
        recipe=recipe, version_number=1, status=RecipeVersion.Status.ACTIVE,
        effective_from=date(2026, 1, 1),
    )


@pytest.fixture
def line(org, m_feed):
    return ProductionBlock.objects.create(
        organization=org, module=m_feed, code="ЛН-1",
        name="Линия", kind=ProductionBlock.Kind.MIXER_LINE,
    )


@pytest.fixture
def task(org, m_feed, rv, line, user):
    return ProductionTask.objects.create(
        organization=org, module=m_feed, doc_number="ПЗ-001",
        recipe_version=rv, production_line=line,
        scheduled_at=datetime(2026, 4, 24, 8, 0, tzinfo=timezone.utc),
        planned_quantity_kg=Decimal("1000"),
        status=ProductionTask.Status.PLANNED,
        technologist=user,
    )


def test_cancel_planned_task(task):
    result = cancel_production_task(task, reason="ошибка")
    assert result.task.status == ProductionTask.Status.CANCELLED


def test_cancel_running_raises(task):
    task.status = ProductionTask.Status.RUNNING
    task.save()
    with pytest.raises(ValidationError):
        cancel_production_task(task)


def test_cancel_done_raises(task):
    task.status = ProductionTask.Status.DONE
    task.save()
    with pytest.raises(ValidationError):
        cancel_production_task(task)


def test_cancel_paused_ok(task):
    task.status = ProductionTask.Status.PAUSED
    task.save()
    result = cancel_production_task(task, reason="поломка")
    assert result.task.status == ProductionTask.Status.CANCELLED
