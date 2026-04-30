"""
Создаёт периодическую задачу Celery Beat `incubation-kpi-alerts` —
ежедневно в 19:00 Asia/Tashkent (после feedlot KPI 18:00).

Алертит когда hatchability партии, закрытой за последние 24 часа, ниже
порога `INCUBATION_HATCH_RATE_ALERT_PCT` (default 80%).
"""
import json

from django.db import migrations


CRONTAB = {
    "minute": "0",
    "hour": "19",
    "day_of_week": "*",
    "day_of_month": "*",
    "month_of_year": "*",
    "timezone": "Asia/Tashkent",
}

TASK_NAME = "incubation-kpi-alerts"
TASK_PATH = "apps.incubation.kpi_alerts_task"


def seed(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    schedule, _ = CrontabSchedule.objects.get_or_create(**CRONTAB)
    PeriodicTask.objects.update_or_create(
        name=TASK_NAME,
        defaults={
            "crontab": schedule,
            "task": TASK_PATH,
            "args": json.dumps([]),
            "kwargs": json.dumps({}),
            "enabled": True,
            "description": (
                "Каждый вечер 19:00 проверяет партии инкубации, закрытые за "
                "последние 24ч, и шлёт TG-алерт если hatch rate ниже порога."
            ),
        },
    )


def remove(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name=TASK_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("incubation", "0002_business_logic_fixes"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(seed, remove),
    ]
