"""
Создаёт периодические задачи Celery Beat для модуля feedlot:
  1. `feedlot-daily-log-check` — 10:00 Asia/Tashkent — напоминание операторам
     если daily-log не заполнен на сегодня
  2. `feedlot-kpi-alerts` — 18:00 Asia/Tashkent — алерты по KPI
     (mortality, FCR) при превышении порогов

Расписания согласованы с ТЗ §F1 (мобильная фабрика end-to-end + KPI-алерты §6).
"""
import json

from django.db import migrations


SCHEDULES = [
    {
        "name": "feedlot-daily-log-check",
        "task": "apps.feedlot.daily_log_check_task",
        "description": (
            "Каждое утро 10:00 проверяет какие активные партии откорма не "
            "имеют записи DailyWeighing/Mortality за сегодня и шлёт TG-напоминание."
        ),
        "crontab": {
            "minute": "0",
            "hour": "10",
            "day_of_week": "*",
            "day_of_month": "*",
            "month_of_year": "*",
            "timezone": "Asia/Tashkent",
        },
    },
    {
        "name": "feedlot-kpi-alerts",
        "task": "apps.feedlot.kpi_alerts_task",
        "description": (
            "Каждый вечер 18:00 проверяет KPI всех активных партий откорма "
            "(падёж, FCR) и шлёт TG-алерт при превышении порогов."
        ),
        "crontab": {
            "minute": "0",
            "hour": "18",
            "day_of_week": "*",
            "day_of_month": "*",
            "month_of_year": "*",
            "timezone": "Asia/Tashkent",
        },
    },
]


def seed(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    for s in SCHEDULES:
        schedule, _ = CrontabSchedule.objects.get_or_create(**s["crontab"])
        PeriodicTask.objects.update_or_create(
            name=s["name"],
            defaults={
                "crontab": schedule,
                "task": s["task"],
                "args": json.dumps([]),
                "kwargs": json.dumps({}),
                "enabled": True,
                "description": s["description"],
            },
        )


def remove(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    for s in SCHEDULES:
        PeriodicTask.objects.filter(name=s["name"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("feedlot", "0001_initial"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(seed, remove),
    ]
