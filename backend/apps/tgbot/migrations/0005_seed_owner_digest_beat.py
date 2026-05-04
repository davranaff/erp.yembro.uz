"""
Beat-расписание: каждое утро 08:00 Asia/Tashkent — owner_digest_task.

Сводка за вчерашний день уходит во все admin-линки с digest_enabled=True.
Если digest нужно отключить per-user — есть команды /digest_off / /digest_on.
"""
import json

from django.db import migrations


SCHEDULE = {
    "name": "tgbot-owner-digest-daily",
    "task": "apps.tgbot.owner_digest_task",
    "description": (
        "Каждое утро 08:00 Asia/Tashkent — owner-digest всем admin-линкам "
        "с digest_enabled=True. Содержит вчерашнюю выручку/прибыль, остатки "
        "кассы, активные KPI-алерты."
    ),
    "crontab": {
        "minute": "0",
        "hour": "8",
        "day_of_week": "*",
        "day_of_month": "*",
        "month_of_year": "*",
        "timezone": "Asia/Tashkent",
    },
}


def seed(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    schedule, _ = CrontabSchedule.objects.get_or_create(**SCHEDULE["crontab"])
    PeriodicTask.objects.update_or_create(
        name=SCHEDULE["name"],
        defaults={
            "crontab": schedule,
            "task": SCHEDULE["task"],
            "args": json.dumps([]),
            "kwargs": json.dumps({}),
            "enabled": True,
            "description": SCHEDULE["description"],
        },
    )


def remove(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name=SCHEDULE["name"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("tgbot", "0004_tglink_digest_enabled"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(seed, remove),
    ]
