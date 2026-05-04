"""
Создать периодическую задачу `tgbot-daily-collection-alerts` —
ежедневно в 09:15 Asia/Tashkent: TG-сводка владельцу/админам по
задачам сборщика дебиторки (эскалации + сорванные обещания + промахи
прогнозов). Шлётся только если есть «горячие» задачи.

Время — 09:15, на 15 минут позже debt-reminder-daily (09:00) — чтобы
не толкать оба message в один момент и owner успел увидеть отдельно.
"""
import json

from django.db import migrations


CRONTAB_PARAMS = {
    "minute": "15",
    "hour": "9",
    "day_of_week": "*",
    "day_of_month": "*",
    "month_of_year": "*",
    "timezone": "Asia/Tashkent",
}

TASK_NAME = "tgbot-daily-collection-alerts"
TASK_PATH = "apps.tgbot.daily_collection_alerts_task"


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
                "Ежедневная TG-сводка для админов sales по задачам "
                "сборщика долгов (эскалации, нарушенные обещания, прогнозы)."
            ),
        },
    )


def remove_schedule(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name=TASK_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("tgbot", "0005_seed_owner_digest_beat"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(seed_schedule, remove_schedule),
    ]
