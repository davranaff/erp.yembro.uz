"""
Создаёт периодическую задачу Celery Beat `feed-shrinkage-daily` —
ежедневно в 02:00 Asia/Tashkent (см. spec §5.1) для прогона алгоритма
усушки по всем активным организациям.
"""
import json

from django.db import migrations


CRONTAB_PARAMS = {
    "minute": "0",
    "hour": "2",
    "day_of_week": "*",
    "day_of_month": "*",
    "month_of_year": "*",
    "timezone": "Asia/Tashkent",
}

TASK_NAME = "feed-shrinkage-daily"
TASK_PATH = "apps.feed.apply_feed_shrinkage_task"


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
                "Ежедневное компаундное списание усушки сырья и готового корма "
                "по активным профилям FeedShrinkageProfile (spec §5.1)."
            ),
        },
    )


def remove_schedule(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name=TASK_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("feed", "0004_shrinkage_profiles_and_states"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(seed_schedule, remove_schedule),
    ]
