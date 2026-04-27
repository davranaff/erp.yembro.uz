"""
Создать периодическую задачу Celery Beat `tgbot-debt-reminder-daily` —
ежедневно в 09:00 Asia/Tashkent: авто-напоминания должникам в Telegram.
"""
import json

from django.db import migrations

CRONTAB_PARAMS = {
    "minute": "0",
    "hour": "9",
    "day_of_week": "*",
    "day_of_month": "*",
    "month_of_year": "*",
    "timezone": "Asia/Tashkent",
}

TASK_NAME = "tgbot-debt-reminder-daily"
TASK_PATH = "apps.tgbot.debt_reminder_daily_task"


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
                "Ежедневные Telegram-напоминания всем должникам "
                "(SaleOrder confirmed + не полностью оплачен)."
            ),
        },
    )


def remove_schedule(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name=TASK_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("tgbot", "0001_initial"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(seed_schedule, remove_schedule),
    ]
