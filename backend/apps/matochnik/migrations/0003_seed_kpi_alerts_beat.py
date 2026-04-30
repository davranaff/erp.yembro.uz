"""
Создаёт периодические задачи Celery Beat для модуля matochnik:
  1. `matochnik-daily-log-check` — 10:00 Asia/Tashkent — напоминание
     если daily-log не заполнен за сегодня
  2. `matochnik-kpi-alerts` — 18:00 Asia/Tashkent — алерты по KPI
     (низкая яйценоскость, повышенный падёж за неделю)
"""
import json

from django.db import migrations


SCHEDULES = [
    {
        "name": "matochnik-daily-log-check",
        "task": "apps.matochnik.daily_log_check_task",
        "description": (
            "Каждое утро 10:00 проверяет какие активные стада не имеют записи "
            "DailyEggProduction/Mortality/FeedConsumption за сегодня и шлёт "
            "TG-напоминание технологам."
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
        "name": "matochnik-kpi-alerts",
        "task": "apps.matochnik.kpi_alerts_task",
        "description": (
            "Каждый вечер 18:00 проверяет KPI всех активных стад "
            "(яйценоскость, недельный падёж) и шлёт TG-алерт при превышении порогов."
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
        ("matochnik", "0002_business_logic_fixes"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(seed, remove),
    ]
