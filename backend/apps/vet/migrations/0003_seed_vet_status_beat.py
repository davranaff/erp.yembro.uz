"""
Создать периодическую задачу Celery Beat `vet-auto-status` — ежедневно
в 03:00 Asia/Tashkent для авто-перевода статусов лотов препаратов
(AVAILABLE → EXPIRING_SOON → EXPIRED).
"""
import json

from django.db import migrations


CRONTAB_PARAMS = {
    "minute": "0",
    "hour": "3",
    "day_of_week": "*",
    "day_of_month": "*",
    "month_of_year": "*",
    "timezone": "Asia/Tashkent",
}

TASK_NAME = "vet-auto-status"
TASK_PATH = "apps.vet.auto_update_stock_status"


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
            "description": (
                "Ежедневный авто-перевод статусов вет-лотов: "
                "AVAILABLE → EXPIRING_SOON → EXPIRED по дате истечения."
            ),
        },
    )


def remove_schedule(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name=TASK_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("vet", "0002_sellerdevicetoken_and_more"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(seed_schedule, remove_schedule),
    ]
