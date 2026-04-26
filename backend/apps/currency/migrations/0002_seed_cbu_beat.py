"""
Создать периодическую задачу Celery Beat `cbu-daily-sync` — ежедневно в
10:00 Asia/Tashkent. CBU обновляет курсы около 09:00, буфер 1 час.
"""
import json

from django.db import migrations


CRONTAB_PARAMS = {
    "minute": "0",
    "hour": "10",
    "day_of_week": "*",
    "day_of_month": "*",
    "month_of_year": "*",
    "timezone": "Asia/Tashkent",
}

TASK_NAME = "cbu-daily-sync"
TASK_PATH = "apps.currency.sync_cbu_rates"


def seed_schedule(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    schedule, _ = CrontabSchedule.objects.get_or_create(**CRONTAB_PARAMS)

    PeriodicTask.objects.update_or_create(
        name=TASK_NAME,
        defaults={
            "crontab": schedule,
            "task": TASK_PATH,
            "args": json.dumps([]),
            "kwargs": json.dumps({}),
            "enabled": True,
            "description": "Ежедневный импорт курсов валют с cbu.uz.",
        },
    )


def remove_schedule(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name=TASK_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("currency", "0001_initial"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(seed_schedule, remove_schedule),
    ]
